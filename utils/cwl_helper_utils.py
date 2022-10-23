#!/usr/bin/env python3

"""
Again CWL helpers that have been WET Types all over the shop.
"""

from typing import List, Dict
from pathlib import Path
from classes.cwl import CWL

from utils.repo import join_run_path_from_caller_path


def get_include_items(cwl_item: CWL) -> List[Path]:
    cwl_obj = cwl_item.cwl_obj
    include_items = []
    # Check if there are include items
    loading_options = cwl_obj.loadingOptions.idx[cwl_obj.loadingOptions.fileuri]
    requirements = loading_options.get("requirements", None)

    # Check there are requirements
    if requirements is None:
        return []

    # Check inline javascript is a requirement
    inline_javascript_requirement = requirements.get("InlineJavascriptRequirement", None)
    if inline_javascript_requirement is None:
        return []

    # Check we have an expression lib, and it is a list
    expression_lib = inline_javascript_requirement.get("expressionLib", None)
    if expression_lib is None or not isinstance(expression_lib, List):
        return []

    # Iterate through list, only want includes
    for lib_item in expression_lib:

        # Must be a dict
        if not isinstance(lib_item, Dict):
            continue

        # Iterate through dict
        # Look for keys that equal $include
        # And return value of that key
        for key, value in lib_item.items():
            if key == "$include":
                value_path: Path = Path(value)
                include_items.append(join_run_path_from_caller_path(cwl_item.cwl_file_path, value_path))

    return include_items
