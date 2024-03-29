#!/usr/bin/env python

"""
A subclass of cwl, this function implements the validate and create for a cwl object
Based mostly on the cwl-utils package
"""
# External imports
import re
from copy import deepcopy
from typing import List, Dict
from ruamel.yaml import YAML
from tempfile import NamedTemporaryFile
from pathlib import Path
from ruamel.yaml.comments import CommentedMap as OrderedDict
import json

# CWL Utils
from cwl_utils.parser.latest import \
    RecordSchema

# Utils
from ..utils.cwl_helper_utils import split_cwl_id_to_path_and_fragment
from ..utils.logging import get_logger
from ..utils.errors import CWLSchemaError

# Locals
from .cwl import CWL

# Set logger
logger = get_logger()


class CWLSchema(CWL):
    """
    Implement the validate_object and create_object and write_object implementations for a cwltool
    """

    VALID_TYPES = ["record", "enum"]

    def __init__(self, cwl_file_path, name, version, create=False, user_obj=None):
        # Call super class
        super().__init__(cwl_file_path, name, version, cwl_type="schema", create=create, user_obj=user_obj)

    def import_cwl_yaml(self):
        # Read in the cwl file from a yaml
        yaml = YAML()
        with open(self.cwl_file_path, "r") as cwl_h:
            yaml_obj = yaml.load(cwl_h)

        self.cwl_obj = RecordSchema(yaml_obj).type_

    def validate_object(self):
        """
        Validate a cwl schema object

        A cwl schema expects the following

        1. type is of enum or record
        2. name attribute is present
        3. If type is of type record, each field has a label and a doc
        :return:
        """

        # Initialise count
        validation_passing = True
        issue_count = 0

        # Check type attr
        schema_type = self.cwl_obj.get("type", None)
        if schema_type is None:
            logger.error(f"Expected 'type' attribute but not found in \"{self.cwl_file_path}\"")
            raise CWLSchemaError

        # Schema supports two types, records and enums
        if schema_type not in self.VALID_TYPES:
            logger.error("Expected one of \"{valid_types}\" but got \"{obj_type}\"".format(
                valid_types=", ".join(self.VALID_TYPES),
                obj_type=self.cwl_obj.get("type")
            ))
            raise CWLSchemaError

        # Check if 'name' attr present
        if self.cwl_obj.get("name") is None:
            logger.error(f"Expected to retrieve \"name\" attribute for schema in path \"{self.cwl_file_path}\"")
            validation_passing = False

        # Do record based check which just makes sure that for each attribute we have a doc / label
        validation_passing_fields = []
        if schema_type == "record":
            for field_name, field_attrs in self.cwl_obj.get("fields").items():
                validation_passing_field, issue_count = self.check_docs([field_attrs], issue_count)
                validation_passing_fields.append(validation_passing_field)

        for vpf in validation_passing_fields:
            validation_passing = validation_passing * vpf

        # Write 'type' to named temporary file
        type_tempfile = NamedTemporaryFile(suffix=".schema.packed.json")

        with open(type_tempfile.name, 'w') as type_tempfile_h:
            type_tempfile_h.write(json.dumps(self.cwl_obj))

        # Set md5sum
        self.md5sum = self.get_packed_md5sum(type_tempfile)

        if not validation_passing:
            logger.error(f"Validation failed with {issue_count} issues.")
            raise CWLSchemaError

    def create_object(self, user_obj):
        """
        Create a new cwl schema
        :return:
        """

        self.cwl_obj = RecordSchema(
            type_="record",
            fields=[]
        )

    # Write the tool to the cwltool file path
    def write_object(self, user_obj):
        """
        Write the tool to the cwltool file path
        :return:
        """

        # Rather than use .save() (which doesn't order everything quite the way we want it to)
        # We create our own dict from the object first, then use the round_trip_dumper

        # Before we commence we have to reorganise a couple of setting

        # Create ordered dictionary ready to be written
        write_obj = OrderedDict({
            "type": self.cwl_obj.type_,
            "name": self.name,
            "fields": self.cwl_obj.fields,
        })

        yaml = YAML()
        yaml.indent = 4
        yaml.block_seq_indent = 2

        with open(self.cwl_file_path, 'w') as cwl_h:
            yaml.dump(write_obj, cwl_h)

    def check_docs(self, cwl_attr_list, issue_count):
        """
        Check labels and docs for schema fields
        :param cwl_attr_list:
        :param issue_count:
        :return:
        """
        validation_passing = True
        # Check inputs
        for cwl_obj in cwl_attr_list:
            # Check label and doc
            if cwl_obj.get("label", None) is None:
                issue_count += 1
                logger.error(f"Issue {issue_count}: Input \"{cwl_obj.get('id', None)}\" "
                             f"does not have a 'label' attribute \"{self.cwl_file_path}\"")
                validation_passing = False
            if cwl_obj.get("doc", None) is None:
                issue_count += 1
                logger.error(f"Issue {issue_count}: Input \"{cwl_obj.get('id', None)}\" "
                             f"does not have a 'doc' attribute \"{self.cwl_file_path}\"")
                validation_passing = False

        return validation_passing, issue_count

    def get_sanitised_object(self) -> OrderedDict:
        new_cwl_obj = deepcopy(self.cwl_obj)

        new_fields = OrderedDict()
        for field_key, field_dict in new_cwl_obj.get("fields").items():
            field_type = deepcopy(field_dict.get("type"))
            is_array = 0
            optional = False

            # Check if null
            if isinstance(field_type, List):
                if field_dict.get("type")[0] == "null":
                    optional = True
                    field_type = field_dict.get("type")[1]

            # Latest field type should be a dict or list
            if isinstance(field_type, Dict):
                if field_type.get("type") == "array":
                    field_type = field_type.get("items")
                    is_array = 1
            elif isinstance(field_type, List):
                if not len(field_type) == 1:
                    logger.warning(f"Don't know what to do with key {field_key}")
                    logger.warning(f"{field_dict}")
                field_type = field_dict.get("type")[0]
            else:
                new_fields[field_key] = field_dict
                continue

            # Field type / new field dict
            if not isinstance(field_type, Dict):
                logger.warning(f"Expected a dict to be left for {field_key}")
                logger.warning(f"Got {field_dict}")
                continue
                
            if len(field_type.keys()) > 1 and "$import" in field_type.keys():
                logger.warning(f"Unsure how to handle $import and additional keys for {field_key}")
                continue
            elif len(field_type.keys()) == 1 and "$import" in field_type.keys():
                logger.info("Importing from external schema")
                schema_import_path = field_type.get("$import")
                # Read schema from extenral paths
                relative_schema_file_path, schema_name = split_cwl_id_to_path_and_fragment(schema_import_path)
                relative_schema_file_path = Path(relative_schema_file_path)
                schema_version = re.sub(r"\.yaml$", "", relative_schema_file_path.name.rsplit("__", 1)[-1])
                imported_schema_obj = CWLSchema(
                    self.cwl_file_path.parent.joinpath(relative_schema_file_path).resolve(),
                    schema_name,
                    schema_version
                )
                new_fields[field_key] = imported_schema_obj.get_sanitised_object()
            else:
                new_fields[field_key] = field_dict
                new_fields[field_key]["type"] = field_type

            new_fields[field_key]["doc"] = field_dict.get("doc")
            new_fields[field_key]["is_array"] = is_array
            new_fields[field_key]["optional"] = optional

        new_cwl_obj["fields"] = new_fields

        return new_cwl_obj
