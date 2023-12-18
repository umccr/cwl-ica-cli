#!/usr/bin/env python3

"""
Add an existing category to an existing tool or workflow

Updates the workflow object across projects on ICA with the additional category

Updates workflow.yaml / tool.yaml

Errors if tool / workflow already contains said category

Takes in --tool-name or --workflow-name as possible choices
Takes in --category-name as standard choice
"""

# External imports
from ruamel.yaml import YAML
import fileinput

# Utils
from ...utils.errors import ItemVersionNotFoundError, WorkflowVersionExistsError
from ...utils.repo import get_user_yaml_path
from ...utils.errors import UserNotFoundError, ItemDirectoryNotFoundError, MultipleAuthorsError
from ...utils.repo import read_yaml, get_project_yaml_path, get_category_yaml_path
from ...utils.logging import get_logger
from ...utils.yaml import dump_yaml
from ...utils.errors import CheckArgumentError, ItemNotFoundError, CategoryNotFoundError

# Classes
from ...classes.command import Command
from ...classes.project import Project
from ...classes.project_production import ProductionProject

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
        self.projects_list = []

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

        # Get project item name
        self.get_projects_from_item_name()

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

        # Update each of the workflows for each of the projects
        if len(self.projects_list) > 0:
            logger.info(f"Updating {self.item_type_key} on projects")
            self.update_projects()

    def get_project_ica_item_list(self, project):
        """
        Get ica_tools_list or ica_workflows_list
        :return:
        """
        if self.item_type_key == "tools":
            return project.ica_tools_list
        elif self.item_type_key == "workflows":
            return project.ica_workflows_list
        else:
            logger.error(f"Don't support this item type {self.item_type_key}")
            raise ItemNotFoundError

    def get_projects_from_item_name(self):
        """
        Return projects that contain said workflow
        :return:
        """

        # Check if name matches --tool-name or --workflow-name
        # Add project to list
        projects_list = read_yaml(get_project_yaml_path())["projects"]
        for project_dict in projects_list:
            # Read in project
            if project_dict.get("production"):
                project = ProductionProject.from_dict(project_dict)
            else:
                project = Project.from_dict(project_dict)
            # Get item type
            project_ica_item_list = self.get_project_ica_item_list(project)
            # Get project item list
            for project_ica_item in project_ica_item_list:
                if project_ica_item.name == self.name:
                    self.projects_list.append(project)
                    continue

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

    def update_projects(self):
        """
        Sync workflows for each project with the new category attribute
        :return:
        """
        # Iterate through projects list
        for project in self.projects_list:
            # Get Project ICA item list
            project_ica_item_list = self.get_project_ica_item_list(project)
            # Iterate through item list
            for ica_item in project_ica_item_list:
                if ica_item.name == self.name:
                    # Sync workflow
                    logger.info(f"Updating workflow ID {ica_item.ica_workflow_id} on project {project.project_name}")
                    ica_item.update_ica_workflow_item(
                        access_token=project.get_project_token(),
                        categories=self.item_obj.categories
                    )

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



