#!/usr/bin/env python3

"""
Given a path to a workflow, create a zip of the workflow ready for deployment to icav2

This involves:

1. Collecting all files related to the workflow (non-trivial step).

1a. Remove any references to hiCpu or hiMem and replace with hicpu or himem respectively

2. Confirm no file is not git-stashed, so we can use the previous commit id in the pipeline reference :construction:

3. Add in a blank params xml step (will be updated once https://jira.illumina.com/browse/SET-3410 is resolved)

4. Create a html document (from cwl auto-generated markdown)  :construction: to add to v2 upload
"""
import os
import shutil
from fileinput import FileInput
from zipfile import ZipFile, ZIP_DEFLATED

from classes.command import Command
from utils.logging import get_logger
from pathlib import Path
from argparse import ArgumentError
from utils.globals import \
    ICAV2_COMPUTE_RESOURCE_TYPE_MAPPINGS, \
    ICAV2_CONTAINER_MAPPINGS, \
    ICAV2_DRAGEN_TEMPSPACE_MAPPINGS, \
    PARAMS_XML_FILE_NAME, \
    BLANK_PARAMS_XML_V2_FILE_CONTENTS
from utils.errors import CheckArgumentError
from typing import Optional, List, Dict
from classes.cwl_workflow import CWLWorkflow
from utils.repo import get_workflows_dir, get_cwl_ica_repo_path
from utils.miscell import get_name_version_tuple_from_cwl_file_path
from utils.cwl_workflow_helper_utils import get_step_mappings, collect_objects_recursively, check_workflow_step_lengths
from utils.cwl_schema_helper_utils import get_schemas
from utils.cwl_schema_helper_utils import get_schema_mappings
from utils.subprocess_handler import run_subprocess_proc

logger = get_logger()

# FIXME - harmonize with build-workflow-release-assets commands and undeprecate


