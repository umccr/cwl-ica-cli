#!/usr/bin/env python3

"""
Given a path to a cwl schema, generate a typescript interface for the schema
"""

# Imports
from __future__ import annotations
from pathlib import Path
import logging
from typing import Dict, List, Union
from tempfile import NamedTemporaryFile
from subprocess import run, CompletedProcess
import json
import re
import os
from os.path import relpath
import argparse

# Globals
CWL_ICA_REPO_PATH = Path(os.environ.get("CWL_ICA_REPO_PATH", ""))
SCHEMA_PATH = Path(CWL_ICA_REPO_PATH) / "schemas"
LOGGER_STYLE = "%(asctime)s - %(levelname)-8s - %(module)-25s - %(funcName)-40s : LineNo. %(lineno)-4d - %(message)s"

# Use basic logging
# Set logger
logger = logging.getLogger()
# Set basic logger
logger.setLevel(level=logging.INFO)

# Set formatter
formatter = logging.Formatter(LOGGER_STYLE)

# Set console handler
console_hander = logging.StreamHandler()
console_hander.setLevel(logging.INFO)
console_hander.setFormatter(formatter)


# Helper functions
def camel_case(s: str) -> str:
    """
    Convert "bclconvert_settings" to "BclconvertSettings"
    :param s:
    :return:
    """
    s = re.sub(r"[_|-]+", " ", s).title().replace(" ", "")
    return ''.join(s)


def strip_versioning(versioned_string: str) -> str:
    """
    Convert 'bclconvert-data-row__3.10.5' to 'bclconvert-data-row'
    """
    return re.sub(r"__\d+.\d+.\d+(?:--\S+)?$", "", versioned_string)


def check_cwl_tool() -> None:
    """
    Ensure cwltool exists
    :return:
    """
    cwltool_version_check_proc = run(["cwltool", "--version"], capture_output=True)

    if not cwltool_version_check_proc.returncode == 0:
        logger.error("Could not get cwltool version from command 'cwltool --version'")
        raise EnvironmentError


def create_packed_schema_json(cwl_yaml_path: Path) -> Dict:
    """
    Creates a template file around the schema and runs cwltool --pack to generate the output schema

    cwlVersion: v1.1
    class: CommandLineTool

    requirements:
      SchemaDefRequirement:
        types:
          - $import: cwl_yaml_path

    inputs: {}
    outputs: {}

    :param cwl_yaml_path:
    :return:
    """
    cwl_tool_file = NamedTemporaryFile(prefix=str(cwl_yaml_path.stem) + ".tool.cwl")

    with open(cwl_tool_file.name, "w") as cwl_tool_file_h:
        cwl_tool_file_h.write(
            "cwlVersion: v1.1" + "\n" +
            "" + "\n" +
            "class: CommandLineTool" + "\n" +
            "" + "\n" +
            "requirements:" + "\n" +
            "  SchemaDefRequirement:" + "\n" +
            "    types:" + "\n" +
            f"     - $import: {cwl_yaml_path.absolute()}" + "\n" +
            "inputs: {}\n" +
            "outputs: {}\n"
        )

    cwltool_pack_proc: CompletedProcess = run(["cwltool", "--pack", cwl_tool_file.name], capture_output=True)

    if not cwltool_pack_proc.returncode == 0:
        logger.error(f"cwltool failed with error '{cwltool_pack_proc.stderr.decode()}'")
        raise RuntimeError

    cwl_packed: Dict = json.loads(cwltool_pack_proc.stdout.decode())

    # Check requirements exists and is of list
    requirements: List = cwl_packed.get("requirements", [])

    if not isinstance(requirements, List) and len(requirements) > 0:
        logger.error("Could not collect requirements from cwltool packed object")

    # Get length of first requirement, check has 'types'
    types: List = requirements[0].get("types", [])

    if not isinstance(types, List) and len(types) > 0:
        logger.error("Could not collect 'types' from cwltool packed object")

    return types[0]


