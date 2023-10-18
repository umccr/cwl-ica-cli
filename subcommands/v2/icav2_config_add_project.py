#!/usr/bin/env python3

"""
Add project to the icav2 configuration yaml
"""
from classes.command import Command
from utils.icav2_gh_helpers import add_project_to_config_yaml, check_project_in_config_yaml, check_tenant_in_config_yaml
from utils.logging import get_logger
from argparse import ArgumentError
from utils.errors import CheckArgumentError
from typing import Optional, Dict, List


logger = get_logger()


class ICAv2AddProject(Command):
    """Usage:
    cwl-ica [options] icav2-add-project help
    cwl-ica [options] icav2-add-project (--tenant-name=<tenant_name>)
                                        (--project-name=<project_name>)
                                        (--project-id=<project_id>)

Description:
    The project to add. This is used by the bundle release asset GH actions to generate workflow objects.
    This command adds the project to config/icav2.yaml

Options:
    --tenant-name=<tenant_name>     Required: The name of the tenant that this project resides in
    --project-name=<project_name>   Required: The project name
    --project-id=<project_id>       Required: The project id

Environment:
    N/A

Example:
    cwl-ica icav2-add-project --tenant-name umccr-test --project-name playground_v2 --project-id aaaaaaaa-1111-2222-3333-bbbbbbbb
    """

    def __init__(self, command_argv):

        # Collect args from doc strings
        super(ICAv2AddProject, self).__init__(command_argv)

        # Initialise parameters
        self.tenant_name: Optional[str] = None
        self.project_name: Optional[str] = None
        self.project_id: Optional[str] = None

        # Check if help has been called
        if self.args["help"]:
            self._help()

        # Confirm 'required' arguments are present and valid
        try:
            logger.debug("Checking args")
            self.check_args()
        except ArgumentError:
            self._help(fail=True)

    def check_args(self):
        # Get project id
        self.tenant_name = self.args.get("--tenant-name", None)
        if self.tenant_name is None:
            logger.error(f"Please use --tenant-name parameter")
            raise CheckArgumentError

        self.project_name = self.args.get("--project-name", None)
        if self.project_name is None:
            logger.error(f"Please use --project-name parameter")
            raise CheckArgumentError

        self.project_id = self.args.get("--project-id", None)
        if self.project_id is None:
            logger.error(f"Please use --project-id parameter")
            raise CheckArgumentError

        # Check tenant not in config yaml
        if not check_tenant_in_config_yaml(self.tenant_name):
            logger.error(f"Tenant {self.tenant_name} not in icav2.yaml")
            raise CheckArgumentError

        if check_project_in_config_yaml(self.tenant_name, self.project_name):
            logger.error(f"Project {self.project_name} already in icav2.yaml")
            raise CheckArgumentError

    def __call__(self):
        logger.info("Add project to icav2.yaml")
        add_project_to_config_yaml(self.tenant_name, self.project_name, self.project_id)


