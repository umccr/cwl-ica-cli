#!/usr/bin/env python3

"""
Some handy scripts for creating input templates - particularly for yaml inputs
"""
import logging

from ruamel.yaml.comments import CommentedMap as OrderedDict
from ruamel.yaml.comments import CommentedSeq as OrderedList

from bin.create_typescript_interface_from_schema import create_packed_schema_json
from utils.logging import get_logger
from utils.errors import CWLTypeNotFoundError
from utils.globals import BLOCK_YAML_INDENTATION_LEVEL, YAML_INDENTATION_LEVEL
import re
from typing import Dict, List
from pathlib import Path
from cwl_utils.parser.latest import \
    SecondaryFileSchema

logger = get_logger()


def create_input_dict(cwl_inputs: Dict, cwl_file_path: Path) -> OrderedDict:
    """
    Create a commented map object from the input template.
    Will have the three top keys

    name:
    cwl_inputs:
    engine_parameters:

    :param cwl_inputs:
    :param cwl_file_path:
    :param output_file_path:
    :param name:
    :param engine_parameters:
    :return:
    """

    input_dict = OrderedDict()

    for cwl_input_id, cwl_input_dict in cwl_inputs.items():
        """
        For each cwl input, append a commented map of the input object
        """
        # FIXME - secondary items causing issues https://github.com/umccr/cwl-ica-cli/issues/1
        if cwl_input_dict.get("cwl_type", None) is None:
            logger.error("CWL Input object is in the wrong format, no 'cwl_type' found.")
            raise KeyError

        if isinstance(cwl_input_dict["cwl_type"], list):
            # Deal with multiple types
            # First use type one
            input_dict = get_commented_map_for_input_object(
                input_dict,
                input_id=cwl_input_id,
                cwl_type=cwl_input_dict.get("cwl_type")[0],
                label=cwl_input_dict.get("label"),
                doc=cwl_input_dict.get("doc"),
                is_array=cwl_input_dict.get("is_array", 0),
                optional=cwl_input_dict.get("optional", False),
                indentation_level=YAML_INDENTATION_LEVEL
            )
            # Add note to item that it could be of multiple types
            try:
                input_dict.get("input").yaml_add_eol_comment(key=cwl_input_id,
                                                             comment=f"Could also be of type [{', '.join(type_ for type_ in cwl_input_dict.get('cwl_type')[1:])}]")
            except TypeError:
                logger.warning(f"Cannot add eol to input {cwl_input_id}")
        else:
            if cwl_input_dict.get("cwl_type") == "schema":
                # Create a pre comment
                input_dict.yaml_set_comment_before_after_key(key=cwl_input_id,
                                                             before=f"// {'Optional' if cwl_input_dict.get('optional') else 'Required'} Input: {cwl_input_dict.get('label')} //",
                                                             indent=YAML_INDENTATION_LEVEL)
                input_dict = get_commented_map_for_schema_input_object(
                    input_dict,
                    input_object=cwl_input_dict.get("schema_obj").get("fields"),
                    input_id=cwl_input_id,
                    label=cwl_input_dict.get("label"),
                    doc=cwl_input_dict.get("doc"),
                    indentation_level=YAML_INDENTATION_LEVEL+4,
                    is_array=cwl_input_dict.get("is_array", 0)
                )
            else:
                input_dict = get_commented_map_for_input_object(
                    input_dict,
                    input_id=cwl_input_id,
                    cwl_type=cwl_input_dict.get("cwl_type"),
                    label=cwl_input_dict.get("label"),
                    doc=cwl_input_dict.get("doc"),
                    optional=cwl_input_dict.get("optional", False),
                    symbols=cwl_input_dict.get("symbols"),
                    is_array=cwl_input_dict.get("is_array", 0),
                    secondary_files=cwl_input_dict.get("secondary_files"),
                    indentation_level=YAML_INDENTATION_LEVEL
                )

    return input_dict

    # Write out dumper manually
    #with open(str(output_file_path), 'w') as yaml_h:
    #    # Dump out the name
    #    round_trip_dump(OrderedDict({"name": name}), yaml_h)
    #    # Iterate throughout the inputs, dump each item in the yaml dict separately
    #    # Very hacky, but the best option we had at the time
    #    yaml_h.write("input:\n")
    #    for input_id, input_item in input_dict.items():
    #        for line in round_trip_dump(OrderedDict({input_id: input_item}), indent=4).splitlines(True):
    #            if cwl_inputs[input_id]["optional"]:
    #                yaml_h.write("    # " + line)
    #            else:
    #                yaml_h.write("    " + line)
    #    # Create the engine parameters
    #    round_trip_dump(OrderedDict({"engineParameters": engine_parameters}), yaml_h)