def sanitise_schema_types(schema_json: Dict, schema_path: Path, schema_name: Union[str | None] = None) -> (Dict, Dict, List):
    """
    Sanitise the schema types from the schema json
    If items are arrays they will have the '[]' suffix in the type name
    If items are optional, they will have the '?' suffix in the type name
    :param schema_name:
    :param schema_json:
    :param schema_path:
    :return:
    """
    # Things we return (in order)
    sanitised_schemas: Dict = {}
    imported_interfaces: Dict = {}
    new_enum_classes: List = []

    # Other local vars
    if schema_name is None:
        schema_name: str = camel_case(schema_path.stem.split("__", 1)[0])
    sanitised_schema: Dict = {}

    field: Dict
    for field in schema_json.get("fields"):
        # Get basics
        field_name: str = Path(field.get("name")).name
        field_label: str = field.get("label", "")
        field_description: str = field.get("doc", "")
        field_optional: bool = False
        field_is_array: bool = False

        # Get field type
        field_type: Union[List | Dict | str] = field.get("type")

        # Check if field type is optional
        if isinstance(field_type, List):
            if field_type[0] == 'null':
                field_optional = True
                # Remove field now
                _ = field_type.pop(0)
            if len(field_type) == 1:
                field_type = field_type[0]
            else:
                re_sanitised_schemas_ext: List[Dict] = []
                re_imported_interfaces_ext: Dict = {}
                re_new_enum_classes_ext: List = []
                for field_type_item in field_type:
                    # Multi-type
                    re_sanitised_schemas: Dict
                    re_imported_interfaces: Dict
                    re_new_enum_classes: List
                    re_sanitised_schemas, re_imported_interfaces, re_new_enum_classes = \
                        sanitise_schema_types({"fields": [
                                                {
                                                    "name": field_name,
                                                    "label": field_label,
                                                    "doc": field_description,
                                                    "type": field_type_item
                                                }
                                              ]
                                              }, schema_path,
                                              schema_name=field_name)
                    re_sanitised_schemas_ext.append(re_sanitised_schemas.get(field_name))
                    re_imported_interfaces_ext.update(re_imported_interfaces)
                    re_new_enum_classes_ext.extend(re_new_enum_classes)

                # Use a pipe to indicate that this item can be multiple types
                field_type = \
                    " | ".join([schema_[field_name].get("type") for schema_ in re_sanitised_schemas_ext])
                # Then extend interfaces
                imported_interfaces.update(re_imported_interfaces_ext)
                new_enum_classes.extend(re_new_enum_classes_ext)

        # Check if field type is a dict and that it is an array
        if isinstance(field_type, Dict) and field_type.get("type", None) is not None \
                and field_type.get("type") == "array":
            field_type = field_type.get("items")
            field_is_array = True

        # Check if field type is an enum
        if isinstance(field_type, Dict) and field_type.get("type", None) is not None \
                and field_type.get("type") == "enum":
            # Collect symbols
            symbols = [
                Path(symbol).name
                for symbol in field_type.get("symbols")
            ]

            # Collect new field type name
            new_field_type = camel_case(Path(field_type.get("symbols")[0]).parent.name)

            field_type = new_field_type

            new_enum_classes.append({
                "name": field_type,
                "symbols": symbols
            })

        # Check if field type is a record (imported only)
        if isinstance(field_type, Dict) and field_type.get("type", None) is not None and \
                field_type.get("type") == "record":

            # Check if from the same file
            if schema_path.name == Path(field_type.get("name")).parts[0].lstrip("#"):
                # Extend values recursively
                re_sanitised_schemas: Dict
                re_imported_interfaces: Dict
                re_new_enum_classes: List
                re_sanitised_schemas, re_imported_interfaces, re_new_enum_classes = \
                    sanitise_schema_types(field_type, schema_path,
                                          schema_name=camel_case(Path(field_type.get("name")).name))
                sanitised_schemas.update(re_sanitised_schemas)
                imported_interfaces.update(re_imported_interfaces)
                new_enum_classes.extend(re_new_enum_classes)
                field_type = camel_case(Path(field_type.get("name")).name)
            else:
                # Add to list of interfaces to import
                new_interface_name = camel_case(Path(field_type.get("name")).name)
                imported_interfaces[new_interface_name] = field_type.get("name")
                field_type = new_interface_name

        # Check if field type is a string and set to 'int', we change to number for typescript
        if isinstance(field_type, str) and field_type in ["int", "float"]:
            field_type = "number"

        # Check if field type is of type File or Directory and rename to IFile or IDirectory
        if isinstance(field_type, str) and field_type == "File":
            field_type = "IFile"
        if isinstance(field_type, str) and field_type == "Directory":
            field_type = "IDirectory"

        if field_is_array:
            field_type += "[]"

        if field_optional:
            field_name += "?"

        sanitised_schema[field_name] = {
            "label": field_label,
            "doc": field_description,
            "type": field_type
        }

    for value in sanitised_schema.values():
        if value.get("type") == "IFile":
            imported_interfaces["FileProperties as IFile"] = "cwl-ts-auto"
        if value.get("type") == "IDirectory":
            imported_interfaces["DirectoryProperties as IDirectory"] = "cwl-ts-auto"

    # Add this schema to list of schemas to create
    sanitised_schemas[schema_name] = sanitised_schema

    return sanitised_schemas, imported_interfaces, new_enum_classes


