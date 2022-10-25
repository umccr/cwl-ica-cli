#!/usr/bin/env python3

"""
Create tool from template
Pulls in a cwl tool object and runs create_object() on it.
"""

from subcommands.creators.create_from_template import CreateFromTemplate
from utils.logging import get_logger
from argparse import ArgumentError
from utils.repo import get_typescript_expressions_dir
from utils.errors import CheckArgumentError
from utils.typescript_helpers import create_typescript_expression_dir, \
    create_blank_typescript_file, \
    create_blank_typescript_test_file
from typing import Optional

logger = get_logger()


class CreateTypeScriptExpressionFromTemplate(CreateFromTemplate):
    """Usage:
    cwl-ica create-typescript-expression-from-template help
    cwl-ica create-typescript-expression-from-template (--typescript-expression-name="<name_of_typescript_expression>")
                                                       (--typescript-expression-version="<typescript_expression_version>")
                                                       [--username="<your_name>"]
                                                       [--xtrace]


Description:
    We initialise a .ts file under the directory <CWL_ICA_REPO_PATH>/typescript-expressions/<typescript_expression_name>/<typescript_expression_version>/<typescript_expression_name>__<typescript_expression_version>.ts
    We also use yarn v3 to create a project in this directory. Please read up on the instructions on installing yarn in the TypeScript section of this repos' wiki

    The file is empty apart from the username component being populated at the top of the file as the author.

    TypeScript Expressions cannot be 'registered' in the same way that other CWL components can be, although this may change at a later stage

    It is best to use this command to create 'common' JavaScript expressions for tools / workflows that may share
    common requirements.

    We then also create a typescript file with the following contents
    // Author: Your Username
    // For assistance on generation of typescript expressions
    // In CWL, please visit our wiki page at https://github.com/umccr/cwl-ica/wiki/TypeScript

Options:
    --typescript-expression-name=<typescript_expression_name>            Required, the name of the typescript-expression
    --typescript-expression-version=<typescript_expression_version>      Required, the version of the typescript-expression
    --username=<username>                                                Optional, the username of the creator / maintainer
    --xtrace                                                             Optional, set xtrace on the initialise_typescript_expression_directory shell script

EnvironmentVariables:
    CWL_ICA_DEFAULT_USER                                                 Saves having to use --username

Example
    cwl-ica create-typescript-expression-from-template --typescript-expression-name dragen-tools --typescript-expression-version 1.0.0  --username "Alexis Lucattini"
    """

    def __init__(self, command_argv):
        # Collect args from doc strings
        super().__init__(command_argv, suffix="ts")

        # Collect arguments
        self.args: dict = self.get_args(command_argv)

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
        self.cwl_file_path = self.get_cwl_file_path()

        if len(list(self.cwl_file_path.parent.glob("*"))) > 0:
            logger.error(f"Directory {self.cwl_file_path.parent} already exists")
            raise FileExistsError

        logger.info("Creating yarn.lock files in typescript expressions directory")
        self.create_typescript_expression_dir()

        logger.info("Creating blank typescript find in typescript expressions directory")
        self.create_blank_typescript_file()

        # Log to user
        logger.info(f"Created empty typescript expression directory at \"{self.cwl_file_path.parent}\" "
                    f"with a blank typescript file at {self.cwl_file_path}")

        # Create a blank tests under the tests directory
        logger.info("Creating a blank typescript test in the tests directory")
        self.create_blank_typescript_test()

    def check_args(self):
        """
        Check --workflow-name, --workflow-version and --username are defined
        Check --workflow-name, --workflow-version are appropriate
        Check --username is in user.yaml
        :return:
        """

        # Check defined and assign properties
        typescript_expression_name_arg = self.args.get("--typescript-expression-name", None)
        self.check_shlex_arg("--typescript-expression-name", typescript_expression_name_arg)
        self.check_conformance("--typescript-expression-name", typescript_expression_name_arg)
        if typescript_expression_name_arg is None:
            logger.error("--typescript-expression-name not defined")
            raise CheckArgumentError
        self.name = typescript_expression_name_arg

        typescript_expression_version_arg = self.args.get("--typescript-expression-version", None)
        self.check_shlex_version_arg("--typescript-expression-version", typescript_expression_version_arg)
        if typescript_expression_version_arg is None:
            logger.error("--typescript-expression-version not defined")
            raise CheckArgumentError
        self.version = typescript_expression_version_arg

        # Set user args
        self.set_user_arg()
        self.set_user_obj()

        # Set xtrace
        self.xtrace = self.args.get("--xtrace", False)

    def get_top_dir(self, create_dir=True):
        """
        Returns <CWL_ICA_REPO_PATH>/typescript-expressions
        :return:
        """
        return get_typescript_expressions_dir(create_dir=create_dir)

    def create_typescript_expression_dir(self):
        create_typescript_expression_dir(self.cwl_file_path.parent, xtrace=self.xtrace)

    def create_blank_typescript_file(self):
        create_blank_typescript_file(self.cwl_file_path, self.username)

    def create_blank_typescript_test(self):
        create_blank_typescript_test_file(self.cwl_file_path.parent, self.cwl_file_path.stem, self.username)
