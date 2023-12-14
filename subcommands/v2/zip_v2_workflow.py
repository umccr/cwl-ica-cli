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

from classes.command import Command
from utils.logging import get_logger
from pathlib import Path
from argparse import ArgumentError
from utils.errors import CheckArgumentError
from typing import Optional, List, Dict
from classes.cwl_workflow import CWLWorkflow
from utils.repo import get_workflows_dir
from utils.miscell import get_name_version_tuple_from_cwl_file_path
from utils.cwl_workflow_helper_utils import get_step_mappings, check_workflow_step_lengths, \
    zip_workflow
from utils.cwl_schema_helper_utils import get_schemas
from utils.cwl_schema_helper_utils import get_schema_mappings

logger = get_logger()

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
        """
        Create a zipped workflow object from the cwl object
        :return:
        """
        zip_workflow(self.cwl_workflow_obj, self.output_zip_file)
