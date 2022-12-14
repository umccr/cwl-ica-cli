#!/usr/bin/env python3

"""
List of quick functions I have set up way too late!
Mostly done for icav2 work
"""
import gzip
import json
import os
import shutil
from fileinput import FileInput
from tempfile import TemporaryDirectory
from urllib.parse import urlparse
from zipfile import ZIP_DEFLATED, ZipFile

from classes.cwl_workflow import CWLWorkflow
from classes.cwl_tool import CWLTool
from classes.cwl_expression import CWLExpression
from cwl_utils.parser.latest import \
    Workflow, WorkflowStep
from typing import Optional, Dict, List
from pathlib import Path

from utils.globals import ICAV2_MAX_STEP_CHARACTERS, ICAV2_COMPUTE_RESOURCE_MAPPINGS, ICAV2_CONTAINER_MAPPINGS, \
    ICAV2_DRAGEN_TEMPSPACE_MAPPINGS, MATCH_RUN_LINE_REGEX_OBJ, MATCH_SCHEMA_LINE_REGEX_OBJ
from utils.miscell import get_items_dir_from_cwl_file_path
from utils.cwl_helper_utils import get_include_items, get_fragment_from_cwl_id
from utils.cwl_schema_helper_utils import get_schemas, add_additional_schemas_to_schema_list_recursively, \
    get_schema_mappings
from utils.miscell import get_name_version_tuple_from_cwl_file_path
from utils.repo import join_run_path_from_caller_path, get_cwl_ica_repo_path, get_tools_dir, get_workflows_dir
from utils.logging import get_logger
from utils.subprocess_handler import run_subprocess_proc

logger = get_logger()


