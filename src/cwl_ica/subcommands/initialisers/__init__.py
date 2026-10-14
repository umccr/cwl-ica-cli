#!/usr/bin/env python3

"""
Call is subclass dependent
For all this means creating the item in the .yaml file

Historically tool-init / workflow-init also registered the item onto ICA projects via ICAv1.
ICAv1 has been deprecated, so initialisers now only write the item into the relevant config
yaml (tool.yaml / workflow.yaml / expression.yaml / schema.yaml).
"""

# External imports
from ruamel.yaml import YAML
from pathlib import Path

# Utils
from ...utils.logging import get_logger
from ...utils.repo import read_yaml
from ...utils.yaml import dump_yaml
from ...utils.errors import (
    CheckArgumentError,
    ItemVersionExistsError, ItemDirectoryNotFoundError
)

# Classes
from ...classes.command import Command


# Set logger
logger = get_logger()


class Initialiser(Command):
    """
    The initialiser is based over two parts
    * Initialise cwl object and import it / validate it -> most components defined in the subclass
    * Import the categories yaml object, check categories are registered -> method created here, called in subclass

    The call is then defined in this class
    """

    def __init__(
            self,
            command_argv,
            item_dir=None,
            item_yaml_path=None,
            item_type_key=None,
            item_type=None,
            item_suffix="cwl"
    ):
        # Call super class
        super(Initialiser, self).__init__(command_argv)

        # CWL Object has a suite of basic uses such as the
        self.cwl_obj = None
        self.md5sum = None  # Part of the cwl_obj but different calculation for cwl-schema objects
        # We will have a name and a version for this tool/expression/workflow etc.
        self.name = None
        self.version = None
        self.cwl_file_path = None
        # Also assign the type in the subclass so this can be referenced in the call
        self.item_dir = item_dir
        self.item_type_key = item_type_key  # tools / workflows etc
        self.item_type = item_type  # tool / workflow
        self.item_yaml_path = item_yaml_path
        self.item_suffix = item_suffix
        # We will also store the item list yaml for re-writing
        self.items_list = None
        self.item = None
        self.item_version = None
        # Categories
        self.categories = []  # List of category objects
        self.categories_list = None  # str list of categories

        # Check help
        self.check_length(command_argv)

        # Check if help has been called
        if self.args["help"]:
            self._help()

        # Confirm 'required' arguments are present and valid
        try:
            self.check_args()
        except CheckArgumentError:
            self._help(fail=True)

        # Steps in subclass
        # Check args
        # Get args
        # Read in tool.yaml / workflow.yaml / etc as object
        if not Path(self.item_yaml_path).is_file():
            self.items_list = []
        else:
            self.items_list = read_yaml(self.item_yaml_path)[self.item_type_key]
        # Get item -> Check version is not the same
        self.item = self.get_item_from_item_list()

        if self.item is None:
            self.item = self.create_item_object()
            self.item_version = self.item.versions[0]
            self.add_item_to_items_list()
        else:
            self.check_unique_version()
            self.item_version = self.create_item_version_object()
            # We need to create the item version
            self.add_item_version_to_item()
            # Extend categories list with existing categories
            if self.item_type in ["tool", "workflow"]:
                self.categories = list(set(self.categories + self.item.categories))

        # Update cwl_obj and md5sum attributes
        self.cwl_obj = self.item_version.cwl_obj
        self.md5sum = self.item_version.md5sum

    def __call__(self):
        """
        Writes the item to the item yaml
        * tool.yaml, expression.yaml, workflow.yaml and schema.yaml all follow the same conventions
          with the exception of categories in tools and workflows
        :return:
        """
        # Write out the item yaml
        logger.info(f"Updating \"{self.get_item_yaml()}\"")
        self.write_item_yaml()

    # Methods implemented in subclass
    def check_args(self):
        """
        Implemented in subclass
        :return:
        """
        raise NotImplementedError

    def create_item_object(self):
        """
        This creates the item object along with the first version of the item
        This also calls create_item_version and assigns item_version attribute
        :return:
        """
        raise NotImplementedError

    def create_item_version_object(self):
        """
        Create the item version for self.item and assign to item_version
        :return:
        """
        raise NotImplementedError

    def set_cwl_obj(self):
        """
        Get the CWL workflow, assign to cwl_obj, implemented in subclass
        :return:
        """
        self.cwl_obj = self.item_version.cwl_obj
        self.md5sum = self.item_version.md5sum

    @staticmethod
    def get_item_obj_from_dict(item):
        """
        Get item as an object (ItemTool etc.) from an ordered dict.
        :param item:
        :return:
        """
        raise NotImplementedError

    def get_item_yaml(self):
        """
        returns tool.yaml / workflow.yaml, global redefined in subclass
        :return:
        """
        return self.item_yaml_path

    def get_item_from_item_list(self):
        """
        Item will contain a name / version. Iterate through item list and then call
        the get_item_obj_from_dict method that is unique to this item class (and implemented in the subclass)
        :return:
        """
        for item in self.items_list:
            if item.get("name", None) == self.name:
                return self.get_item_obj_from_dict(item)
        else:
            return None

    def check_cwl_path(self, cwl_path):
        """
        Check that the cwl path exists under item_dir
        :return:
        """
        # Check path is relative to item path
        if not cwl_path.absolute().resolve().relative_to(self.item_dir):
            logger.error(f"Expected item of type \"{self.item_type}\" to be in \"{self.item_dir}\"")
            raise ItemDirectoryNotFoundError

    def check_unique_version(self):
        """
        Check there's no overlapping unique version
        :return:
        """
        for version in self.item.versions:
            if version.name == self.version:
                logger.error(f"Version already exists in \"{self.item_type}.yaml\"")
                raise ItemVersionExistsError

    def set_name_and_version_from_file_path(self):
        """
        Sets the name and version attributes from the path attribute
        :return:
        """
        self.name, self.version = self.cwl_file_path.resolve().stem.split("__")

    def set_categories_list(self):
        """
        Sets the list of categories
        :return:
        """
        categories_arg = self.args.get("--categories")
        if categories_arg is not None:
            # Categories
            self.categories_list = categories_arg.split(",")  # str list of categories
        else:
            self.categories_list = []

    def read_item_yaml(self):
        """
        Read an item.yaml like tool.yaml or workflow.yaml
        :return:
        """
        yaml = YAML()

        with open(self.get_item_yaml(), 'r') as item_yaml_h:
            self.items_list = yaml.load(item_yaml_h)[self.item_type_key]

    def add_item_to_items_list(self):
        """
        Add the cwl obj item yaml to workflow.yaml or tool.yaml etc
        :return:
        """
        self.items_list.append(self.item.to_dict())

    def add_item_version_to_item(self):
        """
        Add an item version to an item
        :return:
        """
        self.item.versions.append(self.item_version.to_dict())

    def write_item_yaml(self):
        """
        Mostly static method
        :return:
        """

        # Check if we have any tools registered
        if not Path(self.get_item_yaml()).is_file():
            all_items_list = []
        else:
            all_items_list = read_yaml(self.get_item_yaml())[self.item_type_key]

        new_all_items_list = [item.copy() for item in all_items_list]

        for i, item in enumerate(all_items_list):
            if item.get("name") == self.name:
                new_all_items_list[i] = self.item.to_dict()
                break
        else:
            new_all_items_list.append(self.item.to_dict())

        with open(self.get_item_yaml(), "w") as item_yaml_h:
            dump_yaml({self.item_type_key: new_all_items_list}, item_yaml_h)