def get_commented_map_for_input_object(input_dict: OrderedDict, input_id: str, cwl_type: str, is_array: int = 0,
                                       label: str = None, doc: str = None, optional: bool = False, symbols: List = None,
                                       secondary_files: List[SecondaryFileSchema] = None, indentation_level: int = 0) -> OrderedDict:
    """
    For an input object, return a commented map based on the input type
    :param indentation_level:
    :param optional:
    :param input_dict:
    :param input_id:
    :param cwl_type: Singular type, create a commented map from this object
    :param is_array:
    :param label:
    :param doc:
    :param symbols:
    :param secondary_files:
    :return:
    """

    # Some schemas don't set optionals right?
    if cwl_type.endswith("?"):
        cwl_type = cwl_type.rstrip("?")
        optional = True

    # Low-hanging fruit types
    if cwl_type in ["string", "float", "int", "boolean"]:
        # Initialise the input dict
        if cwl_type == "string":
            input_dict[input_id] = "a_string"
        elif cwl_type == "float":
            input_dict[input_id] = 1.0
        elif cwl_type == "int":
            input_dict[input_id] = 1
        elif cwl_type == "boolean":
            input_dict[input_id] = False

        # input_dict.yaml
        # Create a eol comment (Informing user to fix a_string to something else)
        input_dict.yaml_set_comment_before_after_key(key=input_id,
                                                     before=f"// {'Optional' if optional else 'Required'} Input: {label} //",
                                                     indent=indentation_level)
        input_dict.yaml_add_eol_comment(key=input_id, comment="FIXME")

    # Schemas
    elif cwl_type in ["record"]:
        input_dict.yaml_set_comment_before_after_key(key=input_id,
                                                     before=f"// {'Optional' if optional else 'Required'} Input: {label} //",
                                                     indent=indentation_level)
        input_dict.yaml_add_eol_comment(key=input_id, comment="FIXME")
        input_dict[input_id] = get_commented_map_for_schema_input_object(
            input_dict=input_dict,
            input_object=input_dict[input_id].get("fields"),
            input_id=input_id,
            label=label,
            doc=doc,
            optional=optional,
            indentation_level=indentation_level + 4,
            is_array=0
        )

    # Enumerates
    elif cwl_type in ["enum"]:
        # Create a pre comment
        input_dict.yaml_set_comment_before_after_key(key=input_id,
                                                     before=f"// {'Optional' if optional else 'Required'} Input: {label} //",
                                                     indent=indentation_level)
        if cwl_type == "enum":
            input_dict[input_id] = symbols[0]
            try:
                input_dict.yaml_add_eol_comment(key=input_id,
                                                comment=f"Alternative options include [{', '.join(symbols[1:])}]")
            except TypeError:
                logger.warning(f"Cannot add eol to input {input_id}")

    # File objects
    elif cwl_type in ["File", "Directory"]:
        # Initialise the input dict
        input_dict[input_id] = OrderedDict({
            "class": cwl_type,
            "location": "gds://path/to/file"
        })
        # Add secondary files if applicable
        if secondary_files is not None:
            if not isinstance(secondary_files, List):
                logger.error(f"Got secondary files but wasn't list object for '{input_id}'")
                raise TypeError
            input_dict[input_id]["secondaryFiles"] = [
                {
                    "class": "File",
                    "location": f"gds://path/to/file{secondary_file.pattern}"
                }
                for secondary_file in secondary_files
            ]

        # Create a pre comment
        input_dict.yaml_set_comment_before_after_key(key=input_id,
                                                     before=f"// {'Optional' if optional else 'Required'} Input: {label} //",
                                                     indent=indentation_level)

        # Create an eol comment (Informing user to fix location to something else)
        input_dict[input_id].yaml_add_eol_comment(key="location",
                                                  comment="FIXME")

    else:
        logger.error(f"{cwl_type} is not a known type")
        raise CWLTypeNotFoundError

    nested_input_id = input_dict[input_id]
    while is_array > 0:
        # Countdown array
        is_array -= 1
        nested_input_id = OrderedList([nested_input_id])
    input_dict[input_id] = nested_input_id

    return input_dict


