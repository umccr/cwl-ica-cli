#!/usr/bin/env python3

"""
List of quick functions I have set up way too late!
Mostly done for icav2 work
"""

from classes.cwl_workflow import CWLWorkflow
from classes.cwl_tool import CWLTool
from classes.cwl_expression import CWLExpression
from cwl_utils.parser_v1_1 import Workflow, WorkflowStep
from typing import Optional, Dict, List
from pathlib import Path
from utils.miscell import get_items_dir_from_cwl_file_path
from utils.cwl_helper_utils import get_include_items
from utils.cwl_schema_helper_utils import get_schemas, add_additional_schemas_to_schema_list_recursively
from utils.miscell import get_name_version_tuple_from_cwl_file_path
from utils.repo import join_run_path_from_caller_path, get_cwl_ica_repo_path


def get_step_mappings(steps: List[WorkflowStep], workflow_path: Path) -> List[Dict]:
    # Initialise step mappings
    step_mappings = []

    # Iterate through steps and return steps
    for step in steps:
        step_mappings.append({
            "old": step.run,
            "new": str(
                join_run_path_from_caller_path(workflow_path, Path(step.run)).relative_to(get_cwl_ica_repo_path())
            )
        })

    return step_mappings


def collect_objects_recursively(cwl_item, workflow_items: Optional[Dict] = None) -> Dict:
    # Get workflow items
    if workflow_items is None:
        workflow_items = {
            "schemas": [],
            "tools": [],
            "expressions": [],
            "workflows": [],
            "typescript-expressions": []
        }
    include_items = []
    schema_items = []

    # Get cwl_obj
    cwl_obj = cwl_item.cwl_obj

    # Get ts-expressions and schemas of top level workflow
    schema_items.extend(get_schemas(cwl_item))
    include_items.extend(get_include_items(cwl_item))

    # Get step paths
    for step in cwl_obj.steps:
        step_run_path = join_run_path_from_caller_path(cwl_item.cwl_file_path, Path(step.run))
        step_items_dir = get_items_dir_from_cwl_file_path(step_run_path)
        step_name, step_version = get_name_version_tuple_from_cwl_file_path(step_run_path, step_items_dir)
        if step_items_dir.name == "workflows":
            workflow_items["workflows"].append(step_run_path)
            step_obj = CWLWorkflow(step_name, step_version, step_run_path, False)
            workflow_items = collect_objects_recursively(step_obj, workflow_items=workflow_items)
            include_items.extend(get_include_items(step_obj))
            schema_items.extend(get_schemas(step_obj))
        elif step_items_dir.name == "tools":
            workflow_items["tools"].append(step_run_path)
            step_obj = CWLTool(step_run_path, step_name, step_version, False)
            include_items.extend(get_include_items(step_obj))
            schema_items.extend(get_schemas(step_obj))
        elif step_items_dir.name == "expressions":
            workflow_items["expressions"].append(step_run_path)
            step_obj = CWLExpression(step_run_path, step_name, step_version, False)
            include_items.extend(get_include_items(step_obj))
            schema_items.extend(get_schemas(step_obj))

    # Update workflow items
    workflow_items["typescript-expressions"].extend(include_items)
    workflow_items["schemas"].extend(schema_items)

    # Filter down workflow items
    for cwl_type, file_list in workflow_items.items():
        workflow_items[cwl_type] = list(set(file_list))

    # Make sure the schemas import other schemas
    workflow_items["schemas"] = add_additional_schemas_to_schema_list_recursively(workflow_items["schemas"])

    return workflow_items


