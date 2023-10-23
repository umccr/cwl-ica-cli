#!/usr/bin/env python3

"""
Deploy a zipped workflow to icav2

Provide a default storage size and a project-name / project id and you're done!

Return a pipeline ID

"""

import os
from utils.icav2_helpers import get_project_id_from_project_name, \
    get_icav2_configuration, is_project_id_format, \
    get_analysis_storage_id_from_analysis_storage_size, create_workflow_from_zip_path

from classes.command import Command
from utils.logging import get_logger
from pathlib import Path
from argparse import ArgumentError
from utils.globals import ICAv2AnalysisStorageSize, ICAV2_DEFAULT_ANALYSIS_STORAGE_SIZE
from utils.errors import CheckArgumentError
from typing import Optional

logger = get_logger()


# FIXME - deprecate this command, use icav2 projectpipeline create-cwl-workflow-from-zip instead

class DeployV2Workflow(Command):
    """Usage:
    cwl-ica [options] icav2-deploy-pipeline help
    cwl-ica [options] icav2-deploy-pipeline (--zipped-workflow-path=<zipped-workflow-path>)
                                            (--project-name=<project_name> | --project-id=<project_id>)
                                            [--analysis-storage-id=<analysis_storage_id> | --analysis-storage-size=<analysis_storage_size>]

Description:
    From a zip file, deploy a workflow to icav2

Options:
    --zipped-workflow-path=<workflow path>           Required, path to zipped up workflow
    --project-id=<project_id>                        Optional, provide the project id (takes precedence over --project-name)
    --project-name=<project_name>                    Optional, provide the project name
    --analysis-storage-id=<analysis_storage_id>      Optional, takes precedence over analysis-storage-size
    --analysis-storage-size=<analysis_storage_size>  Optional, default is set to Small

Environment:
    ICAV2_ACCESS_TOKEN

Example:
    cwl-ica icav2-deploy-pipeline --zipped-workflow-path bclconvert-with-qc-pipeline__4.0.3.zip --project-name playground_v2
    """

    def __init__(self, command_argv):

        # Collect args from doc strings
        super(DeployV2Workflow, self).__init__(command_argv)

        # Initialise parameters
        self.zipped_workflow_path: Optional[Path] = None
        self.project_id: Optional[str] = None
        self.project_name: Optional[str] = None
        self.analysis_storage_size: Optional[ICAv2AnalysisStorageSize] = None
        self.analysis_storage_id: Optional[str] = None
        self.code: Optional[str] = None
        self.pipeline_id: Optional[str] = None

        # Check if help has been called
        if self.args["help"]:
            self._help()

        # Confirm 'required' arguments are present and valid
        try:
            logger.debug("Checking args")
            self.check_args()
        except ArgumentError:
            self._help(fail=True)

    def check_args(self):
        logger.warning(
            "The cwl-ica icav2-deploy-pipeline subcommand has been deprecated, "
            "please checkout the icav2 projectpipelines create-cwl-workflow* subcommands "
            "from the https://github.com/umccr/icav2-cli-plugins repository"
        )
        # Confirm zipped_workflow_path is set and is a file
        zipped_workflow_path_arg = self.args.get("--zipped-workflow-path", None)
        if zipped_workflow_path_arg is None:
            logger.error("--zipped-workflow-path not defined")
            raise CheckArgumentError
        self.zipped_workflow_path = Path(zipped_workflow_path_arg)
        if not self.zipped_workflow_path.is_file():
            logger.error("Could not find --zipped-workflow-path")
            raise FileNotFoundError

        if os.environ.get("ICAV2_ACCESS_TOKEN", None) is None:
            logger.error("Could not get env var ICAV2_ACCESS_TOKEN")
            raise EnvironmentError
        # TODO check token expiry

        # Check either project name or project id is set
        project_id = self.args.get("--project-id", None)
        project_name = self.args.get("--project-name", None)

        if project_id is not None:
            self.project_id = project_id
            # Check project id is uuid format
            if not is_project_id_format(self.project_id):
                logger.error(f"--project-id parameter {self.project_id} is not of UUID format")
            # TODO - check is real project
        elif project_name is not None:
            self.project_name = self.project_name
            self.project_id = get_project_id_from_project_name(
                project_name,
                get_icav2_configuration()
            )
        else:
            logger.error("Must specify one of --project-id or --project-name")
            raise CheckArgumentError

        # Get analysis storage size
        self.analysis_storage_id = self.args.get("--analysis-storage-id", None)
        self.analysis_storage_size = self.args.get("--analysis-storage-size", None)

        # --analysis-storage-id takes preference
        if self.analysis_storage_id is not None:
            pass
        # --analysis-storage-id is not set and --analysis-storage-size is also not set
        # Get the default size (SMALL) and take to next step
        elif self.analysis_storage_size is None:
            self.analysis_storage_size = ICAV2_DEFAULT_ANALYSIS_STORAGE_SIZE
        elif self.analysis_storage_size is not None:
            self.analysis_storage_size = ICAv2AnalysisStorageSize(self.analysis_storage_size)
        # Use --analysis-storage-size or default value to get --analysis-storage-id
        if self.analysis_storage_id is None:
            self.analysis_storage_id = get_analysis_storage_id_from_analysis_storage_size(
                self.analysis_storage_size,
                get_icav2_configuration()
            )

    def __call__(self):
        self.deploy_workflow()

    def deploy_workflow(self):
        pipeline_id, code = create_workflow_from_zip_path(
            self.zipped_workflow_path,
            self.project_id,
            self.analysis_storage_id,
            get_icav2_configuration()
        )

        logger.info(f"Created pipeline with code '{code}' and id '{pipeline_id}'")
