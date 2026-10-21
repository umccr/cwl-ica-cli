#!/usr/bin/env python

"""
The project class holds the configuration of an ICA project as registered in
${CWL_ICA_REPO_PATH}/config/project.yaml.

Historically this class also performed ICAv1 actions (creating / syncing workflows on ICA
through libica). ICAv1 has been deprecated, so the class is now a plain data container used
to read and write project entries in project.yaml. The tools / workflows entries are kept as
raw mappings and passed through untouched.
"""

# External imports
from ruamel.yaml.comments import CommentedMap as OrderedDict

# Utils
from ..utils.logging import get_logger
from ..utils.errors import ProjectCreationError, ItemNotFoundError
from ..utils.yaml import to_multiline_string

# Set logger
logger = get_logger()


class Project:
    """
    A project has the following attributes
    * project_id           # The ICA project id
    * project_name         # The project name as described here
    * project_abbr         # The project abbreviation
    * project_description  # The description of the project
    * tenant_id            # The ICA domain of the project
    """

    is_production = False  # True in ProductionProject class

    def __init__(
        self,
        project_name,
        project_id,
        project_abbr,
        project_api_key_name,
        project_description,
        linked_projects,
        tenant_id,
        tools,
        workflows
    ):
        """
        Collect the project from the project list if defined,
        otherwise read in the project from the project yaml path
        :param project_name:
        :param project_id:
        :param project_abbr:
        :param project_api_key_name:
        :param project_description:
        :param linked_projects:
        :param tenant_id:
        :param tools:
        :param workflows:
        """
        # Easy initialise of project name
        self.project_name = project_name

        # Now assign components from the object
        self.project_id = project_id
        self.project_abbr = project_abbr
        self.project_api_key_name = project_api_key_name
        self.project_description = project_description
        self.linked_projects = linked_projects
        self.tenant_id = tenant_id

        # Tools and workflows are kept as raw mappings (the on-ICA registration was ICAv1)
        self.ica_tools_list = tools if tools is not None else []
        self.ica_workflows_list = workflows if workflows is not None else []

    # Static methods
    @staticmethod
    def get_project_obj_from_project_list(project_name, project_list):
        """
        Returns the project object based on the project name
        :param project_name:
        :param project_list:
        :return:
        """

        for project in project_list:
            if project.get("project_name", None) == project_name:
                return project.deepcopy()

    def get_items_by_item_type(self, item_type):
        """
        Return the tool list or workflows list
        :return:
        """
        if item_type == "tool":
            return self.ica_tools_list
        elif item_type == "workflow":
            return self.ica_workflows_list
        else:
            raise ItemNotFoundError

    # Read / Write functions for project
    def to_dict(self):
        """
        Write out project to dictionary
        :return:
        """

        return OrderedDict({
            "project_name": self.project_name,
            "project_id": self.project_id,
            "project_description": to_multiline_string(self.project_description),
            "project_abbr": self.project_abbr,
            "project_api_key_name": self.project_api_key_name,
            "production": self.is_production,
            "linked_projects": self.linked_projects,
            "tenant_id": self.tenant_id,
            "tools": self.ica_tools_list,
            "workflows": self.ica_workflows_list
        })

    @classmethod
    def from_dict(cls, project_dict):
        """
        Create project object from dictionary
        :param project_dict:
        :return:
        """

        # Check the item_dict has the appropriate keys
        if project_dict.get("project_name", None) is None:
            logger.error("\"project_name\" attribute not found, cannot create project")
            raise ProjectCreationError

        if project_dict.get("project_id", None) is None:
            logger.error("\"project_id\" attribute not found, cannot create project")
            raise ProjectCreationError

        if project_dict.get("project_abbr", None) is None:
            logger.error("\"project_abbr\" attribute not found, cannot create project")
            raise ProjectCreationError

        if project_dict.get("project_api_key_name", None) is None:
            logger.error("\"project_api_key_name\" attribute not found, cannot create project")
            raise ProjectCreationError

        if project_dict.get("project_description", None) is None:
            logger.error("\"project_description\" attribute not found, cannot create project")
            raise ProjectCreationError

        if project_dict.get("linked_projects", None) is None:
            logger.error("\"linked_projects\" attribute not found, cannot create project")
            raise ProjectCreationError

        if project_dict.get("tenant_id", None) is None:
            logger.error("\"tenant_id\" attribute not found, cannot create project")
            raise ProjectCreationError

        return cls(project_name=project_dict.get("project_name", None),
                   project_id=project_dict.get("project_id", None),
                   project_abbr=project_dict.get("project_abbr", None),
                   project_api_key_name=project_dict.get("project_api_key_name", None),
                   project_description=project_dict.get("project_description", None),
                   linked_projects=project_dict.get("linked_projects", None),
                   tenant_id=project_dict.get("tenant_id", None),
                   tools=project_dict.get("tools", None),
                   workflows=project_dict.get("workflows", None))
