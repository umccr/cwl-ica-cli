#!/usr/bin/env python3

"""
Improves consistency when reading / writing yamls
https://stackoverflow.com/questions/51103498/using-ruamel-yaml-to-keep-multiline-strings-with-same-indentation-python
"""


from ruamel.yaml import YAML
from ruamel.yaml.scalarstring import PreservedScalarString
import textwrap


def to_multiline_string(s, width=60):
    return PreservedScalarString('\n'.join(textwrap.wrap(s, width=width))+"\n")


def dump_yaml(data_object, file_handler):
    """
    Uses round_trip_dump
    :param data_object:
    :param file_handler:
    :return:
    """
    yaml = YAML()
    yaml.indent = 4
    yaml.block_seq_indent = 2
    yaml.dump(data_object, file_handler)


def dump_cwl_yaml(data_object, file_handler):
    """
    Dump
    :param data_object:
    :param file_handler:
    :return:
    """

    yaml_obj = YAML()

    yaml_dict = yaml_obj.map(**data_object)

    extensions = False
    metadata = False
    docs = False
    hints = False

    for idx, key in enumerate(data_object.keys()):
        if idx < 2:
            # cwlVersion / class or type/name in schema -> Move on
            continue
        elif key.startswith("$") and not extensions:
            # Start of extensions section
            yaml_dict.yaml_set_comment_before_after_key(key, before="\nExtensions")
            extensions = True
        elif key.startswith("$") and extensions:
            # Extensions should all be bundled together
            continue
        elif key.startswith("s:") and not metadata:
            # Start of metadata section
            yaml_dict.yaml_set_comment_before_after_key(key, before="\nMetadata")
            metadata = True
        elif key.startswith("s:") and metadata:
            # Metadata should be all bundled together
            continue
        elif key in ["id", "label", "doc"] and not docs:
            # Start of docs section
            yaml_dict.yaml_set_comment_before_after_key(key, before="\nID/Docs")
            docs = True
        elif key in ["id", "label", "doc"] and docs:
            # docs should be all bundled together
            continue
        # cwltool specific
        elif data_object["class"] == "CommandLineTool" and key in ["hints", "requirements"] and not hints:
            yaml_dict.yaml_set_comment_before_after_key(
                key,
                before="\n"
                       "ILMN V1 Resources Guide: https://illumina.gitbook.io/ica-v1/analysis/a-taskexecution#type-and-size\n"
                       "ILMN V2 Resources Guide: https://help.ica.illumina.com/project/p-flow/f-pipelines#compute-types\n"
            )
            hints = True
        elif data_object["class"] == "CommandLineTool" and key in ["hints", "requirements"] and hints:
            # hints requirements should be all bundled together
            continue
        else:
            yaml_dict.yaml_set_comment_before_after_key(key, before="\n")

    dump_yaml(yaml_dict, file_handler)
