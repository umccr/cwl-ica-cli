#!/usr/bin/env python3

"""
Validate a cwl tool
"""

# External imports
from argparse import ArgumentError
from pathlib import Path

# Utils
from ...utils.logging import get_logger
from ...utils.repo import get_tools_dir
from ...utils.errors import CheckArgumentError

# Classes
from ...classes.cwl_tool import CWLTool

# Locals
from . import Validate

logger = get_logger()


class ToolValidate(Validate):
    """Usage:
    cwl-ica tool-validate help
    cwl-ica tool-validate (--tool-path="<path_to_cwl_tool>")

Description:
    Validate a CWL File of CommandLineTool. This must be done prior to registering the tool with the "cwl-ica tool-init" command.
    The CWL tool must be in the tools/ directory under CWL_ICA_REPO_PATH

Options:
    --tool-path=<tool_path>      Required, the path to the cwl tool

Example
    cwl-ica tool-validate --tool-path tools/samtools-fastq/1.10/samtools-fastq__1.10.cwl
    """

    def __init__(self, command_argv):
        """
        Check arguments - check cwl file path exists
        Import cwl object
        :param command_argv:
        """
        # Collect args from doc strings
        super().__init__(command_argv)

        # Check help
        self.check_length(command_argv)

        # Check if help has been called
        if self.args["help"]:
            self._help()

        # Confirm 'required' arguments are present and valid
        try:
            self.check_args()
        except ArgumentError:
            self._help(fail=True)

    def __call__(self):
        super(ToolValidate, self).__call__()

    def check_args(self):
        """
        Check --tool-path exists
        :return:
        """

        # Check defined and assign properties
        tool_path_arg = self.args.get("--tool-path", None)
        if tool_path_arg is None:
            logger.error("--tool-path not defined")
            raise CheckArgumentError
        self.cwl_file_path = Path(tool_path_arg)
        # Checks cwl_file_path
        self.check_file()

        # Make sure file path exists
        self.name, self.version = self.split_name_version(items_dir=self.get_top_dir())

        # Check name
        self.check_shlex_arg("--tool-path", self.name)

        # Check version
        self.check_shlex_version_arg("--tool-path", self.version)

        # Set cwl obj
        self.cwl_obj = self.import_cwl_obj()

    def import_cwl_obj(self):
        """
        Create a cwl object
        :return:
        """

        return CWLTool(
            cwl_file_path=self.cwl_file_path,
            name=self.name,
            version=self.version,
            create=False,
            user_obj=None
        )

    @staticmethod
    def get_top_dir(create_dir=False):
        """
        Returns <CWL_ICA_REPO_PATH>/tools
        :return:
        """
        return get_tools_dir(create_dir=create_dir)
