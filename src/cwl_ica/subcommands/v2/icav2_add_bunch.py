#!/usr/bin/env python3

"""
Get the logs of a step

This is entirely the wrong spot for this, but the code was already all here!

"""
# External imports
import os
from pathlib import Path
from ruamel.yaml import CommentedSeq
from argparse import ArgumentError
from typing import Optional, List, Dict, Union, Type

# Wrapica imports
from wrapica.region import get_regions

# Utils
from ...utils.icav2_gh_helpers import (
    get_bunch_attributes_from_input_yaml, get_bunch_names,
    get_bunch_from_bunch_name,
    read_config_yaml, write_config_yaml
)
from ...utils.logging import get_logger
from ...utils.errors import CheckArgumentError

# Classes
from ...classes.icav2_bunch_classes import Bunch
from ...classes.command import Command
from ...utils.repo import get_cwl_ica_repo_path

# Set logger
logger = get_logger()


class ICAv2AddBunch(Command):
    """Usage:
    cwl-ica [options] icav2-add-bunch help
    cwl-ica [options] icav2-add-bunch [--input-yaml=<input_yaml>]
                                      [--tenant-name=<tenant_name>]
                                      [--bunch-name=<bunch_name>]
                                      [--bunch-description=<bunch_description>]
                                      [--bunch-region-id=<bunch_region_id>]
                                      [--bunch-region-city-name=<bunch_city_name>]
                                      [--pipeline-project-name=<project_name>]
                                      [--workflow-path=<workflow_path>]
                                      [--username=<username>]
                                      [--project=<project_name]...
                                      [--category=<category>]...

Description:
    Create a bunch.
    A bunch is a workflow plus the projects and categories the workflow pipeline is to be linked to.

    The input yaml has the following keys:
      * tenant_name: <str>  The name of the tenant that the bunch belongs to
      * bunch_name: <str> Name of the bunch
      * bunch_description: <str> A short description of the bunch.
      * bunch_region_id | bunch_region_city_name: <str> The region the bunch resides in
      * workflow_path: <str> The relative workflow path
      * pipeline_project_name: <str> The project where the pipeline is pushed to
      * projects: <List[Project]> List of projects to push the pipeline to
        * - project_name: ""  # Must match project_name in projects icav2 configuration file.
      * categories: <List[category]> List of categories to specify for the pipeline.
        * - category

    A bunch will store the following metadata in the icav2 config yaml file:
    * bunch_name: <str> Name of the bunch
    * workflow_path: <str> The relative workflow path
    * pipeline_project_name: <str> The project name to push the bunch to
    * bunch_region_id: <str> The region id that this bunch belongs to
    * bunch_region_city_name: <str> The region city name that this bunch belongs to

    If a bunch with the same name already exists in the icav2 config yaml file, it is left unchanged.

    If an attribute is defined on the CLI AND in the input.yaml, the attribute on the CLI will take preference.
    In the event, the said attribute is an array, the attribute will be a union of the CLI and input yaml attributes.

    When the pipeline is generated via GitHub actions, if two bunches have the same workflow path and the same pipeline project, they will share a pipeline id.

Options:
    --input-yaml=<input_yaml>                                Optional: The path to the input yaml used to generate a bunch.

    The following parameters are required via either the input-yaml OR via the CLI:
    --tenant-name=<tenant_name>                              Optional: The name of the tenant.
    --bunch-name=<bunch_name>                                Optional: The name of the bunch.

    The following parameters are required via either the input-yaml OR via the CLI if this is a new bunch:
    --bunch-description=<bunch_description>                  Optional: A short description of the bunch.
    --bunch-region-id=<bunch_region_id>                      Optional: The region id (or use bunch_region_city_name), only required if multiple regions available
    --bunch-region-city-name=<bunch_region_city_name>        Optional: The region city name (or use bunch_region_id), only required if multiple regions available
    --pipeline-project-name=<pipeline_project_name>          Optional: The name of the project you wish to push the pipeline to.
    --workflow-path=<workflow_path>                          Optional: The path to the workflow
    --project=<project>                                      Optional: Projects to link the pipeline to, specify multiple times for multiple projects.
    --category=<category>                                    Optional: Category to add to the pipeline, specify multiple times for multiple categories
    --username=<username>                                    Optional: The cwl-ica username (assume CWL_ICA_DEFAULT_USER is in env var)

Environment:
    CWL_ICA_DEFAULT_USER  Optional, should be set if in cwl-ica conda env
    ICAV2_BASE_URL        Required for validating regions
    ICAV2_ACCESS_TOKEN    Required for validating regions

Example:
    cwl-ica icav2-add-bunch --input-yaml /path/to/input.yaml
    """

    def __init__(self, command_argv):

        # Collect args from doc strings
        super(ICAv2AddBunch, self).__init__(command_argv)

        # Initialise parameters
        self.tenant_name: Optional[str] = None
        self.bunch_name: Optional[str] = None
        self.bunch_description: Optional[str] = None
        self.pipeline_project_name: Optional[str] = None
        self.workflow_path: Optional[Path] = None
        self.bunch_region_id: Optional[str] = None
        self.bunch_region_city_name: Optional[str] = None
        self.username: Optional[str] = None
        self.project_list: Optional[str] = None
        self.category_list: Optional[str] = None

        self.bunch: Optional[Bunch] = None

        # Check if help has been called
        if self.args["help"]:
            self._help()

        # Confirm 'required' arguments are present and valid
        try:
            logger.debug("Checking args")
            self.check_args()
        except ArgumentError:
            self._help(fail=True)

    def check_arg_in_input_yaml_and_cli(
            self,
            arg_name: str,
            input_yaml_data: Dict,
            required: False,
            arg_type: Union[Type[str] | Type[List] | Type[Path]],
            attr_name: Optional[str] = None,
            yaml_key: Optional[str] = None,
            env=None
    ):
        """
        For a given argument, check that it's been specified either on the cli or in the input yaml
        :param env:
        :param yaml_key:
        :param arg_name:
        :param required:
        :param arg_type:
        :param input_yaml_data:
        :param attr_name:
        :return:
        """
        # Now iterate over other arguments and append / add to items
        arg_value = self.args.get(arg_name, None)
        if attr_name is None:
            attr_name = arg_name.lstrip("-").replace("-", "_")
        if yaml_key is None:
            yaml_key = attr_name

        if arg_value is None and env is not None:
            arg_value = os.environ.get(env, None)

        # Work on strings first
        if arg_type in [str, Path]:
            # Check if in cli
            if arg_value is not None:
                pass
            # Or in yaml
            elif yaml_key in input_yaml_data.keys():
                arg_value = input_yaml_data[yaml_key]
            # Bad news if we get to here and not specified yet
            elif required:
                logger.error(f"{arg_name} not specified in the input yaml or on the CLI")
                raise CheckArgumentError

            if arg_value is None:
                # Don't cast None type to string
                return

            # Cast from string to Path if need be
            if not isinstance(arg_value, arg_type):
                arg_value = arg_type(arg_value)

            self.__setattr__(attr_name, arg_value)
            return

        if arg_type == List:
            # Append if in both
            values_in_yaml_and_cli = []

            if arg_value is not None:
                values_in_yaml_and_cli.extend(arg_value)

            if yaml_key in input_yaml_data.keys():
                values_in_yaml_and_cli.extend(input_yaml_data.get(yaml_key))

            if required and len(values_in_yaml_and_cli) == 0:
                logger.error(f"{arg_name} not specified in the input yaml or on the CLI")
                raise CheckArgumentError

            self.__setattr__(attr_name, values_in_yaml_and_cli)

    def set_bunch_region_attributes(self):
        regions_list = get_regions()

        if self.bunch_region_id is None and self.bunch_region_city_name is None:

            # Check we only have one region
            if not len(regions_list) == 1:
                logger.error("Neither --bunch-region-id or --bunch-region-city-name were specified.")
                raise CheckArgumentError

            self.bunch_region_id = regions_list[0].id
            self.bunch_region_city_name = regions_list[0].city_name

        if self.bunch_region_city_name is None:
            try:
                region_obj = next(
                    filter(
                        lambda region: region.id == self.bunch_region_id,
                        regions_list
                    )
                )

                self.bunch_region_city_name = region_obj.city_name
            except StopIteration:
                logger.error(f"Could not find region that matches id {self.bunch_region_id}")
                raise CheckArgumentError

        if self.bunch_region_id is None:
            try:
                region_obj = next(
                    filter(
                        lambda region: region.city_name == self.bunch_region_city_name,
                        regions_list
                    )
                )

                self.bunch_region_id = region_obj.id
            except StopIteration:
                logger.error(f"Could not find region that matches id {self.bunch_region_id}")
                raise CheckArgumentError

    def check_args(self):
        # Check if input yaml is provided
        input_yaml_arg = self.args.get("--input-yaml", None)
        if input_yaml_arg is not None:
            if not Path(input_yaml_arg).is_file():
                logger.error(f"Could not find file --input-yaml '{input_yaml_arg}'")
                raise CheckArgumentError
            input_yaml_path = Path(input_yaml_arg)
        else:
            input_yaml_path = None
        # Get bunch attributes from input yaml
        if input_yaml_path is not None:
            input_yaml_data = get_bunch_attributes_from_input_yaml(input_yaml_path)
        else:
            input_yaml_data = {}

        # Go through the rest of the arguments
        self.check_arg_in_input_yaml_and_cli(
            "--tenant-name",
            input_yaml_data,
            required=True,
            arg_type=str
        )

        # Go through the rest of the arguments
        self.check_arg_in_input_yaml_and_cli(
            "--bunch-name",
            input_yaml_data,
            required=True,
            arg_type=str
        )

        self.check_arg_in_input_yaml_and_cli(
            "--bunch-description",
            input_yaml_data,
            required=False,
            arg_type=str
        )

        self.check_arg_in_input_yaml_and_cli(
            "--bunch-region-id",
            input_yaml_data,
            required=False,
            arg_type=str
        )

        self.check_arg_in_input_yaml_and_cli(
            "--bunch-region-city-name",
            input_yaml_data,
            required=False,
            arg_type=str
        )

        self.check_arg_in_input_yaml_and_cli(
            "--pipeline-project-name",
            input_yaml_data,
            required=True,
            arg_type=str
        )

        self.check_arg_in_input_yaml_and_cli(
            "--workflow-path",
            input_yaml_data,
            required=True,
            arg_type=Path,
        )

        self.check_arg_in_input_yaml_and_cli(
            "--username",
            input_yaml_data,
            required=True,
            arg_type=str,
            env="CWL_ICA_DEFAULT_USER"
        )

        self.check_arg_in_input_yaml_and_cli(
            "--project",
            input_yaml_data,
            required=True,
            arg_type=List,
            attr_name="project_list",
            yaml_key="projects"
        )

        self.check_arg_in_input_yaml_and_cli(
            "--category",
            input_yaml_data,
            required=True,
            arg_type=List,
            attr_name="category_list",
            yaml_key="categories"
        )

        if self.bunch_region_id is None or self.bunch_region_city_name is None:
            self.set_bunch_region_attributes()

        # Determine if this is an existing bunch
        if self.bunch_name in get_bunch_names():
            # Iterate over bunch name
            self.bunch = get_bunch_from_bunch_name(self.bunch_name)
            logger.warning(f"Bunch {self.bunch_name} already exists, leaving it unchanged")

        else:
            # Ensure the following parameters exist
            bunch_parent_attributes = [
                "bunch_description",
                "bunch_region_id",
                "bunch_region_city_name",
                "pipeline_project_name",
                "workflow_path",
                "project_list",
                "category_list"
            ]

            # Iterate over each attribute to check
            for bunch_parent_attribute in bunch_parent_attributes:
                if self.__getattribute__(bunch_parent_attribute) is None:
                    logger.error(f"Please specify {bunch_parent_attribute} via either input-yaml or CLI")
                    raise CheckArgumentError

            # Check projects are valid
            if self.project_list is not None:
                registered_project_list = list(
                    map(
                        lambda project_iter: project_iter.get("project_name"),
                        read_config_yaml().get("projects")
                    )
                )
                for project in self.project_list:
                    if project not in registered_project_list:
                        logger.error(f"Cannot create bunch, project {project} is not the available project list")
                        raise CheckArgumentError

            # Generate bunch object
            self.bunch = Bunch(
                create=True,
                bunch_name=self.bunch_name,
                bunch_description=self.bunch_description,
                tenant_name=self.tenant_name,
                pipeline_path=self.workflow_path.absolute().resolve().relative_to(get_cwl_ica_repo_path()),
                pipeline_project_name=self.pipeline_project_name,
                bunch_region_id=self.bunch_region_id,
                bunch_region_city_name=self.bunch_region_city_name,
                projects=self.project_list,
                categories=self.category_list,
            )

    def __call__(self):
        logger.info("Writing bunch to icav2.yaml")
        config_data = read_config_yaml()

        if config_data.get("bunches") is None:
            config_data["bunches"] = CommentedSeq()
            config_data.yaml_set_comment_before_after_key(
                key="bunches",
                before="\nList of bunches\n"
            )

        config_data.yaml_set_comment_before_after_key(
            key="bunches",
            after="\n"
        )

        bunch_list = config_data.get("bunches")
        index_to_update = -1

        # Iterate bunch dict to update
        for index, bunch_dict_iter in enumerate(bunch_list):
            if bunch_dict_iter.get("bunch_name") == self.bunch_name:
                index_to_update = index
                break

        # Update or make a new bunch dict
        if index_to_update == -1:
            bunch_list.append(self.bunch.to_dict())
        else:
            bunch_list[index_to_update] = self.bunch.to_dict()

        config_data["bunches"] = bunch_list

        write_config_yaml(config_data)
