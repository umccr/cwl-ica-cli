#!/usr/bin/env python3

"""
Get the logs of a step

This is entirely the wrong spot for this, but the code was already all here!

"""
import tempfile
import os

from libica.openapi.v2.model.analysis_step_logs import AnalysisStepLogs

from utils.cwl_helper_utils import get_fragment_from_cwl_id
from utils.icav2_helpers import get_project_id_from_project_name, \
    get_icav2_configuration, is_project_id_format, \
    get_workflow_steps, filter_analysis_steps, write_analysis_step_logs

from classes.command import Command
from utils.logging import get_logger
from pathlib import Path
from argparse import ArgumentError
from utils.errors import CheckArgumentError
from typing import Optional


logger = get_logger()


class GetICAv2AnalysisStepLogs(Command):
    """Usage:
    cwl-ica [options] icav2-get-analysis-step-logs help
    cwl-ica [options] icav2-get-analysis-step-logs (--analysis-id=<analysis_id>)
                                                   (--step-name=<step_name>)
                                                   (--stdout | --stderr)
                                                   [--project-name=<project_name> | --project-id=<project_id>]
                                                   [--output-path=<output_file>]

Description:
    Given an analysis id and project id, print either the log stderr or log stdout to console or to an output file
    The step name can be collected by running cwl-ica icav2-list-analysis-steps.
    You can also use 'cwltool' as the step-name parameter to print the cwltool debug logs.

Options:
    --analysis-id=<analysis_id>                              Required, the analysis id you wish to list logs of
    --step-name=<step_name>                                  Required, the name of the step, use 'cwltool' to get the cwltool debug logs (maps to technical step id pipeline_runner.0)
    --stdout                                                 Optional, get the stdout of a step
    --stderr                                                 Optional, get the stderr of a step
                                                             Must specify one (and only one of) --stdout and --stderr
    --project-id=<project_id>                                Optional, id of project context you wish to launch the pipeline analysis.
    --project-name=<project_name>                            Optional, name of the project context you wish to launch the pipeline analysis.
                                                             Must specify one (and only one of) --project-name and --project-id  or set ICAV2_PROJECT_ID env var
    --output-path=<output_file>                              Write output to file, otherwise written to stdout / console

Environment:
    ICAV2_ACCESS_TOKEN (required)
    ICAV2_BASE_URL (optional, defaults to ica.illumina.com)
    ICAV2_PROJECT_ID (optional)


Example:
    cwl-ica icav2-get-analysis-step-logs --project-name playground_v2 --analysis-id abcd12345 --step-name cwltool --stderr --output-path cwltool-debug-logs.txt
    """

    def __init__(self, command_argv):

        # Collect args from doc strings
        super(GetICAv2AnalysisStepLogs, self).__init__(command_argv)

        # Initialise parameters
        self.project_id: Optional[str] = None
        self.project_name: Optional[str] = None
        self.analysis_id: Optional[str] = None
        self.step_name: Optional[str] = None
        self.stdout: Optional[bool] = None
        self.stderr: Optional[bool] = None
        self.output_path: Optional[Path] = None

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
            "The cwl-ica icav2-get-analysis-step-logs subcommand has been deprecated, "
            "please checkout the icav2 projectanalyses get-analysis-step-logs subcommand instead "
            "from the https://github.com/umccr/icav2-cli-plugins repository"
        )
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

        # Get analysis storage size
        self.step_name = self.args.get("--step-name", None)

        # Check analysis id is not None
        if self.step_name is None:
            logger.error("Must specify --step-name parameter, please use the cwl-ica icav2-list-analysis-steps"
                         "and use the 'name' attribute of the step youd like to see")
            raise CheckArgumentError
        if self.step_name == "cwltool":
            self.step_name = "pipeline_runner.0"

        # Check not both stderr and stdout have been specified
        if self.args.get("--stderr", False) and self.args.get("--stdout", False):
            logger.error("Please specify one and only one of --stderr and --stdout")
            raise CheckArgumentError
        if not self.args.get("--stderr", False) and not self.args.get("--stdout", False):
            logger.error("Please specify one and only one of --stderr and --stdout")
            raise CheckArgumentError

        # Check if stderr has been specified
        if self.args.get("--stderr", False):
            self.stderr = True
            self.stdout = False
        else:
            self.stderr = False
            self.stdout = True

        # Check output path parent exists
        if self.args.get("--output-path", None) is not None:
            self.output_path = Path(self.args.get("--output-path"))
            if str(self.output_path) == "-":
                # Writing to stdout
                self.output_path = None
            elif not self.output_path.parent.is_dir():
                logger.error(f"Parent of {self.output_path} does not exist, please create it first")
                raise CheckArgumentError

    def get_analysis_logs(self) -> AnalysisStepLogs:
        # Get workflow steps
        workflow_steps = get_workflow_steps(
            self.project_id, self.analysis_id, configuration=get_icav2_configuration()
        )

        # Get step names
        workflow_step_names = filter_analysis_steps(workflow_steps, True)

        # Check step in list of step names
        matching_workflow_steps = list(filter(lambda x: x.get("name") == self.step_name, workflow_step_names))
        if len(matching_workflow_steps) == 0:
            logger.error(f"Could not find step-name {self.step_name} in analysis id {self.analysis_id}")
            logger.error("Please try running cwl-ica icav2-list-analysis-steps to view list of available step names")
            raise ValueError
        if len(matching_workflow_steps) > 1:
            logger.error(f"Got multiple matches for step-name {self.step_name}")
            raise ValueError

        matching_workflow_step = matching_workflow_steps[0]

        if matching_workflow_step.get("status") in ["WAITING"]:
            logger.error(f"Could not get information about {self.step_name} since it is still waiting to run")
            raise ValueError

        # Get analysis step log object
        log_obj: AnalysisStepLogs = list(
            filter(
                lambda x: str(get_fragment_from_cwl_id(x.get("name"))) == matching_workflow_step.get("name"),
                workflow_steps
            )
        )[0].logs

        if len(log_obj.to_dict()) == 0:
            logger.error(f"Could not collect logs for step {matching_workflow_step.get('name')}")
            raise AttributeError

        return log_obj

    def print_logs(self, log_obj: AnalysisStepLogs):

        if self.output_path is not None:
            output_path = self.output_path
        else:
            tmp_obj = tempfile.NamedTemporaryFile()
            output_path = tmp_obj.name

        write_analysis_step_logs(
            log_obj,
            self.project_id,
            "stderr" if self.stderr else "stdout",
            output_path,
            configuration=get_icav2_configuration(),
            is_cwltool_log=True if self.step_name == "pipeline_runner.0" else False
        )

        if self.output_path is None:
            with open(output_path, 'r') as f_h:
                print(f_h.read())

    def __call__(self):
        logger.info("Collecting workflow and getting log files")
        log_obj = self.get_analysis_logs()
        logger.info("Writing out log files, this may take some time if the analysis is still running")
        self.print_logs(log_obj)
