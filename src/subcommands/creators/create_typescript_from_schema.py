#!/usr/bin/env python

"""
Wrapper around create_typescript_interface_from_schema.py
"""

from classes.command import Command
from utils.logging import get_logger
from typing import Optional
from docopt import docopt
from pathlib import Path
from argparse import ArgumentError
from string import ascii_letters, digits
from utils.repo import get_user_yaml_path, read_yaml, get_tools_dir, get_schemas_dir
from utils.errors import UserNotFoundError, CheckArgumentError, InvalidNameError, InvalidVersionError
from semantic_version import Version
import os
from utils.miscell import get_name_version_tuple_from_cwl_file_path
from utils.subprocess_handler import run_subprocess_proc

logger = get_logger()


class CreateTypeScriptInterfaceFromCWLSchema(Command):
    """Usage:
    cwl-ica create-typescript-interface-from-cwl-schema help
    cwl-ica create-typescript-interface-from-cwl-schema (--schema-path="<name_of_schema>")

Description:
    Given a path to a schema definition, create a file in the same location with a .ts suffix.
    This works by wrapping and packing the schema in a tool via cwltool --pack and then pulling it out again

EnvironmentVariables:
    CWL_ICA_REPO_PATH         So we know where to find the other schemas that may be nested in the schema

Example
    cwl-ica create-typescript-interface-from-cwl-schema --schema-path schemas/fastq-list-row/1.0.0/fastq-list-row__1.0.0.yaml
    """

    def __init__(self, command_argv, suffix="ts"):
        # Collect args from doc strings
        super().__init__(command_argv)

        # Initialise each of our parameters
        self.name: Optional[str] = None
        self.version: Optional[str] = None
        self.yaml_file_path: Optional[Path] = None

        # Init requirements of subclass
        # Get args
        self.get_args(command_argv)
        # Check length / add 'help' attribute if necessary
        # Check args
        try:
            self.check_args()
        except ArgumentError:
            self._help(fail=True)

    def __call__(self):
        # Create typescript object
        logger.info(f"Creating a typescript interface to match the schema '{self.yaml_file_path}'")
        self.create_typescript_interface_from_schema()

        # Check completion was complete
        if not self.get_typescript_interface_path().is_file():
            logger.error(f"Expected a file to be created at {self.get_typescript_interface_path()}, check the logs")
            raise FileNotFoundError

    def check_args(self):
        """
        Check --schema-path exists and is in the schema directory
        :return:
        """

        # Check defined and assign properties
        schema_path_arg = self.args.get("--schema-path", None)
        self.check_shlex_arg("--schema-path", schema_path_arg)
        self.check_conformance("--schema-path", schema_path_arg)
        if schema_path_arg is None:
            logger.error("--schema-path not defined")
            raise CheckArgumentError

        self.name, self.version = get_name_version_tuple_from_cwl_file_path(self.yaml_file_path, items_dir=get_schemas_dir())

    def get_typescript_interface_path(self):
        return self.yaml_file_path.parent / (self.yaml_file_path.stem + ".ts")

    def get_schema_file_path(self):
        return get_schemas_dir() / self.name / self.version

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

    def create_typescript_interface_from_schema(self):
        """
        Run the create_typescript_interface_from_schema.py script
        """
        run_subprocess_proc(
            [
                "create_typescript_interface_from_schema.py",
                "--schema-path", str(self.yaml_file_path)
            ], capture_output=True
        )
