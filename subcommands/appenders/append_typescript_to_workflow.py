#!/usr/bin/env python3

"""
Subclass of initialiser
"""

from subcommands.appenders.append_typescript_dir import AppendTypeScriptDir
from utils.logging import get_logger
from pathlib import Path
from utils.repo import get_workflows_dir
from utils.errors import CheckArgumentError

logger = get_logger()


class AppendTypeScriptWorkflowDir(AppendTypeScriptDir):
    """Usage:
    cwl-ica [options] append-typescript-directory-to-cwl-workflow help
    cwl-ica [options] append-typescript-directory-to-cwl-workflow (--workflow-path /path/to/workflow.cwl)
                                                                  [--xtrace]

Description:
    Create a directory adjacent to the workflow cwl path that handles js in typescript.

Options:
    --workflow-path=<the workflow path>    Required, the path to the cwl workflow
    --xtrace                               Optional, add xtrace option to initialise_typescript_expression_directory.sh

Example:
    cwl-ica append-typescript-directory-to-cwl-workflow --workflow-path "workflows/bclconvert/4.0.3/bclconvert__4.0.3.cwl"
    """

    def __init__(self, command_argv):
        # Call super class
        super(AppendTypeScriptWorkflowDir, self).__init__(
            command_argv,
            suffix="cwl",
            item_dir=get_workflows_dir(),
            item_type="type"
        )

    def __call__(self):
        # Call the super class' call function
        super(AppendTypeScriptWorkflowDir, self).__call__()

    # Methods implemented in subclass
    def check_args(self):
        """
        Checks --workflow-path exists
        :return:
        """

        # We will have a name and a version for this workflow/tool/workflow etc.

        # Check --workflow-path argument
        cwl_path = self.args.get("--workflow-path", None)

        if cwl_path is None:
            logger.error("--workflow-path not specified")
            raise CheckArgumentError

        # Convert to path type
        cwl_path = Path(cwl_path)

        self.check_cwl_path(cwl_path)

        self.cwl_file_path = cwl_path

        if not cwl_path.is_file():
            logger.error(f"--workflow-path argument \"{cwl_path} could not be found")
            raise CheckArgumentError

        # Get the name and version attributes
        self.set_name_and_version_from_file_path()

        self.set_xtrace_arg()
