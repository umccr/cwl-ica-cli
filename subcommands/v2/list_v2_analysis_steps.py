#!/usr/bin/env python3

"""
List steps of an analysis

This is entirely the wrong spot for this, but the code was already all here!

"""

from libica.openapi.v2.model.create_cwl_analysis import CreateCwlAnalysis

from utils.icav2_helpers import get_project_id_from_project_name, \
    get_icav2_configuration, is_project_id_format, \
    get_analysis_storage_id_from_analysis_storage_size, \
    get_pipeline_id_from_pipeline_code, get_data_obj_from_project_id_and_path, \
    create_data_obj_from_project_id_and_path, \
    launch_workflow, get_workflow_steps, filter_analysis_steps

from datetime import datetime

from classes.command import Command
from classes.icav2_launch_json import ICAv2LaunchJson
from utils.logging import get_logger
from pathlib import Path
from argparse import ArgumentError
from utils.globals import ICAv2AnalysisStorageSize
from utils.errors import CheckArgumentError
from typing import Optional, Dict, List
import json
import os

logger = get_logger()


class ICAv2ListAnalysisSteps(Command):
    """Usage:
    cwl-ica [options] icav2-list-analysis-steps help
    cwl-ica [options] icav2-list-analysis-steps (--analysis-id=<analysis-id>)
                                                [--project-name=<project_name> | --project-id=<project_id>]
                                                [--show-technical-steps]

Description:
    List analysis steps 

Options:
    --analysis-id=<analysis_id>                              Required, the id of the analysis
    --project-id=<project_id>                                Optional, id of project context you wish to launch the pipeline analysis.
    --project-name=<project_name>                            Optional, name of the project context you wish to launch the pipeline analysis.
                                                             Must set one of (and only one of) --project-id or --project-name or set ICAV2_PROJECT_ID env var
    --show-technical-steps                                   Also list technical steps

Environment:
    ICAV2_ACCESS_TOKEN (required)
    ICAV2_BASE_URL (optional, defaults to ica.illumina.com)
    ICAV2_PROJECT_ID (optional)


Example:
    cwl-ica icav2-list-analysis-steps --project-name playground_v2 --analysis-id abcd123456
    """

    def __init__(self, command_argv):
        logger.warning(
            "The cwl-ica list-analysis-steps subcommand has been deprecated, "
            "please checkout the icav2 projectanalyses list-analysis-steps subcommand "
            "from the https://github.com/umccr/icav2-cli-plugins repository"
        )
        # Collect args from doc strings
        super(ICAv2ListAnalysisSteps, self).__init__(command_argv)

        # Initialise parameters
        self.project_id: Optional[str] = None
        self.project_name: Optional[str] = None
        self.analysis_id: Optional[str] = None
        self.show_technical_steps: Optional[bool] = None

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
        # Get project id
        self.project_id = self.args.get("--project-id", None)
        self.project_name = self.args.get("--project-name", None)
        if self.project_id is not None:
            if not is_project_id_format(self.project_id):
                logger.error(f"Got --project-id parameter as {self.project_id} but is not in project-id format")
                raise CheckArgumentError
        if self.project_id is None and self.project_name is None:
            if os.environ.get("ICAV2_PROJECT_ID", None) is not None:
                self.project_id = os.environ.get("ICAV2_PROJECT_ID")
            else:
                logger.error("Must set one of --project-id or --project-name or set ICAV2_PROJECT_ID env var")
                raise CheckArgumentError
        if self.project_id is None and self.project_name is not None:
            self.project_id = get_project_id_from_project_name(self.project_name, get_icav2_configuration())

        # Get analysis storage size
        self.analysis_id = self.args.get("--analysis-id", None)

        # Check analysis id is not None
        if self.analysis_id is None:
            logger.error("Must specify --analysis-id parameter")
            raise CheckArgumentError

        if not is_project_id_format(self.analysis_id):
            logger.error(f"Got --analysis-id parameter as {self.analysis_id} but is not in UUID format")
            raise CheckArgumentError

        # Check if show technical steps has been specified
        if self.args.get("--show-technical-steps", False):
            self.show_technical_steps = True
        else:
            self.show_technical_steps = False

    def get_analysis_steps(self) -> List[Dict]:
        # Get workflow steps
        workflow_steps = get_workflow_steps(self.project_id, self.analysis_id, configuration=get_icav2_configuration())

        return filter_analysis_steps(workflow_steps, self.show_technical_steps)

    def __call__(self):
        analysis_steps = self.get_analysis_steps()
        print(json.dumps(analysis_steps, indent=2))
