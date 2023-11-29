#!/usr/bin/env python3

"""
Add a tenant to the v2 configuration yaml
"""
from classes.command import Command
from utils.icav2_gh_helpers import add_tenant_to_config_yaml, check_tenant_in_config_yaml
from utils.logging import get_logger
from argparse import ArgumentError
from utils.errors import CheckArgumentError
from typing import Optional


logger = get_logger()


class ICAv2AddTenant(Command):
    """Usage:
    cwl-ica [options] icav2-add-tenant help
    cwl-ica [options] icav2-add-tenant (--tenant-name=<tenant_name>)

Description:
    The tenant name to add. This is used by GH Actions to collect the secret ICAV2_ACCESS_TOKEN_<TENANT_NAME>.
    So this is merely a placeholder, it does not need to match the actual name of the tenant (but it should).
    This command adds the tenant to config/icav2.yaml

Options:
    --tenant-name=<tenant_name>   Required: The name of the tenant
Environment:

Example:
    cwl-ica icav2-add-tenant --tenant-name umccr-test
    """

    def __init__(self, command_argv):

        # Collect args from doc strings
        super(ICAv2AddTenant, self).__init__(command_argv)

        # Initialise parameters
        self.tenant_name: Optional[str] = None

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

        # Check tenant not in config yaml
        if check_tenant_in_config_yaml(self.tenant_name):
            logger.error("Tenant already in icav2.yaml")
            raise CheckArgumentError

    def __call__(self):
        logger.info("Add tenant to icav2.yaml")
        add_tenant_to_config_yaml(self.tenant_name)