def get_step_mappings(steps: List[WorkflowStep], workflow_path: Path) -> List[Dict]:
    # Initialise step mappings
    step_mappings = []

    # Iterate through steps and return steps
    for step in steps:
        step_mappings.append({
            "step_name": str(
                Path(urlparse(step.run).path).name,
            ),
            "step_path": str(
                join_run_path_from_caller_path(
                    workflow_path, Path(urlparse(step.run).path)
                ).relative_to(get_cwl_ica_repo_path())
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
        step_run_path = join_run_path_from_caller_path(cwl_item.cwl_file_path, Path(urlparse(step.run).path))
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


def check_workflow_step_lengths(cwl_workflow: Workflow, cwl_file_path: Path):
    for step in cwl_workflow.steps:
        step_name = str(get_fragment_from_cwl_id(step.id).name)

        # Skip if step.run is not a tool
        try:
            get_name_version_tuple_from_cwl_file_path(cwl_file_path.absolute().parent.joinpath(Path(step.run)).absolute().resolve(), get_tools_dir())
        except ValueError:
            continue

        if len(step_name) > ICAV2_MAX_STEP_CHARACTERS:
            logger.warning(
                f"Step name '{step_name}' is greater than {ICAV2_MAX_STEP_CHARACTERS} characters"
            )


def zip_workflow(cwl_obj: CWLWorkflow, output_zip_path: Path):
    # Collect all the workflow objects
    all_workflow_objects = collect_objects_recursively(cwl_obj)

    # Create a temporary directory
    output_tempdir_obj = TemporaryDirectory()
    output_tempdir = Path(output_tempdir_obj.name) / output_zip_path.stem

    # And we want to make sure it doesn't already exist
    output_tempdir.mkdir(exist_ok=False)
    logger.info(f"Transferring files over into {output_tempdir}")

    # Copy over the workflow objects
    for cwl_item, cwl_file_list in all_workflow_objects.items():

        # Get the cwl file list
        for cwl_file in cwl_file_list:
            # Get the new path
            new_path = output_tempdir.joinpath(cwl_file.relative_to(get_cwl_ica_repo_path()))

            # Create a directory for this file
            new_path.parent.mkdir(parents=True, exist_ok=False)

            # And copy over contents of the file
            shutil.copy2(cwl_file, new_path)

    # Copy over the main workflow
    new_workflow_path = output_tempdir / "workflow.cwl"
    shutil.copy2(cwl_obj.cwl_file_path, new_workflow_path)

    # Edit the main workflow
    step_mappings = get_step_mappings(cwl_obj.cwl_obj.steps, cwl_obj.cwl_file_path)
    schema_mappings = get_schema_mappings(get_schemas(cwl_obj), cwl_obj.cwl_file_path)

    with FileInput(new_workflow_path, inplace=True) as _input:
        for line in _input:
            line_strip = line.rstrip()
            for step_mapping in step_mappings:
                line_match_run = MATCH_RUN_LINE_REGEX_OBJ.match(line_strip.lstrip())
                if line_match_run is not None and line_match_run.group(2) == step_mapping.get("step_name"):
                    line_strip = line_strip.replace(
                        line_strip.lstrip(),
                        f"run: {step_mapping.get('step_path')}"
                    )
            for schema_mapping in schema_mappings:
                line_match_schema = MATCH_SCHEMA_LINE_REGEX_OBJ.match(line_strip.lstrip())
                if line_match_schema is not None and urlparse(line_match_schema.group(4)).path == schema_mapping.get("schema_name"):
                    line_strip = line_strip.replace(
                        urlparse(line_match_schema.group(2)).path,
                        str(schema_mapping.get('schema_path'))
                    )
            print(line_strip)

    # Iterate through all paths and make sure we convert resource requirements?
    for path_item in output_tempdir.rglob("*"):
        # Don't need to deal with directories
        if not path_item.is_file():
            continue

        with FileInput(path_item, inplace=True) as _input:
            for line in _input:
                # Strip line then reprint it
                # Which also conveniently converts any windows line endings into standard unix line endings
                line_strip = line.rstrip()

                # Deal with https://github.com/umccr-illumina/ica_v2/issues/108
                for resource_mapping in ICAV2_COMPUTE_RESOURCE_MAPPINGS:
                    if resource_mapping.get("v1") in line_strip:
                        line_strip = line_strip.replace(
                            resource_mapping.get("v1"),
                            resource_mapping.get("v2")
                        )

                # Deal with https://github.com/umccr-illumina/dragen/issues/48
                for container_mapping in ICAV2_CONTAINER_MAPPINGS:
                    if container_mapping.get("v1") in line_strip:
                        line_strip = line_strip.replace(
                            container_mapping.get("v1"),
                            container_mapping.get("v2")
                        )

                # Deal with https://github.com/umccr-illumina/ica_v2/issues/21
                # / also related https://github.com/umccr-illumina/ica_v2/issues/47
                if path_item.suffix == ".cwljs":
                    if ICAV2_DRAGEN_TEMPSPACE_MAPPINGS.get("v1") in line_strip:
                        line_strip = line_strip.replace(
                            ICAV2_DRAGEN_TEMPSPACE_MAPPINGS.get("v1"),
                            ICAV2_DRAGEN_TEMPSPACE_MAPPINGS.get("v2")
                        )

                # Print line back to file
                print(line_strip)

    # Find steps in workflow.cwl and workflows/ (subworkflows)
    logger.info("Finding steps names with lengths greater than 23 characters")
    workflow_list = []
    workflow_dir = Path(output_tempdir / "workflows")
    if workflow_dir.is_dir():
        for path_item in workflow_dir.rglob("*"):
            if path_item.is_file() and path_item.suffix == ".cwl":
                workflow_list.append(path_item)
    for workflow_item in workflow_list:
        cwl_repo_workflow_path = Path(get_cwl_ica_repo_path()) / workflow_item.relative_to(output_tempdir)
        workflow_name, workflow_version = get_name_version_tuple_from_cwl_file_path(cwl_repo_workflow_path, get_workflows_dir())
        workflow_object = CWLWorkflow(workflow_name, workflow_version, cwl_repo_workflow_path)
        check_workflow_step_lengths(workflow_object.cwl_obj, cwl_obj.cwl_file_path)

    # Revalidate directory with cwltool --validate
    logger.info("Now all files have been transferred, confirming successful 'zip' with cwltool --validate")
    proc_returncode, proc_stdout, proc_stderr = run_subprocess_proc(
        [
            "cwltool", "--validate", str(output_tempdir / "workflow.cwl")
        ],
        cwd=str(output_tempdir),
        capture_output=True
    )

    if not proc_returncode == 0:
        logger.error(f"cwltool --validate resulted in an error after 'zipping' of workflow "
                     f"please run cwltool --debug --validate {str(output_tempdir / 'workflow.cwl')} to investigate further"
                     f"leaving {str(output_tempdir)} as is")
        raise ChildProcessError

    # Check zip file doesn't exist
    if output_zip_path.is_file():
        os.remove(output_zip_path)

    # Create the zipped directory
    with ZipFile(output_zip_path, "w", ZIP_DEFLATED) as zip_file:
        for entry in output_tempdir.rglob("*"):
            zip_file.write(entry, Path(output_tempdir.name) / Path(entry.relative_to(output_tempdir)))

    # Remove the directory
    shutil.rmtree(output_tempdir)


def create_packed_workflow_from_zipped_workflow_path(zipped_path: Path, output_path: Path):
    """
    From a zipped workflow, extract into a temp dir and create a packed json through cwltool --pack,
    :return:
    """

    if not output_path.parent.is_dir():
        logger.error(f"Could not write to {output_path}, parent directory does not exist")
        raise NotADirectoryError

    with gzip.open(output_path, "wb") as pack_h, \
        TemporaryDirectory() as unzip_tmpdir, \
        ZipFile(zipped_path, "r") as workflow_zip:
        # Unzip workflow to tmp dir
        workflow_zip.extractall(unzip_tmpdir)
        extracted_main_workflow_path = Path(unzip_tmpdir) / zipped_path.stem / "workflow.cwl"
        # Pack workflow
        pack_returncode, pack_stdout, pack_stderr = run_subprocess_proc(
            [
                "cwltool", "--pack", extracted_main_workflow_path
            ],
            capture_output=True
        )

        pack_h.write(bytes(json.dumps(pack_stdout).encode()))
