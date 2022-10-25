#!/usr/bin/env python

"""
This is the superclass for the three tools
append_typescript_to_workflow
append_typescript_to_tool
append_typescript_to_expression

Where the single premise of the subcommand is to add the directory 'typescript-expressions' to that tool/workflow/expression etc

We also test that yarn is installed and at least v3

Yarn is then stripped entirely as the top directory
"""


from classes.command import Command
from utils.logging import get_logger
from pathlib import Path
from string import ascii_letters, digits
from argparse import ArgumentError
from utils.repo import get_user_yaml_path, read_yaml
from utils.errors import UserNotFoundError, CheckArgumentError, InvalidNameError, InvalidVersionError
from semantic_version import Version
import os
from utils.errors import ItemDirectoryNotFoundError
from utils.typescript_helpers import create_blank_typescript_file, \
    create_blank_typescript_test_file, \
    create_typescript_expression_dir

from typing import Optional

logger = get_logger()


class AppendTypeScriptDir(Command):
    """
    Usage defined in subclasses
    """

    def __init__(self, command_argv, suffix="cwl", item_dir=None, item_type=None):
        # Collect args from doc strings
        super().__init__(command_argv)

        # Initialise each of our parameters
        self.name = None
        self.version = None
        self.username = None
        self.cwl_file_path = None
        self.typescript_expression_path = None
        self.suffix = suffix
        self.user_obj = None
        self.item_dir = item_dir
        self.item_type = item_type

        self.xtrace: Optional[bool] = None

        # Check length / add 'help' attribute if necessary
        # Check args
        self.check_args()

        try:
            self.check_args()
        except ArgumentError:
            self._help(fail=True)

    def __call__(self):
        # Create directory structure
        self.cwl_file_path = self.get_cwl_file_path()
        self.typescript_expression_path = self.get_typescript_expression_path()

        if not self.cwl_file_path.is_file():
            logger.error(f"Could not find file at \"{self.cwl_file_path}\"")
            raise FileNotFoundError

        if self.typescript_expression_path.is_dir():
            logger.error(f"typescript-expressions directory '{self.typescript_expression_path}' already exists")
            raise FileExistsError

        # Create typescript expression dir
        logger.info(f"Creating typescript expression directory to complement '{self.cwl_file_path}'")
        self.create_typescript_expression_dir()

        # Create blank file
        logger.info(f"Creating blank typescript file inside the new typescript-expressions directory")
        self.create_blank_typescript_file()

        # Create blank test file
        logger.info(f"Creating blank test file inside the new typescript-expressions directory")
        self.create_blank_typescript_test()

    # Functions implemented in subclass
    def check_args(self):
        """
        Check name, version and username are all defined
        :return:
        """
        raise NotImplementedError

    def get_top_dir(self, create_dir=False):
        """
        Implemented in subclass
        :return:
        """
        raise NotImplementedError

    @staticmethod
    def check_shlex_arg(arg_name, arg_val):
        """
        If argument contains characters outside of A-Z, 0-9, -, _, then fail
        :return:
        """

        # Removed hyphens from name convention, can be used for the versioning only
        illegal_chars = set(arg_val).difference(ascii_letters + digits + "-_")

        if not len(illegal_chars) == 0:
            logger.error("The following illegal characters were found in arg {arg_name}"
                         "{arg_chars}".format(
                            arg_name=arg_name,
                            arg_chars=", ".join(["\"%s\"" % char for char in illegal_chars])
                         ))
            raise InvalidNameError

    @staticmethod
    def check_conformance(arg_name, arg_val):
        """
        Check that the
        :param arg_name:
        :param arg_val:
        :return:
        """
        # Checks that the name conforms to convention of lowercase only
        if not arg_val.lower() == arg_val:
            logger.warning(f"Please use lowercase only when specifying arg {arg_name}.")

    @staticmethod
    def check_shlex_version_arg(arg_name, arg_val):
        """
        Check the version arg is good
        :param arg_name:
        :param arg_val:
        :return:
        """

        version_is_good = True

        try:
            Version.parse(arg_val)
        except ValueError:
            version_is_good = False

        if not version_is_good:
            logger.error("Was not able to parse {arg_val} as a version for parameter {arg_name}".format(
                            arg_name=arg_name,
                            arg_val=arg_val
                         ))
            raise InvalidVersionError

    def set_user_obj(self):
        """
        Checks that --username is in user_yaml_path
        :return:
        """

        # Check user yaml
        user_yaml_path = get_user_yaml_path()
        user_list = read_yaml(user_yaml_path)['users']

        # User dict
        for user in user_list:
            username = user.get("username", None)
            if username == self.username:
                self.user_obj = user
                break
        else:
            logger.error(f"Could not find \"{self.username}\" in {user_yaml_path}. "
                         f"Please configure user with cwl-ica configure-user")
            raise UserNotFoundError

    def set_user_arg(self):
        """
        Get --username or CWL_ICA_DEFAULT_USER env var
        :return:
        """

        username_arg = self.args.get("--username", None)

        username_env = os.environ.get("CWL_ICA_DEFAULT_USER", None)

        if username_arg is None and username_env is None:
            logger.error("Please specify the --username parameter or set a default user through "
                         "'cwl-ica set-default-user' then reactivate the conda env")
            raise CheckArgumentError

        self.username = username_arg if username_arg is not None else username_env

    def get_cwl_file_path(self):
        """
        Returns file under tools/<tool-name>/<tool-version>/<tool-name>-<tool-version>.cwl
        :return:
        """

        # Get directory
        items_path = self.item_dir
        # Get tool name
        item_path = Path(items_path) / \
            Path(self.name) / \
            Path(self.version) / \
            Path(self.name + "__" + self.version + "." + self.suffix)

        # Create tool name path
        if not item_path.parent.is_dir():
            item_path.parent.mkdir(parents=True)

        # Return tool path
        return item_path

    def check_cwl_path(self, cwl_path):
        """
        Check that the cwl path exists under item_dir
        :return:
        """
        # Check path is relative to item path
        if not cwl_path.absolute().resolve().relative_to(self.item_dir):
            logger.error(f"Expected item of type \"{self.item_type}\" to be in \"{self.item_dir}\"")
            raise ItemDirectoryNotFoundError

    def set_xtrace_arg(self):
        self.xtrace = self.args.get("--xtrace", False)

    def get_typescript_expression_path(self):
        return self.cwl_file_path.parent / "typescript-expressions"

    def set_name_and_version_from_file_path(self):
        """
        Sets the name and version attributes from the path attribute
        :return:
        """
        self.name, self.version = self.cwl_file_path.resolve().stem.split("__")

    def create_typescript_expression_dir(self):
        create_typescript_expression_dir(self.get_typescript_expression_path(), self.xtrace)

    def create_blank_typescript_file(self):
        create_blank_typescript_file(self.get_typescript_expression_path() / (self.cwl_file_path.stem + ".ts"), self.username)

    def create_blank_typescript_test(self):
        create_blank_typescript_test_file(self.get_typescript_expression_path(), self.cwl_file_path.stem, self.username)
