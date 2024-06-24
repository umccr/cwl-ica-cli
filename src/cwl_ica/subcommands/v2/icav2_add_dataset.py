#!/usr/bin/env python3

"""
Get the logs of a step

This is entirely the wrong spot for this, but the code was already all here!

"""

# External imports
from datetime import datetime
from itertools import zip_longest
from pathlib import Path
from argparse import ArgumentError
from typing import Optional, List
import os

# Libica
from libica.openapi.v2.model.data import Data

# Wrapica
from wrapica.project_data import get_project_data_obj_by_id, convert_icav2_uri_to_data_obj
from wrapica.project import check_project_has_data_sharing_enabled

# Utils
from ...utils.docopt_helpers import clean_multi_args
from ...utils.icav2_gh_helpers import (
    get_dataset_from_input_yaml,
    is_data_id_format, read_config_yaml
)
from ...utils.logging import get_logger
from ...utils.errors import CheckArgumentError

# Classes
from ...classes.icav2_bunch_classes import Dataset, DatasetItem, DatasetItemFile, DatasetItemFolder
from ...classes.command import Command

# Set logger
logger = get_logger()


class ICAv2AddDataset(Command):
    """Usage:
    cwl-ica [options] icav2-add-dataset help
    cwl-ica [options] icav2-add-dataset [--tenant-name=<tenant_name>]
                                        [--input-yaml=<input_yaml>]
                                        [--dataset-name=<dataset_name>]
                                        [--dataset-description=<description>]
                                        [--username=<username>]
                                        [--data=<data>]...
                                        [--data-uri=<data_uri>]...
                                        [--data-id=<data_id>]...
                                        [--project-id=<project_id>]...


Description:
    Add a dataset to icav2 configurations file.
    The dataset can then be added to bunches.

    The input yaml has the following keys:
      * tenant_name: <str> Name of the tenant
      * dataset_name: <str> Name of the dataset
      * description: <str> A short description of the data.
      * data: <List>
        * Each element in data is either a string (like a URI)
        * Or a key, value pair where the key is one of 'data', 'data_id' or 'data_uri'
        * If a data id is specified, a project ID must also be specified with the project_id key.
        * Data URIs must be in one of the following formats
          - icav2://<project_id>/path/to/data
          - icav2://<project_name>/path/to/data

    Dataset name, description and data can also be specified on the commandline.

    In the case both an input-yaml is specified and data is specified on the commandline, both will be added.

    A dataset is designed to be 'completely immutable'. Any modification to files or folders of existing datasets will
    render the dataset useless.
    It is for this reason that one should make datasets in very small units.
    Bunch versions can use a list of datasets.

    For each dataset, the following attributes will be stored (for reproducibility purposes).
    * dataset_tenant_name (the name of the tenant)
    * dataset_name (the name you have chosen for the dataset)
    * dataset_description (the short description you have provided)
    * cwl_username (your cwl-ica username)
    * dataset_region_id
    * dataset_region_city_name
    * dataset_creation_time (current UTC time)
    * dataset_id_hash (md5sum of data ids present in the dataset (sorted by data id)).

    For each data item, the following attributes will be stored (for reproducibility purposes)
    Plus data_type specific attributes.
    * data_id
    * owning_project_id
    * owning_project_name
    * data_uri  (icav2://project-name/path/to/data)
    * creation_time (time data was created)
    * modification_time (time data was modified)
    * creator_id (the id of the data creator)
    * creator_name (the id of the data user)
    * data_type (one of FILE or FOLDER)

    FILES ONLY
    * file_size_in_bytes
    * object_e_tag

    FOLDERS ONLY
    * num_files (number of files in folder - recursively)
    * folder_size_in_bytes (sum of file_size_in_bytes for all files in the directory)
    * object_e_tag_md5sum (md5sum of the object_e_tag list (sorted by file path))
    * folder_structure_md5sum (md5sum of the folder structure (sorted by file path))


Options:
    --tenant-name=<tenant_name>           Required: The name of the tenant
    --input-yaml=<input_yaml>             Optional: The path to the input yaml that contains the dataset information.
    --dataset-name=<dataset_name>         Optional: The name of the dataset (can also be set in the input yaml)
    --dataset-description=<description>   Optional: A description of the dataset (can also be set in the input yaml)
    --username=<username>                 Optional: Your CWL-ICA username (assume CWL_ICA_DEFAULT_USER is in env var)
    --data=<data>                         Optional: Specify data as a list of data ids or uris
    --data-uri=<data_uri>                 Optional: Specify data as a list of uris
    --data-id=<data_id>                   Optional: Specify data as a list of data ids.
    --project-id=<project_id>             Optional: Required if using --data-id endpoint (must match the same order as data-id).


Environment:
    ICAV2_ACCESS_TOKEN (required)
    ICAV2_BASE_URL (optional, defaults to ica.illumina.com)
    ICAV2_PROJECT_ID (optional)
    CWL_ICA_DEFAULT_USER  (optional, should be set if in cwl-ica conda env)


Example:
    cwl-ica icav2-add-dataset --input-yaml dataset.yaml
    """

    def __init__(self, command_argv):

        # Collect args from doc strings
        super(ICAv2AddDataset, self).__init__(command_argv)

        # Initialise parameters
        self.dataset_name: Optional[str] = None
        self.dataset_description: Optional[str] = None
        self.username: Optional[str] = None
        self.tenant_name: Optional[str] = None
        self.input_yaml: Optional[Path] = None
        self.data_list_obj: Optional[List[Data]] = None
        self.creation_time: Optional[datetime] = None
        self.dataset_items: Optional[List[DatasetItem]] = None

        # Dataset class
        self.dataset: Optional[Dataset] = None

        # Check if help has been called
        if self.args["help"]:
            self._help()

        # Because were using 'multi' args need to run check_multi_args
        self.args = clean_multi_args(self.args, self.__doc__, use_dual_options=False)

        # Confirm 'required' arguments are present and valid
        try:
            logger.debug("Checking args")
            self.check_args()
        except ArgumentError:
            self._help(fail=True)

    def check_args(self):
        # Get tenant name
        self.tenant_name = self.args.get("--tenant-name", None)
        if self.tenant_name is None:
            logger.error(f"Please use --tenant-name parameter")
            raise CheckArgumentError

        # Check if input yaml is provided
        input_yaml_arg: str | None = self.args.get("--input-yaml", None)
        if input_yaml_arg is not None:
            if not Path(input_yaml_arg).is_file():
                logger.error(f"Could not find file --input-yaml '{input_yaml_arg}'")
                raise CheckArgumentError
            self.input_yaml = Path(input_yaml_arg)

        # Get input yaml objects
        if self.input_yaml is not None:
            self.dataset_name, self.dataset_description, self.data_list_obj = (
                get_dataset_from_input_yaml(self.input_yaml)
            )
        else:
            self.data_list_obj = []

        # Try get name from the cli
        dataset_name_arg = self.args.get("--dataset-name", None)
        if dataset_name_arg is not None:
            self.dataset_name = dataset_name_arg

        # Check that dataset_name is defined
        if self.dataset_name is None:
            logger.error("Please specify --dataset-name on the cli or use the name key in the input yaml")
            raise CheckArgumentError

        # Try get description from CLI
        dataset_description_arg = self.args.get("--dataset-description", None)
        if dataset_description_arg is not None:
            self.dataset_description = dataset_description_arg

        # Check that dataset_description is defined
        if self.dataset_description is None:
            logger.error("Please specify --dataset-description on the cli or use the name key in the input yaml")
            raise CheckArgumentError

        # Get username from cli or env
        username_arg = self.args.get("--username", None)
        if username_arg is not None:
            self.username = username_arg
        # Check env
        elif os.environ.get("CWL_ICA_DEFAULT_USER", None) is not None:
            self.username = os.environ.get("CWL_ICA_DEFAULT_USER")
        # Raise error
        else:
            logger.error("Please specify username with --username or set the default user with cwl-ica set-default-user")
            raise CheckArgumentError

        # Check dataset name is not already in the dataset config
        config = read_config_yaml()
        if config is not None:
            datasets = config.get("datasets", None)
            dataset_names_list = list(map(lambda dataset: dataset.get("dataset_name", None), datasets))
            if datasets is not None and self.dataset_name in dataset_names_list:
                logger.error("Dataset name already in icav2.yaml")
                raise CheckArgumentError

        project_id_arg_list: List | None = self.args.get("--project-id", None)
        data_id_arg_list: List | None = self.args.get("--data-id", None)

        if data_id_arg_list is not None:
            # Check project id is specified if data id is specified on cli
            if project_id_arg_list is None:
                logger.error("Cannot specify --data-id without also specifying --project-id")
                raise CheckArgumentError

            # If project id list is specified, it can be just one project id, but if multiple, it must match
            # the length of the data ids.
            if not len(project_id_arg_list) == 1 and not len(project_id_arg_list) == len(data_id_arg_list):
                logger.error("Please either specify --project-id just once or as many times as --data-id is specified")
                raise CheckArgumentError

            # Get data parameter list
            for project_id_arg, data_id_arg in zip_longest(project_id_arg_list, data_id_arg_list):
                self.data_list_obj.append(get_project_data_obj_by_id(project_id_arg, data_id_arg))

        # Check uri list
        for data_uri_arg in self.args.get("--data-uri"):
            self.data_list_obj.append(convert_icav2_uri_to_data_obj(data_uri_arg))

        # Check generic --data arg
        for index_arg, data_arg in enumerate(self.args.get("--data")):
            if is_data_id_format(data_arg):
                if not len(project_id_arg_list) == 1 and not len(project_id_arg_list) == len(self.args.get("--data")):
                    logger.error(
                        "Please either specify --project-id just once or as many times as --data is specified")
                    raise CheckArgumentError
                if len(project_id_arg_list) == 1:
                    self.data_list_obj.append(get_project_data_obj_by_id(project_id_arg_list[0], data_arg))
                else:
                    self.data_list_obj.append(get_project_data_obj_by_id(project_id_arg_list[index_arg], data_arg))
            else:
                self.data_list_obj.append(convert_icav2_uri_to_data_obj(data_arg))

        # Convert data objects to dataset items
        self.dataset_items: List[DatasetItem] = [
            DatasetItemFile(
                create=True,
                data_obj=data_obj,
            )
            if data_obj.data.details.data_type == "FILE"
            else
            DatasetItemFolder(
                create=True,
                data_obj=data_obj,
            )
            for data_obj in self.data_list_obj
        ]

        # Project
        data_project_ids = list(
            map(
                lambda dataset_item: dataset_item.owning_project_id,
                self.dataset_items
            )
        )

        for project_id in data_project_ids:
            if not check_project_has_data_sharing_enabled(project_id):
                logger.error(f"Project {project_id} does not have data sharing enabled")
                raise CheckArgumentError

        # Make dataset as a class
        self.dataset = Dataset(
            dataset_name=self.dataset_name,
            dataset_description=self.dataset_description,
            username=self.username,
            tenant_name=self.tenant_name,
            create=True,
            dataset_items=self.dataset_items,
            data_objs=self.data_list_obj,
            dataset_creation_time=None,
            region_obj=None,
            dataset_id_hash=None,
        )

    def __call__(self):
        logger.info("Writing dataset to config")
        self.dataset.to_v2_config_yaml()
