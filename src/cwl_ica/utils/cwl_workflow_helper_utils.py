#!/usr/bin/env python3

"""
List of quick functions I have set up way too late!
Mostly done for icav2 work
"""

# External imports
import gzip
import json
import os
import shutil
from fileinput import FileInput
from tempfile import TemporaryDirectory
from urllib.parse import urlparse
from zipfile import ZIP_DEFLATED, ZipFile
from typing import Optional, Dict, List, Union
from pathlib import Path

# CWL Utils
from cwl_utils.parser import load_document_by_uri, CommandLineTool
from cwl_utils.parser.latest import \
    Workflow, WorkflowStep, ExpressionTool

# Locals
from .globals import (
    ICAV2_MAX_STEP_CHARACTERS, ICAV2_COMPUTE_RESOURCE_TYPE_MAPPINGS, ICAV2_CONTAINER_MAPPINGS,
    ICAV2_DRAGEN_TEMPSPACE_MAPPINGS, MATCH_RUN_LINE_REGEX_OBJ, MATCH_SCHEMA_LINE_REGEX_OBJ,
    ICAV2_COMPUTE_RESOURCE_STANDARD_SIZE_MAPPINGS, MATCH_INCLUDE_LINE_REGEX_OBJ
)
from .miscell import get_items_dir_from_cwl_file_path
from .cwl_helper_utils import get_include_items, get_fragment_from_cwl_id, get_path_from_cwl_id
from .cwl_schema_helper_utils import (
    get_schemas, add_additional_schemas_to_schema_list_recursively,
    get_schema_mappings
)
from .cwl_utils_typing_helpers import ResourceRequirementType, DockerRequirementType
from .miscell import get_name_version_tuple_from_cwl_file_path
from .repo import join_run_path_from_caller_path, get_cwl_ica_repo_path, get_tools_dir
from .logging import get_logger
from .subprocess_handler import run_subprocess_proc

# Classes
from ..classes.cwl_workflow import CWLWorkflow
from ..classes.cwl_tool import CWLTool
from ..classes.cwl_expression import CWLExpression

# Set logger
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


def collect_locations_from_secondary_file_print_deps_recursively(
        secondary_file_print_deps: Dict,
        cwl_path: Path
) -> List[Path]:
    """
    Used to collect secondary files recursively
    :param secondary_file_print_deps:
    {
    "class": "File",
    "location": "bclconvert-with-qc-pipeline__4.0.3.cwl",
    "format": "https://www.iana.org/assignments/media-types/application/cwl",
    "secondaryFiles": [
        {
            "class": "File",
            "location": "https://schema.org/version/latest/schemaorg-current-http.rdf",
            "basename": "schemaorg-current-http.rdf",
            "nameroot": "schemaorg-current-http",
            "nameext": ".rdf"
        },
        {
            "class": "File",
            "location": "../../../schemas/bclconvert-run-configuration/2.0.0--4.0.3/bclconvert-run-configuration__2.0.0--4.0.3.yaml",
            "format": "https://www.iana.org/assignments/media-types/application/cwl",
            "secondaryFiles": [
                {
                    "class": "File",
                    "location": "../../../schemas/samplesheet/2.0.0--4.0.3/samplesheet__2.0.0--4.0.3.yaml#samplesheet",
                    "format": "https://www.iana.org/assignments/media-types/application/cwl",
                    "secondaryFiles": [
                      ....
    :param cwl_path
    :return: Array
      [
        "../../../schemas/bclconvert-run-configuration/2.0.0--4.0.3/bclconvert-run-configuration__2.0.0--4.0.3.yaml"
        ...
      ]
    """

    location_list: List = []

    if "location" in secondary_file_print_deps.keys():
        file_location = secondary_file_print_deps["location"]
        if file_location.startswith("https:"):
            pass
        elif Path(file_location).name == cwl_path.name:
            pass
        else:
            location_list.append(
                cwl_path.parent.joinpath(
                    get_path_from_cwl_id(secondary_file_print_deps["location"])
                ).absolute()
            )

    if "secondaryFiles" in secondary_file_print_deps.keys():
        for secondary_file_print_dep in secondary_file_print_deps["secondaryFiles"]:
            location_list.extend(
                collect_locations_from_secondary_file_print_deps_recursively(secondary_file_print_dep, cwl_path)
            )

    # May end up with some duplicates
    location_list = list(set(location_list))

    return location_list