def get_commented_map_for_schema_input_object(
        input_dict: OrderedDict, input_id: str, input_object: OrderedDict,
        label: str, doc: str, optional: bool = False, indentation_level: int = 0, is_array: int = 0,
    ) -> OrderedDict:
    """
    For an input schema object, return a commented map based on the input type
    calls the get_commented_map_for_input_object for each record / field in the schema object
    :param optional:
    :param is_array:
    :param indentation_level:
    :param doc:
    :param label:
    :param input_id:
    :param input_dict:
    :param input_object:
    :return:
    """

    input_dict[input_id] = OrderedDict()

    if not isinstance(input_object, Dict):
        logger.error(f"Expected input object to be a dict but got {type(input_object)} instead")
        raise ValueError

    field_name: str
    field_items: OrderedDict
    for field_name in input_object.keys():
        field_items = input_object.get(field_name)
        # Pop optional 'null' from schema list
        if isinstance(field_items.get("type"), OrderedList):
            if len(field_items.get("type")) >= 1 and field_items.get("type")[0] == 'null':
                field_items["type"] = field_items.get("type")[1]
            else:
                logger.warning("Don't know what to do here, multiple items in field list or first item was not null")
                logger.warning(field_items.get("type"))
                continue

        # Check if type is field
        if isinstance(field_items.get("type"), OrderedDict):
            # Check if the input object is an array
            if field_items.get("type").get("type") == "array":
                is_array = 1
                field_items["type"] = field_items.get("type").get("items")

            if field_items.get("type").get("type") is not None and field_items.get("type").get("type") == "enum":
                # Enum inside schema?
                input_dict[input_id] = get_commented_map_for_input_object(
                    input_dict=input_dict[input_id],
                    input_id=field_name,
                    cwl_type=field_items.get("type").get("type"),
                    label=field_items.get("label"),
                    doc=field_items.get("doc"),
                    symbols=field_items.get("type").get("symbols"),
                    indentation_level=indentation_level
                )
            else:
                # if field_items.get("type").get("$import") is not None:
                #     # We have an external nested schema
                #     schema_import_path = schema_file_path.parent.joinpath(
                #         field_items.get("type").get("$import")
                #     ).absolute().resolve()
                #     logging.info("Importing external schema")
                #     #print(create_packed_schema_json(schema_import_path))
                #     input_dict[input_id] = get_commented_map_for_schema_input_object(
                #         input_dict[input_id],
                #         input_id=field_name,
                #         input_object=create_packed_schema_json(schema_import_path).get("fields"),
                #         schema_file_path=schema_file_path,
                #         label=field_items.get("label"),
                #         doc=field_items.get("doc"),
                #         indentation_level=indentation_level + 4
                #     )

                if field_items.get("type").get("fields") is None:
                    logger.warning(f"Don't know what this is. type has keys {field_items.get('type').keys()}")
                    logger.warning(f"Type is '{field_items.get('type')}'")
                    raise ValueError

                else:
                    # We have an internal nested schema (that we've already sanitised like a good boy)
                    input_dict[input_id] = get_commented_map_for_schema_input_object(
                        input_dict=input_dict[input_id],
                        input_id=field_name,
                        input_object=field_items.get("type").get("fields"),
                        label=field_items.get("label"),
                        doc=field_items.get("doc"),
                        indentation_level=indentation_level + 4
                    )
                    # Create a pre comment
                    input_dict[input_id].yaml_set_comment_before_after_key(key=field_name,
                                                                           before=f"// {'Optional' if optional else 'Required'} Input: {field_name} //",
                                                                           indent=indentation_level)
        elif isinstance(field_items.get("type"), str) and field_items.get("type") == "record":
            input_dict[input_id] = get_commented_map_for_schema_input_object(
                input_dict=input_dict[input_id],
                input_id=field_name,
                input_object=field_items.get("fields"),
                label=field_items.get("label"),
                doc=field_items.get("doc"),
                indentation_level=indentation_level + 4,
                is_array=field_items.get("is_array"),
                optional=field_items.get("optional")
            )
            # Create a pre comment
            input_dict[input_id].yaml_set_comment_before_after_key(key=field_name,
                                                                   before=f"// {'Optional' if field_items.get('optional') else 'Required'} Input: {field_name} //",
                                                                   indent=indentation_level)
        elif isinstance(field_items.get("type"), str):
            array_depth = 0
            while field_items.get("type").endswith("[]"):
                array_depth += 1
                field_items["type"] = re.sub(r"\[]$", "", field_items.get("type"))
            input_dict[input_id] = get_commented_map_for_input_object(
                input_dict[input_id],
                input_id=field_name,
                cwl_type=field_items.get("type"),
                is_array=array_depth,
                label=field_items.get("label"),
                doc=field_items.get("doc"),
                symbols=field_items.get("symbols") if field_items.get("type") == "enum" else None,
                secondary_files=field_items.get("secondary_files"),
                indentation_level=indentation_level
            )
        else:
            logger.error(f"Don't know how we got here. Field items type attribute is of type {type(field_items.get('type'))}")

    nested_input_id = input_dict[input_id]
    while is_array > 0:
        # Countdown array
        is_array -= 1
        nested_input_id = OrderedList([nested_input_id])
    input_dict[input_id] = nested_input_id

    return input_dict


def is_schema_input(input_object) -> bool:
    """
    Determine if the input object is a schema object
    returns a nested input
    :param input_object:
    :return:
    """
    if '#' in input_object.items:
        return True
    return False






