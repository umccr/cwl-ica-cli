#!/usr/bin/env python3

"""
Subclass of initialiser
"""

from subcommands.appenders.append_typescript_dir import AppendTypeScriptDir
from utils.logging import get_logger
from pathlib import Path
from classes.item_version_expression import ItemVersionExpression
from classes.item_expression import ItemExpression
from utils.repo import get_expression_yaml_path, get_expressions_dir
from utils.errors import CheckArgumentError


logger = get_logger()


class AppendTypeScriptExpressionDir(AppendTypeScriptDir):
    """Usage:
    cwl-ica [options] append-typescript-directory-to-cwl-expression-tool help
    cwl-ica [options] append-typescript-directory-to-cwl-expression-tool (--expression-path /path/to/expression.cwl)
                                                                         [--xtrace]


Description:
    Create a directory adjacent to the expression cwl path that handles expressions in typescript.


Options:
    --expression-path=<the expression path>                         Required, the path to the cwl expression
    --xtrace                                                        Optional, add xtrace option to initialise_typescript_expression_directory.sh

Example:
    cwl-ica append-typescript-directory-to-cwl-expression-tool --expression-path "expressions/flatten_array_file/1.0.0/flatten_array_file__1.0.0.cwl"
    """

    def __init__(self, command_argv):
        # Call super class
        super(AppendTypeScriptExpressionDir, self).__init__(command_argv,
                                                            suffix="cwl",
                                                            item_dir=get_expressions_dir(),
                                                            item_type="type")

    def __call__(self):
        # Call the super class' call function
        super(AppendTypeScriptExpressionDir, self).__call__()

    # Methods implemented in subclass
    def check_args(self):
        """
        Checks --expression-path exists
        :return:
        """

        # We will have a name and a version for this expression/expression/workflow etc.

        # Check --expression-path argument
        cwl_path = self.args.get("--expression-path", None)

        if cwl_path is None:
            logger.error("--expression-path not specified")
            raise CheckArgumentError

        # Convert to path type
        cwl_path = Path(cwl_path)

        self.check_cwl_path(cwl_path)

        self.cwl_file_path = cwl_path

        if not cwl_path.is_file():
            logger.error(f"--expression-path argument \"{cwl_path} could not be found")
            raise CheckArgumentError

        # Get the name and version attributes
        self.set_name_and_version_from_file_path()

        self.set_xtrace_arg()