def collect_objects_by_print_deps(cwl_path: Path) -> List:
    """
    Supersedes collect objects recursively
    :param cwl_path:
    :return:
    """

    returncode, stdout, stderr = run_subprocess_proc(
        [
            "cwltool", "--no-doc-cache", "--print-deps", str(cwl_path)
        ],
        capture_output=True
    )

    deps_as_dict: Dict = json.loads(stdout)

    dep_locations = collect_locations_from_secondary_file_print_deps_recursively(
        deps_as_dict,
        cwl_path
    )

    return dep_locations


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
            get_name_version_tuple_from_cwl_file_path(
                cwl_file_path.absolute().parent.joinpath(Path(step.run)).absolute().resolve(),
                get_tools_dir()
            )
        except ValueError:
            continue

        if len(step_name) > ICAV2_MAX_STEP_CHARACTERS:
            logger.warning(
                f"Step name '{step_name}' is greater than {ICAV2_MAX_STEP_CHARACTERS} characters"
            )


def zip_workflow(cwl_obj: CWLWorkflow, output_zip_path: Path):
    # Collect all the workflow objects
    all_workflow_paths = collect_objects_by_print_deps(cwl_obj.cwl_file_path)

    # Create a temporary directory
    output_tempdir_obj = TemporaryDirectory()
    output_tempdir = Path(output_tempdir_obj.name) / output_zip_path.stem

    # And we want to make sure it doesn't already exist
    output_tempdir.mkdir(exist_ok=False)
    logger.info(f"Transferring files over into {output_tempdir}")

    # Copy over the workflow objects
    for cwl_path in all_workflow_paths:

        # Get the new path
        new_path = output_tempdir.joinpath(cwl_path.absolute().resolve().relative_to(get_cwl_ica_repo_path()))

        # Create a directory for this file
        new_path.parent.mkdir(parents=True, exist_ok=False)

        # And copy over contents of the file
        shutil.copy2(cwl_path, new_path)

    # Copy over the main workflow
    new_workflow_path = output_tempdir / "workflow.cwl"
    shutil.copy2(cwl_obj.cwl_file_path, new_workflow_path)

    # Edit the main workflow
    step_mappings = get_step_mappings(cwl_obj.cwl_obj.steps, cwl_obj.cwl_file_path)
    schema_mappings = get_schema_mappings(get_schemas(cwl_obj), cwl_obj.cwl_file_path)
    include_mappings = list(
        map(
            lambda x: os.path.relpath(x, cwl_obj.cwl_file_path.parent),
            filter(
                lambda x: x.name.endswith(".cwljs"),
                all_workflow_paths
            )
        )
    )

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
                if (
                    line_match_schema is not None and
                    urlparse(line_match_schema.group(4)).path == schema_mapping.get("schema_name")
                ):
                    line_strip = line_strip.replace(
                        urlparse(line_match_schema.group(2)).path,
                        str(schema_mapping.get('schema_path'))
                    )
            for include_mapping in include_mappings:
                line_match_include = MATCH_INCLUDE_LINE_REGEX_OBJ.match(line_strip.lstrip())
                if line_match_include is not None and urlparse(line_match_include.group(1)).path == include_mapping:
                    line_strip = line_strip.replace(
                        urlparse(line_match_include.group(1)).path,
                        os.path.relpath(
                            (Path(cwl_obj.cwl_file_path.parent) / include_mapping).resolve(),
                            get_cwl_ica_repo_path()
                        )
                    )
            print(line_strip)

    # Iterate through all paths and make sure we convert resource requirements?
    for path_item in output_tempdir.rglob("*"):
        # Don't need to deal with directories
        if not path_item.is_file():
            continue

        # Load file as cwl object
        path_item_cwl_obj: Optional[Union[CommandLineTool | Workflow | ExpressionTool]]
        if path_item.suffix == ".cwl":
            path_item_cwl_obj: Union[CommandLineTool | Workflow | ExpressionTool] = load_document_by_uri(path_item)
        else:
            path_item_cwl_obj = None

        with FileInput(path_item, inplace=True) as _input:
            for line in _input:
                # Strip line then reprint it
                # Which also conveniently converts any windows line endings into standard unix line endings
                line_strip = line.rstrip()

                if path_item_cwl_obj is not None:
                    # Deal with https://github.com/umccr-illumina/ica_v2/issues/128
                    for resource_mapping in ICAV2_COMPUTE_RESOURCE_STANDARD_SIZE_MAPPINGS:
                        if path_item_cwl_obj.hints is None:
                            continue
                        for hint in path_item_cwl_obj.hints:
                            if (
                                isinstance(hint, ResourceRequirementType) and
                                hint.extension_fields is not None and
                                "https://platform.illumina.com/rdf/ica/resources/type" in hint.extension_fields.keys() and
                                hint.extension_fields.get("https://platform.illumina.com/rdf/ica/resources/type") == "standard" and
                                resource_mapping.get("v1") in line_strip
                            ):
                                line_strip = line_strip.replace(
                                    resource_mapping.get("v1"),
                                    resource_mapping.get("v2")
                                )
                    # Deal with https://github.com/umccr-illumina/ica_v2/issues/108
                    for resource_mapping in ICAV2_COMPUTE_RESOURCE_TYPE_MAPPINGS:
                        if path_item_cwl_obj.hints is None:
                            continue
                        for hint in path_item_cwl_obj.hints:
                            if (
                                isinstance(hint, ResourceRequirementType) and
                                hint.extension_fields is not None and
                                "https://platform.illumina.com/rdf/ica/resources/type" in hint.extension_fields.keys() and
                                hint.extension_fields.get("https://platform.illumina.com/rdf/ica/resources/type") == resource_mapping.get("v1") and
                                resource_mapping.get("v1") in line_strip
                            ):
                                line_strip = line_strip.replace(
                                    resource_mapping.get("v1"),
                                    resource_mapping.get("v2")
                                )
                    # Deal with https://github.com/umccr-illumina/ica_v2/issues/130
                    if path_item_cwl_obj.hints is not None:
                        for hint in path_item_cwl_obj.hints:
                            if (
                                isinstance(hint, ResourceRequirementType) and
                                hint.extension_fields is not None and
                                len(
                                    list(
                                        filter(
                                            lambda key: key.startswith("https://platform.illumina.com/rdf/ica/resources/"),
                                            hint.extension_fields.keys()
                                        )
                                    )
                                ) > 0
                            ):
                                line_strip = line_strip.replace(
                                    "ilmn-tes:resources/",
                                    "ilmn-tes:resources:"
                                )

                    # Deal with https://github.com/umccr-illumina/dragen/issues/48
                    for container_mapping in ICAV2_CONTAINER_MAPPINGS:
                        if path_item_cwl_obj.hints is None:
                            continue
                        for hint in path_item_cwl_obj.hints:
                            if isinstance(hint, DockerRequirementType) and \
                                    hint.dockerPull == container_mapping.get("v1"):
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

    # Revalidate directory with cwltool --validate
    logger.info("Now all files have been transferred, confirming successful 'zip' with cwltool --validate")
    proc_returncode, proc_stdout, proc_stderr = run_subprocess_proc(
        [
            "cwltool", "--no-doc-cache", "--validate", str(output_tempdir / "workflow.cwl")
        ],
        cwd=str(output_tempdir),
        capture_output=True
    )

    if not proc_returncode == 0:
        logger.error(f"cwltool --validate resulted in an error after 'zipping' of workflow "
                     f"please run cwltool --debug --validate {str(output_tempdir / 'workflow.cwl')} "
                     f"to investigate further, leaving {str(output_tempdir)} as is")
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

    with (
        gzip.open(output_path, "wb") as pack_h,
        TemporaryDirectory() as unzip_tmpdir,
        ZipFile(zipped_path, "r") as workflow_zip
    ):
        # Unzip workflow to tmp dir
        workflow_zip.extractall(unzip_tmpdir)
        extracted_main_workflow_path = Path(unzip_tmpdir) / zipped_path.stem / "workflow.cwl"
        # Pack workflow
        pack_returncode, pack_stdout, pack_stderr = run_subprocess_proc(
            [
                "cwltool", "--no-doc-cache", "--pack", extracted_main_workflow_path
            ],
            capture_output=True
        )

        pack_h.write(bytes((json.dumps(json.loads(pack_stdout), indent=2, ensure_ascii=False) + "\n").encode()))


def create_cwl_inputs_schema_gen(zipped_path: Path, output_path: Path):
    if not output_path.parent.is_dir():
        logger.error(f"Could not write to {output_path}, parent directory does not exist")
        raise NotADirectoryError

    with (
        gzip.open(output_path, "wb") as json_schema_h,
        TemporaryDirectory() as unzip_tmpdir,
        ZipFile(zipped_path, "r") as workflow_zip
    ):
        # Unzip workflow to tmp dir
        workflow_zip.extractall(unzip_tmpdir)
        extracted_main_workflow_path = Path(unzip_tmpdir) / zipped_path.stem / "workflow.cwl"
        # Pack workflow
        json_schema_gen_returncode, json_schema_gen_stdout, json_schema_gen_stderr = run_subprocess_proc(
            [
                "cwl-inputs-schema-gen", f"file://{extracted_main_workflow_path}"
            ],
            capture_output=True
        )

        json_schema_h.write(
            bytes(
                (json.dumps(json.loads(json_schema_gen_stdout), indent=2, ensure_ascii=False) + "\n").encode()
            )
        )
