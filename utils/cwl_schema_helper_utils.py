#!/usr/bin/env python3

"""
Schema helper types, again something set up WAY TOO LATE!
"""
import re
from copy import deepcopy
from typing import Optional, Dict, List, Union
from pathlib import Path
from urllib.parse import urlparse
from cwl_utils.parser import Workflow

from utils.logging import get_logger
from ruamel.yaml import YAML

from utils.cwl_helper_utils import get_path_from_cwl_id
from utils.repo import \
    join_run_path_from_caller_path, \
    get_cwl_ica_repo_path
from utils.miscell import \
    get_name_version_tuple_from_cwl_file_path, \
    get_items_dir_from_cwl_file_path
from classes.cwl_schema import CWLSchema

from cwl_utils.parser.cwl_v1_0 import SchemaDefRequirement as SchemaDefRequirement_v1_0
from cwl_utils.parser.cwl_v1_1 import SchemaDefRequirement as SchemaDefRequirement_v1_1
from cwl_utils.parser.cwl_v1_2 import SchemaDefRequirement as SchemaDefRequirement_v1_2

from cwl_utils.parser.latest import RecordSchema

SchemaDefRequirement = Union[
    SchemaDefRequirement_v1_0,
    SchemaDefRequirement_v1_1,
    SchemaDefRequirement_v1_2
]

logger = get_logger()


class CWLSchemaObj:
    """
    Missing component of cwlutils
    """

    def __init__(self, cwl_obj, file_path):
        self.cwl_obj: RecordSchema = cwl_obj
        self.cwl_file_path: Path = file_path

        # Confirm type is record
        if not self.cwl_obj.type.get("type") == "record":
            logger.error("Expected record type")

    def get_input_from_str_type(self, workflow_input: Dict) -> Union[Dict, str, List]:
        if workflow_input.get("type").endswith("[]"):
            new_workflow_input = deepcopy(workflow_input)
            new_workflow_input["type"] = re.sub(r"\[]$", "", workflow_input.get("type"))
            return [
                self.get_input_from_str_type(new_workflow_input)
            ]
        if workflow_input.get("type").rstrip("?") == "Directory":
            return {
                "class": "Directory",
                "location": "icav2://project_id/path/to/dir/"
            }
        elif workflow_input.get("type").rstrip("?") == "File":
            return {
                "class": "File",
                "location": "icav2://project_id/path/to/file"
            }
        elif workflow_input.get("type").rstrip("?") == "boolean":
            return workflow_input.get("default") if workflow_input.get("default") is not None else False
        elif workflow_input.get("type").rstrip("?") == "int":
            return workflow_input.get("default") if workflow_input.get("default") is not None else "string"
        elif workflow_input.get("type").rstrip("?") == "string":
            return workflow_input.get("default") if workflow_input.get("default") is not None else "string"

    def get_input_from_array_type(self, workflow_input: Dict) -> Union[Dict, str, List]:
        """
        Likely first element of type is null
        :param workflow_input:
        :return:
        """
        workflow_input_new = deepcopy(workflow_input)
        if workflow_input.get("type")[0] == "null":
            workflow_input_new["type"] = workflow_input.get("type")[1]
        else:
            workflow_input_new["type"] = workflow_input.get("type")[0]

        if isinstance(workflow_input_new.get("type"), Dict):
            return self.get_input_from_dict_type(workflow_input_new)
        elif isinstance(workflow_input_new.get("type"), List):
            return self.get_input_from_array_type(workflow_input_new)
        elif isinstance(workflow_input_new.get("type"), str):
            return self.get_input_from_str_type(workflow_input_new)
        else:
            logger.error(f"Unsure what to do with type {type(workflow_input_new.get('type'))}")
            raise NotImplementedError

    def get_input_from_record_type(self, workflow_input: Dict) -> Union[Dict]:
        """
        Very similar to schema base command
        :param workflow_input:
        :return:
        """
        workflow_inputs = {}
        for field_key, field_dict in workflow_input.get("fields").items():
            if isinstance(field_dict.get("type"), Dict):
                workflow_inputs.update(
                    {
                        field_key: self.get_input_from_dict_type(field_dict)
                    }
                )
            elif isinstance(field_dict.get("type"), List):
                workflow_inputs.update(
                    {
                        field_key: self.get_input_from_array_type(field_dict)
                    }
                )
            elif isinstance(field_dict.get("type"), str):
                workflow_inputs.update(
                    {
                        field_key: self.get_input_from_str_type(field_dict)
                    }
                )
            else:
                logger.warning(f"Don't know what to do with type {type(field_dict.get('type'))} for key {field_key}")
        return workflow_inputs

    def get_input_from_dict_type(self, workflow_input: Dict) -> Union[Dict, List]:
        """
        Dict type
        :param workflow_input:
        :return:
        """
        if "type" in workflow_input.get("type").keys() and workflow_input.get("type").get("type") == "record":
            return self.get_input_from_record_type(workflow_input.get("type"))
        if "type" in workflow_input.get("type").keys() and workflow_input.get("type").get("type") == "array":
            if isinstance(workflow_input.get("type").get("items"), str):
                return [
                    self.get_input_from_str_type(
                        {
                            "type": workflow_input.get("type").get("items")
                        }
                    )
                ]
            elif isinstance(workflow_input.get("type").get("items"), Dict):
                # We have an import
                return self.get_input_from_dict_type(
                    {
                        "type": workflow_input.get("type").get("items")
                    }
                )
        if "$import" in workflow_input.get("type").keys():
            schema_path = self.cwl_file_path.parent.joinpath(
                get_path_from_cwl_id(workflow_input.get("type").get("$import"))
            ).resolve()
            return CWLSchemaObj.load_schema_from_uri(schema_path.as_uri()).get_template()

    def get_template(self) -> Dict:
        """
        Return get inputs from dict
        :return:
        """
        workflow_inputs = {}
        for field_key, field_dict in self.cwl_obj.type.get("fields").items():
            if isinstance(field_dict.get("type"), Dict):
                workflow_inputs.update(
                    {
                        field_key: self.get_input_from_dict_type(field_dict)
                    }
                )
            elif isinstance(field_dict.get("type"), List):
                workflow_inputs.update(
                    {
                        field_key: self.get_input_from_array_type(field_dict)
                    }
                )
            elif isinstance(field_dict.get("type"), str):
                workflow_inputs.update(
                    {
                        field_key: self.get_input_from_str_type(field_dict)
                    }
                )
            else:
                logger.warning(f"Don't know what to do with type {type(field_dict.get('type'))} for key {field_key}")
        return workflow_inputs

    @classmethod
    def load_schema_from_uri(cls, uri_input):
        file_path: Path = Path(urlparse(uri_input).path)

        yaml = YAML()

        with open(file_path, "r") as schema_h:
            schema_obj = yaml.load(schema_h)

        return cls(RecordSchema(schema_obj), file_path)