class ZipV2Workflow(Command):
    """Usage:
    cwl-ica [options] icav2-zip-workflow help
    cwl-ica [options] icav2-zip-workflow (--workflow-path=<workflow_path>)
                                         [--output-path=<output_dir_path>]
                                         [--force]

Description:
    Create a zip file containing a workflow and all relevant input files to the workflow.

Options:
    --workflow-path=<workflow path>    Required, path to workflow
    --output-path=<output_dir_path>    Optional, set the output path, otherwise just the working directory
    --force                            Optional, override existing zip file if one already exists

Example:
    cwl-ica icav2-zip-workflow --workflow-path workflows/bclconvert-with-qc-pipeline/4.0.3/bclconvert-with-qc-pipeline__4.0.3.cwl
    """

    def __init__(self, command_argv):
        logger.warning(
            "The cwl-ica icav2-zip-workflow subcommand has been deprecated, "
            "Please tag the workflow and push to github to build the workflow as a release asset. "
            "You can then use the icav2 projectpipelines create-cwl-workflow* subcommands "
            "from the https://github.com/umccr/icav2-cli-plugins repository to import the pipeline."
        )
        # Collect args from doc strings
        super(ZipV2Workflow, self).__init__(command_argv)

        # Initialise parameters
        self.cwl_file_path: Optional[Path] = None
        self.name: Optional[str] = None
        self.version: Optional[str] = None
        self.cwl_workflow_obj: Optional[CWLWorkflow] = None
        self.force: Optional[bool] = None
        self.output_dir_path: Optional[Path] = None
        self.output_zip_file: Optional[Path] = None

        # Check if help has been called
        if self.args["help"]:
            self._help()

        # Confirm 'required' arguments are present and valid
        try:
            logger.debug("Checking args")
            self.check_args()
        except ArgumentError:
            self._help(fail=True)

        # Pull in workflow
        self.cwl_workflow_obj = CWLWorkflow(
            self.name,
            self.version,
            self.cwl_file_path
        )

    def check_args(self):
        # Check defined and assign properties
        workflow_path_arg = self.args.get("--workflow-path", None)
        if workflow_path_arg is None:
            logger.error("--workflow-path not defined")
            raise CheckArgumentError
        self.cwl_file_path = Path(workflow_path_arg)

        # Set name and version
        self.name, self.version = get_name_version_tuple_from_cwl_file_path(
            self.cwl_file_path,
            get_workflows_dir()
        )

        # Check args
        if not self.cwl_file_path.is_file():
            logger.error(f"Could not find the file {self.cwl_file_path}")
            raise CheckArgumentError

        # Check if force specified
        if self.args.get("--force", False):
            self.force = True
        else:
            self.force = False

        # Check if output_dir_path is set
        if self.args.get("--output-path", None) is not None:
            self.output_dir_path = Path(self.args.get("--output-path")).absolute().resolve()
            if not self.output_dir_path.is_dir():
                logger.error(f"Expected --output-path set as {self.output_dir_path}, is expected to exist")
                raise CheckArgumentError
        else:
            self.output_dir_path = Path(os.getcwd()).absolute().resolve()

        self.output_zip_file = self.output_dir_path / f"{self.name}__{self.version}.zip"

        if self.output_zip_file.is_file() and not self.force:
            logger.error(f"Output file {self.output_zip_file} "
                         f"exists and --force is not set. "
                         f"Please specify --force to overwrite zip file")
            raise CheckArgumentError
        elif self.output_zip_file.is_file() and self.force:
            logger.info(f"Output file {self.output_zip_file} currently exists and will be overwritten")

    def __call__(self):
        logger.info("Validating workflow before copying over files")
        self.cwl_workflow_obj.validate_object()

        logger.info("Ensuring workflow does not have steps with names greater than 21 characters")
        check_workflow_step_lengths(self.cwl_workflow_obj.cwl_obj, self.cwl_file_path)

        logger.info("Zipping up workflow")
        self.zip_workflow()

    def get_step_mappings(self) -> List[Dict]:
        return get_step_mappings(self.cwl_workflow_obj.cwl_obj.steps, self.cwl_file_path)

    def get_schemas(self) -> List[Path]:
        return get_schemas(self.cwl_workflow_obj)

    def get_schema_mappings(self) -> List[Dict]:
        return get_schema_mappings(self.get_schemas(), self.cwl_file_path)

    def zip_workflow(self):
        # Collect all the workflow objects
        all_workflow_objects = collect_objects_recursively(self.cwl_workflow_obj)

        # Create a temporary directory
        output_tempdir = self.output_dir_path / self.output_zip_file.stem

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
        shutil.copy2(self.cwl_file_path, new_workflow_path)

        # Edit the main workflow
        with FileInput(new_workflow_path, inplace=True) as _input:
            for line in _input:
                line_strip = line.rstrip()
                for step_mapping in self.get_step_mappings():
                    if step_mapping.get("old") in line_strip:
                        line_strip = line_strip.replace(step_mapping.get("old"), step_mapping.get("new"))
                for schema_mapping in self.get_schema_mappings():
                    if schema_mapping.get("old") in line_strip:
                        line_strip = line_strip.replace(schema_mapping.get("old"), schema_mapping.get("new"))
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
                    for resource_mapping in ICAV2_COMPUTE_RESOURCE_TYPE_MAPPINGS:
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

        # Place the blank params xml in the output temp directory
        with open(output_tempdir / PARAMS_XML_FILE_NAME, "w") as params_h:
            for line in BLANK_PARAMS_XML_V2_FILE_CONTENTS:
                params_h.write(line + "\n")

        # Check zip file doesn't exist
        if self.output_zip_file.is_file():
            os.remove(self.output_zip_file)

        # Create the zipped directory
        with ZipFile(self.output_zip_file, "w", ZIP_DEFLATED) as zip_file:
            for entry in output_tempdir.rglob("*"):
                zip_file.write(entry, Path(output_tempdir.name) / Path(entry.relative_to(output_tempdir)))

        # Remove the directory
        shutil.rmtree(output_tempdir)
