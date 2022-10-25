#!/usr/bin/env python3

"""
Subclass of initialiser
"""

from subcommands.appenders.append_typescript_dir import AppendTypeScriptDir
from utils.logging import get_logger
from pathlib import Path
from classes.item_version_tool import ItemVersionTool
from classes.item_tool import ItemTool
from utils.repo import get_tool_yaml_path, get_tools_dir
from utils.errors import CheckArgumentError

logger = get_logger()


class AppendTypeScriptToolDir(AppendTypeScriptDir):
    """Usage:
    cwl-ica [options] append-typescript-directory-to-cwl-commandline-tool help
    cwl-ica [options] append-typescript-directory-to-cwl-commandline-tool (--tool-path /path/to/tool.cwl)
                                                                          [--xtrace]


Description:
    Create a directory adjacent to the tool cwl path that handles tools in typescript.


Options:
    --tool-path=<the tool path>                         Required, the path to the cwl tool
    --xtrace                                            Optional, add xtrace option to initialise_typescript_expression_directory.sh

Example:
    cwl-ica append-typescript-directory-to-cwl-commandline-tool --tool-path "tools/flatten_array_file/1.0.0/flatten_array_file__1.0.0.cwl"
    """

    def __init__(self, command_argv):
        # Call super class
        super(AppendTypeScriptToolDir, self).__init__(command_argv,
                                                            suffix="cwl",
                                                            item_dir=get_tools_dir(),
                                                            item_type="type")

    def __call__(self):
        # Call the super class' call function
        super(AppendTypeScriptToolDir, self).__call__()

    # Methods implemented in subclass
    def check_args(self):
        """
        Checks --tool-path exists
        :return:
        """

        # We will have a name and a version for this tool/tool/workflow etc.

        # Check --tool-path argument
        cwl_path = self.args.get("--tool-path", None)

        if cwl_path is None:
            logger.error("--tool-path not specified")
            raise CheckArgumentError

        # Convert to path type
        cwl_path = Path(cwl_path)

        self.check_cwl_path(cwl_path)

        self.cwl_file_path = cwl_path

        if not cwl_path.is_file():
            logger.error(f"--tool-path argument \"{cwl_path} could not be found")
            raise CheckArgumentError

        # Get the name and version attributes
        self.set_name_and_version_from_file_path()

        self.set_xtrace_arg()
