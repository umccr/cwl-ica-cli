#!/usr/bin/env python3

"""
Add an existing category to an existing tool or workflow

Updates workflow.yaml / tool.yaml

Errors if tool / workflow already contains said category

Takes in --tool-name or --workflow-name as possible choices
Takes in --category-name as standard choice
"""

# External imports
import fileinput

# Utils
from ...utils.repo import get_user_yaml_path
from ...utils.errors import UserNotFoundError, ItemDirectoryNotFoundError, MultipleAuthorsError
from ...utils.repo import read_yaml, get_category_yaml_path
from ...utils.logging import get_logger
from ...utils.yaml import dump_yaml
from ...utils.errors import CheckArgumentError, ItemNotFoundError, CategoryNotFoundError

# Classes
from ...classes.command import Command

# Set logger
logger = get_logger()


class AddCategory(Command):
    """
    Add category to an item
    """

    def __init__(self, command_argv, item_yaml_path=None, item_type_key=None, item_type=None):
        # Call super class
        super(AddCategory, self).__init__(command_argv)
        self.item_yaml_path = item_yaml_path
        self.item_type_key = item_type_key
        self.item_type = item_type
        self.name = None  # Name of the item to add the category to
        self.item_obj = None
        self.category = None

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

        # Set item obj
        self.get_item_obj()

        # Check category
        self.check_categories_obj()

        # Set categories list
        self.set_categories_list()

    def __call__(self):
        """
        Run through the required steps
        :return:
        """

        logger.info(f"Updating {self.item_yaml_path.name}")
        self.write_item_yaml()

    def get_item_obj(self):
        """
        Get the item object that matches by name
        :return:
        """
        for item_dict in self.get_item_yaml():
            if item_dict.get("name") == self.name:
                self.item_obj = self.get_item_obj_from_dict(item_dict)
                break
        else:
            logger.error(f"Could not find {self.name} in {self.item_yaml_path}")
            raise ItemNotFoundError

    def get_item_yaml(self):
        """
        Get the item yaml based on yaml path and type key
        :return:
        """
        return read_yaml(self.item_yaml_path)[self.item_type_key]

    def check_categories_obj(self):
        """
        Get the category object
        :return:
        """
        categories_list = read_yaml(get_category_yaml_path())["categories"]
        # Confirm name in categories yaml
        if self.category not in [category_l.get('name') for category_l in categories_list]:
            logger.error(f"Please initialise category '{self.category}' with cwl-ica category-init")
            raise CategoryNotFoundError

    def set_categories_list(self):
        """
        Append the category
        :return:
        """
        # Check category isn't already there
        if self.category in self.item_obj.categories:
            logger.error("Category already exists for this workflow")

        # Setting item category list
        self.item_obj.categories.append(self.category)

    def write_item_yaml(self):
        """
        Write out the item yaml with the additional category
        :return:
        """
        new_items_list = []

        for item in self.get_item_yaml():
            if item.get('name') == self.name:
                new_items_list.append(self.item_obj.to_dict())
            else:
                new_items_list.append(item)

        # Write out project
        with open(self.item_yaml_path, 'w') as item_yaml_h:
            dump_yaml({self.item_type_key: new_items_list}, item_yaml_h)

    @staticmethod
    def get_item_obj_from_dict(item):
        """
        Get item as an object (ItemTool etc.) from an ordered dict.
        Implemented in subclass as subclass defined object type
        :param item:
        :return:
        """
        raise NotImplementedError

    def check_args(self):
        """
        Implemented in subclass
        :return:
        """
        raise NotImplementedError



class AddMaintainer(Command):
    """
    Usage defined in subclass
    """

    def __init__(self, command_argv, item_dir=None, item_type=None):
        # Collect args from doc strings
        super().__init__(command_argv)

        # Initialise each of our parameters
        self.cwl_file_path = None
        self.username = None
        # Get item types
        self.item_dir = item_dir
        self.item_type = item_type

        # Check if help has been called
        if self.args["help"]:
            self._help()

        # Confirm 'required' arguments are present and valid
        try:
            self.check_args()
        except CheckArgumentError:
            self._help(fail=True)

        # Get user object
        self.user_obj = self.get_user_obj()

    def __call__(self):
        """
        Add the 'maintainer' tag
        :return:
        """
        logger.info(f"Updating {self.item_type} '{self.cwl_file_path}' to acknowledge maintainer '{self.username}'")
        self.update_file()
        logger.info(f"Update complete")

    def get_user_obj(self):
        """
        Get the user object from user.yaml
        :return:
        """

        for user in read_yaml(get_user_yaml_path())["users"]:
            if user.get("username") == self.username:
                return user
        logger.error(f"Couldn't find user in {get_user_yaml_path()}")
        raise UserNotFoundError

    def validate_directory(self):
        """
        Confirm file is in the right directory
        :return:
        """
        if self.item_dir not in self.cwl_file_path.parents:
            logger.error(f"Expected to find {self.cwl_file_path} under {self.item_dir}")
            raise ItemDirectoryNotFoundError

    def update_file(self):
        """
        Update the file such that the maintainer user obj goes just under the author

        i.e

        from

        # Metadata
        s:author:
          class: s:Person
          s:name: Alexis Lucattini
          s:email: Alexis.Lucattini@umccr.org
          s:identifier: https://orcid.org/0000-0001-9754-647X

        to

        # Metadata
        s:author:
          class: s:Person
          s:name: Alexis Lucattini
          s:email: Alexis.Lucattini@umccr.org
          s:identifier: https://orcid.org/0000-0001-9754-647X

        s:maintainer:
          class: s:Person
          s:name: New User
          s:email: new.user@email.com
        :return:
        """
        in_authorship = False
        found_authorship = False

        for line in fileinput.input(files=self.cwl_file_path, inplace=True):
            print(line.rstrip())
            if line.strip() == "s:author:":
                if found_authorship:
                    logger.error("Don't know what to do with two authors")
                    raise MultipleAuthorsError
                in_authorship = True
                found_authorship = True
            if in_authorship and line.strip() == "":
                # Make sure we only go through this once
                in_authorship = False
                # Add maintainer
                print("s:maintainer:")
                print("  class: s:Person")
                print(f"  s:name: {self.user_obj.get('username')}")
                print(f"  s:email: {self.user_obj.get('email')}")
                if self.user_obj.get('identifier', None) is not None:
                    print(f"  s:identifier: {self.user_obj.get('identifier')}")
                # Print blank line
                print()

        if not found_authorship:
            logger.error("Could not find 'author' attribute. Cannot add maintainer without author")
            raise UserNotFoundError

    def check_args(self):
        """
        Implemented in subclass
        :return:
        """
        raise NotImplementedError
