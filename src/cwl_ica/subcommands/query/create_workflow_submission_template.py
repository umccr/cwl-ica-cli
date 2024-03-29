#!/usr/bin/env python3

"""
Create the workflow submission template
"""

# External imports
from pathlib import Path
from typing import Dict

# Utils
from ...utils.logging import get_logger
from ...utils.repo import get_workflows_dir, get_workflow_yaml_path

# Classes
from ...classes.item_version_workflow import ItemVersionWorkflow

# Locals
from . import CreateSubmissionTemplate

# Set logger
logger = get_logger()


class CreateWorkflowSubmissionTemplate(CreateSubmissionTemplate):
    """Usage:
    cwl-ica [options] create-workflow-submission-template help
    cwl-ica [options] create-workflow-submission-template (--workflow-path=<path_to_workflow>)
                                                          (--prefix=<path_to_output_file_prefix>)
                                                          (--project=<project_workflow_belongs_to>)
                                                          (--launch-project=<project_to_launch_workflow>)
                                                          [--ica-workflow-run-instance-id=<ica_workflow_run_id>]
                                                          [--ignore-workflow-id-mismatch]
                                                          [--access-token=<access_token>]
                                                          [--gds-prefix=<gds_run_prefix>]
                                                          [--gds-work-prefix=<gds_work_prefix> | --gds-work-directory=<gds_work_directory>]
                                                          [--gds-output-prefix=<gds_run_output_prefix> | --gds-output-directory=<gds_run_output_directory>]
                                                          [--curl]

Description:
    Create a ica workflow submission template for a CWL workflow

Options:
    --workflow-path=<path_to_workflow>                         Required: Path to a cwl workflow
    --prefix=<prefix>                                          Optional: prefix to the run name and the output files
    --project=<project>                                        Required: Project the workflow belongs to
    --launch-project<project>                                  Optional: Linked project to launch from
    --ica-workflow-run-instance-id=<workflow_run_instance_id>  Optional: Workflow run id to base yaml template from
    --ignore-workflow-id-mismatch                              Optional: Ignore workflow id mismatch, useful for when creating a template for a different context
    --access-token=<access-token>                              Optional: Access token in same project as run instance id, ideally use env var ICA_ACCESS_TOKEN
    --gds-prefix=<gds_prefix>                                  Optional: Prefix for engine parameters workDirectory, outputDirectory which become <gds_prefix>/__DATE_STR__/work and <gds_prefix>/__DATE_STR__/output respectively
                                                                 where __DATE_STR__ is set to YYYYMMDD_HHMMSS at run time
                                                                 If gds-prefix is NOT set, user must specify
                                                                    one and only one of (gds-work-prefix OR gds-work-directory)
                                                                    AND one and only one of (gds-output-prefix OR gds-output-directory)
    --gds-work-prefix=<gds_work_prefix>                        Optional: Prefix for engine parameters workDirectory which becomes <gds_prefix>/work/__DATE_STR__
                                                                 where __DATE_STR__ is set to YYYYMMDD_HHMMSS at run time
                                                                 Overrides gds-prefix.workDirectory if set
    --gds-work-directory=<gds_work_directory>                  Optional: Specify the exact output directory path, cannot be used with gds-work-prefix
    --gds-output-prefix=<gds_output_prefix>                    Optional: Prefix for engine parameters outputDirectory which becomes <gds_prefix>/output/__DATE_STR__
                                                                 where __DATE_STR__ is set to YYYYMMDD_HHMMSS at run time
                                                                 Overrides gds-prefix.outputDirectory if set
    --gds-output-directory=<gds_output_directory>              Optional: Specify the exact output directory path, cannot be used with gds-output-prefix parameter
    --curl                                                     Optional: Use the curl command over ica binary to launch workflow

Environment:
  * ICA_BASE_URL
  * ICA_ACCESS_TOKEN

Example:
    cwl-ica create-workflow-submission-template --workflow-path /path/to/workflow --prefix submit-validation --project development_workflows --launch-project development --ica-workflow-run-id wfr.123456789 --gds-prefix gds://path/to/directory
    """

    def __init__(self, command_argv):
        # Call super class
        super().__init__(command_argv,
                         item_type_key="workflows",
                         item_type="workflow",
                         item_dir=get_workflows_dir(),
                         item_yaml_path=get_workflow_yaml_path())

    def get_item_arg(self) -> Path:
        """
        Get --workflow-path or --tool-path from args
        :return:
        """
        return Path(self.args.get("--workflow-path", None))

    def version_loader(self, version: Dict, cwl_file_path: Path) -> ItemVersionWorkflow:
        """
        Load ItemVersionWorkflow
        :return:
        """
        version = version.copy()
        version['cwl_file_path'] = cwl_file_path
        return ItemVersionWorkflow.from_dict(version)

    @staticmethod
    def get_json_for_input_attribute(input_type: str) -> Dict:
        """
        :return:
        """
        raise NotImplementedError

    @staticmethod
    def get_json_for_schema_input_attribute(schema_dict, optional=False):
        """
        :param schema_dict:
        :param optional:
        :return:
        """
        raise NotImplementedError

    def write_json_file(self):
        raise NotImplementedError
