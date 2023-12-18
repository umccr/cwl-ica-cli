#!/usr/bin/env python3

"""
Functions for dockstore
"""
# External imports
import gzip
from typing import List
import json
import re
from ruamel.yaml import CommentedMap, YAML
from pathlib import Path

# Set classes
from ..classes.dockstore import Dockstore

# Utils
from .miscell import get_name_version_tuple_from_cwl_file_path
from .repo import get_cwl_ica_repo_path, get_workflows_dir, get_dockstore_dir


def get_dockstore_yaml_path() -> Path:
    """
    Get the dockstore yaml path
    :return:
    """
    return get_cwl_ica_repo_path() / ".dockstore.yml"


def read_dockstore_yaml() -> List[Dockstore]:
    yaml_obj = YAML()

    dockstore_yaml_path = get_dockstore_yaml_path()

    data = CommentedMap()
    if dockstore_yaml_path.is_file():
        with open(dockstore_yaml_path, 'r') as yaml_h:
            data: CommentedMap = yaml_obj.load(yaml_h)

    if data.get("workflows", None) is None:
        return []

    workflows = list(
        map(
            lambda workflow_dict: Dockstore.from_dict(workflow_dict),
            data.get("workflows")
        )
    )

    return workflows


def write_dockstore_yaml(workflows_list: List[Dockstore]):
    yaml_obj = YAML()

    # Set indentation
    yaml_obj.block_seq_indent = 2
    yaml_obj.sequence_indent = 4

    dockstore_yaml_path = get_dockstore_yaml_path()

    data = {
        "version": 1.2,
        "workflows": list(
            map(
                lambda workflow: workflow.to_dict(),
                workflows_list
            )
        )
    }

    with open(dockstore_yaml_path, 'w') as yaml_h:
        yaml_obj.dump(data, yaml_h)


def get_dockstore_path_from_workflow_path(workflow_path: Path) -> Path:
    name, version = get_name_version_tuple_from_cwl_file_path(workflow_path.absolute(), get_workflows_dir())

    return get_dockstore_dir() / name / version / f"{name}__{version}.packed.cwl.json"


def append_workflow_to_dockstore_yaml(workflow_path: Path, gzipped_packed_workflow_path: Path, tags: List[str]):
    """
    Append workflow to dockstore yaml.
    Write packed json to dockstore directory in GitHub for reference in dockstore yaml
    :return:
    """
    dockstore_obj_list = read_dockstore_yaml()
    dockstore_packed_output_path = get_dockstore_path_from_workflow_path(workflow_path)

    # Check first if we already have an entry for this workflow path
    try:
        dockstore_obj = next(
            filter(
                lambda dockstore_obj_iter_: dockstore_obj_iter_.cwl_file_path == workflow_path,
                dockstore_obj_list
            )
        )

        # Just add a tag then
        dockstore_obj.add_tags(tags)

        # Then replace the original element in the array that we extracted
        index_to_replace = -1
        for index, dockstore_obj_iter in enumerate(dockstore_obj_list):
            if dockstore_obj_iter.cwl_file_path == dockstore_obj.cwl_file_path:
                index_to_replace = index

        dockstore_obj_list[index_to_replace] = dockstore_obj

    # Otherwise, we need to create a new dockstore object
    except StopIteration:
        dockstore_obj = Dockstore(
            create=True,
            name=workflow_path_name_to_dockstore_name(workflow_path.name),
            cwl_file_path=workflow_path,
            subclass="CWL",
            primary_descriptor_path=dockstore_packed_output_path,
            tags=tags,
        )

        dockstore_obj_list.append(dockstore_obj)

    write_dockstore_yaml(dockstore_obj_list)

    write_packed_workflow_to_dockstore_dir(gzipped_packed_workflow_path, dockstore_packed_output_path)


def workflow_path_name_to_dockstore_name(workflow_path_name: str):
    """
    No dots allowed, or double hyphens / underscores
    :param workflow_path_name:
    :return:
    """
    name_with_no_periods = workflow_path_name.replace(".cwl", "").replace(".", "_")

    # Hyphens and underscores are restriced to a single character
    return re.sub(r"([_-])+", r"\1", name_with_no_periods)


def write_packed_workflow_to_dockstore_dir(gzipped_input_packed_workflow_path: Path, dockstore_packed_output_path: Path):
    """
    Take a gzipped packed workflow and dump in a different directory
    :param gzipped_input_packed_workflow_path:
    :param dockstore_packed_output_path:
    :return:
    """
    # Make sure parent of output directory exists
    dockstore_packed_output_path.parent.mkdir(parents=True, exist_ok=True)

    with gzip.open(gzipped_input_packed_workflow_path, "rb") as gzipped_pack_h, \
            open(dockstore_packed_output_path, "w") as pack_h:
        pack_h.write(json.dumps(json.loads(gzipped_pack_h.read().decode()), indent=2))
