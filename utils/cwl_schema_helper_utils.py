#!/usr/bin/env python3

"""
Schema helper types, again something set up WAY TOO LATE!
"""
import os.path
from typing import Optional, Dict, List
from pathlib import Path
from utils.repo import \
    join_run_path_from_caller_path, \
    get_cwl_ica_repo_path
from utils.miscell import \
    get_name_version_tuple_from_cwl_file_path, \
    get_items_dir_from_cwl_file_path
from classes.cwl_schema import CWLSchema


def check_dict_field_type_for_imports(field_type, schema_path) -> Optional[Path]:
    if not isinstance(field_type, Dict):
        return
    if "$import" in field_type.keys():
        import_path: Path = Path(field_type["$import"].split("#", 1)[0])
        return join_run_path_from_caller_path(schema_path, import_path)


def get_schemas(cwl_item) -> List[Path]:
    """
    Get schema list from workflow object
    """
    cwl_obj = cwl_item.cwl_obj
    schema_list = []

    # Get loading options
    loading_options = cwl_obj.loadingOptions.idx[cwl_obj.loadingOptions.fileuri]

    # Collect schemas from namespaces
    namespaces = loading_options.get("$namespaces")
    for namespace in namespaces:
        if "#" not in namespace:
            continue
        schema_run_path = namespace.split("#", 1)[0]
        schema_list.append(join_run_path_from_caller_path(cwl_item.cwl_file_path, schema_run_path))

    return schema_list


def get_schema_mappings(schema_list: List[Path], item_path: Path) -> List[Dict]:

    # Initialise output
    schema_mappings = []

    for schema in schema_list:
        schema_mappings.append(
            {
                "old": os.path.relpath(schema, item_path.parent),
                "new": str(
                    schema.relative_to(get_cwl_ica_repo_path())
                )
            }
        )

    return schema_mappings


def add_additional_schemas_to_schema_list_recursively(schema_list: List[Path]) -> List[Path]:
    schema_list = schema_list.copy()
    while True:
        original_schema_length = len(schema_list)
        additional_schemas = []
        for schema_path in schema_list:
            name, version = get_name_version_tuple_from_cwl_file_path(
                schema_path,
                get_items_dir_from_cwl_file_path(schema_path)
            )
            schema_obj = CWLSchema(schema_path, name, version)
            for field, field_obj in schema_obj.cwl_obj.get("fields").items():

                cwl_type = field_obj.get("type")

                if isinstance(cwl_type, str):
                    continue

                # If instance is a list, make sure we remove either the 'null' bit
                if isinstance(cwl_type, List):
                    if cwl_type[0] == "null":
                        _ = cwl_type.pop(0)
                    if len(cwl_type) == 1:
                        cwl_type = cwl_type[0]
                    else:
                        for field_item in cwl_type:
                            additional_import = check_dict_field_type_for_imports(field_item, schema_obj.cwl_file_path)
                            if additional_import is not None:
                                additional_schemas.append(additional_import)

                # Check for additional schemas
                if isinstance(cwl_type, Dict):
                    if cwl_type.get("type", None) is not None and cwl_type.get("type") == "array":
                        additional_import = check_dict_field_type_for_imports(cwl_type.get("items"),
                                                                              schema_obj.cwl_file_path)
                    else:
                        additional_import = check_dict_field_type_for_imports(cwl_type, schema_obj.cwl_file_path)
                    if additional_import is not None:
                        additional_schemas.append(additional_import)

        schema_list = list(set(schema_list + additional_schemas))

        if len(schema_list) == original_schema_length:
            break

    return schema_list