def write_interface_file(schema_dicts: Dict, imported_interfaces: Dict,
                         enum_classes: List, schema_path: Path, interface_path: Path) -> None:
    """
    Write interface file
    :param schema_dicts:
    :param imported_interfaces:
    :param enum_classes:
    :param schema_path:
    :param interface_path:
    :return:
    """
    with open(interface_path, "w") as interface_h:
        # Add imports to top of file
        for _import, _import_path in imported_interfaces.items():
            # Split the name and version of the schema
            if "__" in _import_path:
                name, version = Path(_import_path.lstrip("#")).parent.stem.split("__", 1)
                # Collect the path of the schema from absolute path
                _import_path = SCHEMA_PATH / name / f"{version}" / f"{name}__{version}"
                # Now resolve that from the path of the schema importing this schema
                _import_path = relpath(_import_path.absolute().resolve(), interface_path.parent.absolute().resolve())
            else:
                _import_path = "cwl-ts-auto"

            interface_h.write("import { %s } from \"%s\"\n" % (_import, _import_path))
        if len(imported_interfaces) > 0:
            interface_h.write("\n")

        # Add enum methods to top of file
        for _enum in enum_classes:
            interface_h.write("export enum %s {\n" % _enum.get("name"))
            for index, symbol in enumerate(_enum.get("symbols")):
                interface_h.write("\t%s = \"%s\"" % (symbol, symbol))
                if not index == len(_enum.get("symbols")) - 1:
                    # Add comma
                    interface_h.write(",")
                interface_h.write("\n")
            interface_h.write("}\n\n")

        for schema_name, schema_dict in schema_dicts.items():
            # Add interface
            interface_h.write("export interface %s {\n" % schema_name)

            for field_name, field_values in schema_dict.items():
                # Write out the interface attribute
                interface_h.write(
                    "\t/*\n"
                    "\t%s: \n"
                    "\t%s\n"
                    "\t*/\n" % (
                        field_values.get("label", field_name),
                        "\n\t".join(field_values.get("doc", "").rstrip("\n").split("\n"))
                    )
                )
                interface_h.write("\t%s: %s\n" % (field_name, field_values.get("type")))

                if not field_name == list(schema_dict.keys())[-1]:
                    interface_h.write("\n")

            interface_h.write("}\n")
            if not schema_name == list(schema_dicts.keys())[-1]:
                interface_h.write("\n")


# args functions
def get_args():
    """
    Get arguments from command line
    :return:
    """
    args = argparse.ArgumentParser(description="Create a typescript interface from a CWL Schema")

    args.add_argument(
        "--schema-path",
        help="Path to schema file",
        required=True
    )

    return args.parse_args()


def check_args(args):
    """
    Check args
    :return:
    """
    # Collect schema path variable
    schema_path: Path = Path(getattr(args, "schema_path", ""))

    # Check when is file
    if not schema_path.is_file():
        logger.error(f"Could not get find schema path file '{schema_path}'. Check the --schema-path parameter")
        raise ValueError

    # Convert schema_path attribute to Path object
    setattr(args, "schema_path", schema_path)

    return args


# main function
def main():
    """
    Perform the following tasks
    * Import args
    * Check args
    * Convert schema into json by using cwltool --pack
    * Sanitise schema
    * Write output
    :return:
    """
    # Import / check args
    args = get_args()
    args = check_args(args)
    schema_path: Path = getattr(args, "schema_path")

    # Check cwltool is good
    check_cwl_tool()

    # Convert schema into json
    schema_as_json: Dict = create_packed_schema_json(schema_path)

    # Sanitise schema
    schema_as_json_sanitised: Dict
    imported_interfaces: Dict
    new_enum_classes: List
    schema_as_json_sanitised, imported_interfaces, new_enum_classes = \
        sanitise_schema_types(schema_as_json, schema_path)

    # Write output
    interface_path = schema_path.parent / (schema_path.stem + ".ts")
    write_interface_file(schema_as_json_sanitised, imported_interfaces, new_enum_classes, schema_path, interface_path)


if __name__ == "__main__":
    main()