def check_dict_field_type_for_imports(field_type, schema_path) -> Optional[Path]:
    if not isinstance(field_type, Dict):
        return
    if "$import" in field_type.keys():
        import_path: Path = get_path_from_cwl_id(field_type["$import"])
        return join_run_path_from_caller_path(schema_path, import_path)


def get_schemas(cwl_item) -> List[Path]:
    """
    Get schema list from workflow object
    """
    cwl_obj: Workflow = cwl_item.cwl_obj
    schema_list = []

    schema_def_requirement = None

    # Collect schemas from requirements
    requirements = cwl_obj.requirements
    if requirements is None:
        return []

    for requirement in cwl_obj.requirements:
        if isinstance(requirement, SchemaDefRequirement):
            schema_def_requirement = requirement

    if schema_def_requirement is None:
        return []

    for schema_type in schema_def_requirement.types:
        schema_list.append(Path(urlparse(schema_type.name).path))

    return schema_list


def get_schema_mappings(schema_list: List[Path], item_path: Path) -> List[Dict]:

    # Initialise output
    schema_mappings = []

    for schema in schema_list:
        schema_mappings.append(
            {
                "schema_name": schema.name,
                "schema_path":
                    urlparse(
                            str(
                                join_run_path_from_caller_path(
                                    item_path, schema,
                                ).relative_to(get_cwl_ica_repo_path())
                            )
                    ).path
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
