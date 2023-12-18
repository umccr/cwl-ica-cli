#!/usr/bin/env python3

"""
Validate a typescript expression
"""

# External imports
from argparse import ArgumentError
from pathlib import Path
from typing import Optional

# Utils
from ...utils.logging import get_logger
from ...utils.errors import CheckArgumentError
from ...utils.typescript_helpers import run_typescript_validation_script

# Classes
from ...classes.command import Command

# Set logger
logger = get_logger()


class TypeScriptExpressionDirValidate(Command):
    """Usage:
    cwl-ica typescript-expression-validate help
    cwl-ica typescript-expression-validate (--typescript-expression-dir="<path_to_typescript_expression_dir>")
                                           [--xtrace]

Description:
    Transpile the TypeScript expressions inside the directory and run all tests.
    Also create the .cwljs file that is safe to be imported by a CWL tool / expression or workflow

Options:
    --typescript-expression-dir=<typescript-expression-dir>  Required, the path to the cwl typescript expression directory
    --xtrace                                                 Optional, set xtrace on the validate_typescript_expressions_directory shell script

Example
    cwl-ica typescript-expression-validate --typescript-expression-dir /path/to/tool/typescript-expressions
    """

    def __init__(self, command_argv):
        """
        Check arguments - check cwl file path exists
        Import cwl object
        :param command_argv:
        """
        # Collect args from doc strings
        super().__init__(command_argv)

        self.typescript_expression_dir: Optional[Path] = None
        self.xtrace: Optional[bool] = None

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
        run_typescript_validation_script(self.typescript_expression_dir, self.xtrace)

    def check_args(self):
        """
        Check --schema-path exists
        :return:
        """

        # Check defined and assign properties
        typescript_expression_arg = self.args.get("--typescript-expression-dir", None)
        if typescript_expression_arg is None:
            logger.error("--typescript-expression-dir not defined")
            raise CheckArgumentError
        self.typescript_expression_dir = Path(typescript_expression_arg)

        if not self.typescript_expression_dir.is_dir():
            logger.error(f"Could not find directory {self.typescript_expression_dir}")
            raise NotADirectoryError

        # Check tsconfig.json exists in directory
        if not (self.typescript_expression_dir / "tsconfig.json").is_file():
            logger.error("Could not find tsconfig.json inside this directory, "
                         "are you sure this is a typescript expression directory?")
            raise FileNotFoundError

        self.xtrace = self.args.get("--xtrace", False)
