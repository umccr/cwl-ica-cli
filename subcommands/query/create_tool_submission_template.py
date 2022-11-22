#!/usr/bin/env python3

"""
Create the tool submission template
"""

from utils.logging import get_logger
from subcommands.query.create_submission_template import CreateSubmissionTemplate
from utils.repo import get_tools_dir, get_tool_yaml_path
from classes.item_version_tool import ItemVersionTool
from pathlib import Path
from typing import Dict

logger = get_logger()


class CreateToolSubmissionTemplate(CreateSubmissionTemplate):
    """Usage:
    cwl-ica [options] create-tool-submission-template help
    cwl-ica [options] create-tool-submission-template (--tool-path=<path_to_tool>)
                                                      (--prefix=<path_to_output_prefix>)
                                                      (--project=<project_tool_belongs_to>)
                                                      [--launch-project=<project_to_launch_tool>]
                                                      [--ica-workflow-run-instance-id=<ica_workflow_run_id>]
                                                      [--ignore-workflow-id-mismatch]
                                                      [--access-token=<access_token>]
                                                      [--gds-prefix=<gds_run_prefix>]
                                                      [--gds-work-prefix=<gds_work_prefix> | --gds-work-directory=<gds_work_directory>]
                                                      [--gds-output-prefix=<gds_run_output_prefix> | --gds-output-directory=<gds_run_output_directory>]
                                                      [--curl]

Description:
    Create a ica tool submission template for a CWL tool

Options:
    --tool-path=<path_to_tool>                                 Required: Path to a cwl tool
    --prefix=<prefix>                                          Optional: prefix to the run name and the output files
    --project=<project>                                        Required: Project the tool belongs to
    --launch-project=<project>                                 Optional: Linked project to launch from
    --ica-workflow-run-instance-id=<workflow_run_instance_id>  Optional: Workflow run id to base yaml template from
    --access-token=<access-token>                              Optional: Access token in same project as run instance id, ideally use env var ICA_ACCESS_TOKEN
    --ignore-workflow-id-mismatch                              Optional: Ignore workflow id mismatch, useful for when creating a template for a different context
    --curl                                                     Optional: Use the curl command over ica binary to launch tool
    --gds-prefix=<gds_prefix>                                  Optional: Prefix for engine parameters workDirectory, outputDirectory which become <gds_prefix>/work/__DATE_STR__ and <gds_prefix>/output/__DATE_STR__ respectively
                                                                 where __DATE_STR__ is set to YYYYMMDD_HHMMSS at run time
                                                                 If gds-prefix is NOT set, user must specify
                                                                    one and only one of (gds-work-prefix OR gds-work-directory)
                                                                    AND one and only one of (gds-output-prefix OR gds-output-directory)
    --gds-work-prefix=<gds_work_prefix>                        Optional: Prefix for engine parameters workDirectory which becomes <gds_prefix>/__DATE_STR__/work
                                                                 where __DATE_STR__ is set to YYYYMMDD_HHMMSS at run time
                                                                 Overrides gds-prefix.workDirectory if set
    --gds-work-directory=<gds_work_directory>                  Optional: Specify the exact output directory path, cannot be used with gds-work-prefix
    --gds-output-prefix=<gds_output_directory>                 Optional: Prefix for engine parameters outputDirectory which becomes <gds_prefix>/__DATE_STR__/output
                                                                 where __DATE_STR__ is set to YYYYMMDD_HHMMSS at run time
                                                                 Overrides gds-prefix.outputDirectory if set
    --gds-output-directory=<gds_output_directory>              Optional: Specify the exact output directory path, cannot be used with gds-output-prefix parameter


Environment:
  * ICA_BASE_URL
  * ICA_ACCESS_TOKEN

Example:
    cwl-ica create-tool-submission-template --tool-path /path/to/tool --prefix submit-validation --project development_workflows --launch-project development --ica-workflow-run-id wfr.123456789
    """

    def __init__(self, command_argv):
        # Call super class
        super().__init__(command_argv,
                         item_type_key="tools",
                         item_type="tool",
                         item_dir=get_tools_dir(),
                         item_yaml_path=get_tool_yaml_path())

    def get_item_arg(self) -> Path:
        """
        Get --tool-path or --tool-path from args
        :return:
        """
        return Path(self.args.get("--tool-path", None))

    def version_loader(self, version: Dict, cwl_file_path: Path) -> ItemVersionTool:
        """
        Load ItemVersionTool
        :return:
        """
        version = version.copy()
        version['cwl_file_path'] = cwl_file_path
        return ItemVersionTool.from_dict(version)

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