class AddToProject(Command):
    """
    Add an item to a project

    This calls very similar functions to initialiser but assumes that item already exists in 'item.yaml'
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
        super(AddToProject, self).__init__(command_argv)

        # CWL Object has a suite of basic uses such as the
        self.cwl_obj = None
        self.md5sum = None  # Part of the cwl_obj but different calculation for cwl-schema objects
        # We will have a name and a version for this tool/expression/workflow etc.
        self.name = None
        self.version = None
        self.cwl_file_path = None
        # Also assign the type in the subclass so this can be referenced in the call
        self.item_dir = item_dir
        self.item_yaml_path = item_yaml_path
        self.item_type = item_type  # tool / workflow
        self.item_type_key = item_type_key  # tools / workflows etc
        self.item_suffix = item_suffix
        # We will also store the item list yaml for re-writing
        self.items_list = None
        self.item = None
        self.item_version = None
        # Project
        self.project = None  # Project object

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
        self.read_item_yaml()

        # Get item -> make sure item is not none
        self.item = self.get_item_from_item_list()

        if self.item is None:
            logger.error(f"Could not find item with name \"{self.name}\" in \"{self.get_item_yaml()}\"")
            raise ItemNotFoundError

        # Get version -> Check match -> Make sure version is not none
        self.item_version = self.get_item_version_from_item()

        if self.item_version is None:
            logger.error(f"Could not find item version in item \"{self.name}\" with version \"{self.version}\"")
            raise ItemVersionNotFoundError

        # Check item version is not in project
        for ica_workflow in self.get_project_ica_item_list():
            if ica_workflow.name == self.name:
                for version in ica_workflow.versions:
                    if version.name == self.version:
                        logger.error("This workflow already exists in this project")
                        raise WorkflowVersionExistsError

    def __call__(self):
        """
        Add the tool / workflow to the project
        :return:
        """
        # Call the item version to set the cwl object
        self.item_version()
        self.cwl_obj = self.item_version.cwl_obj

        # Add item to project
        logger.info(
            f"Adding {self.item_type} \"{self.name}/{self.version}\" to project \"{self.project.project_name}\""
        )
        self.project.add_item_to_project(self.item_type_key, self.cwl_obj,
                                         access_token=self.project.get_project_token(),
                                         categories=self.item.categories)

        # Now we need to write the projects yaml with the new workflow / version added
        logger.info("Updating project yaml")
        self.write_projects_yaml()

    # Get the item
    def get_item_yaml(self):
        """
        returns tool.yaml / workflow.yaml, global redefined in subclass
        :return:
        """
        return self.item_yaml_path

    def read_item_yaml(self):
        """
        Read an item.yaml like tool.yaml or workflow.yaml
        :return:
        """
        yaml = YAML()

        with open(self.get_item_yaml(), 'r') as item_yaml_h:
            self.items_list = yaml.load(item_yaml_h)[self.item_type_key]

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

    # Get the item version
    def get_item_version_from_item(self):
        """
        Iterate through the versions of the item and return the version object that matches.
        Since the version is a sub-object of the item object, any updates to item_version will update item
        :return:
        """
        for version in self.item.versions:
            if version.name == self.version:
                return version
        return None

    def set_name_and_version_from_file_path(self):
        """
        Sets the name and version attributes from the path attribute
        :return:
        """
        self.name, self.version = self.cwl_file_path.absolute().relative_to(self.item_dir).stem.split("__")

    # Methods implemented in subclass
    @staticmethod
    def get_item_obj_from_dict(item):
        """
        Get item as an object (ItemTool etc.) from an ordered dict.
        Implemented in subclass as subclass defined object type
        :param item:
        :return:
        """
        raise NotImplementedError

    def get_project_ica_item_list(self):
        """
        Get the project ica item list through projects' either ica_tools_list or ica_workflows_list
        :return:
        """
        raise NotImplementedError

    def check_args(self):
        """
        Implemented in subclass
        :return:
        """
        raise NotImplementedError

    def check_project(self, project_arg):
        """
        Checks project attribute is in projects yaml
        :return:
        """

        projects_list = read_yaml(get_project_yaml_path())["projects"]

        for project_dict in projects_list:
            # Not the right project, skip it
            if not project_dict.get("project_name", None) == project_arg:
                continue

            # Check production
            if project_dict.get("production", False):
                self.project = ProductionProject.from_dict(project_dict)
            else:
                self.project = Project.from_dict(project_dict)

            # Got project, break loop
            break

        else:
            logger.error(f"Could not find project \"{self.project}\" in project.yaml. "
                         f"Please first run 'cwl-ica project-init' for this project")

    def write_projects_yaml(self):
        """
        Re-write projects dictionary
        :return:
        """

        all_projects_list = read_yaml(get_project_yaml_path())['projects']
        new_all_projects_list = all_projects_list.copy()

        for i, project_dict in enumerate(all_projects_list):
            if not project_dict.get("project_name") == self.project.project_name:
                continue
            new_all_projects_list[i] = self.project.to_dict()

        with open(get_project_yaml_path(), "w") as project_h:
            dump_yaml({"projects": new_all_projects_list}, project_h)


