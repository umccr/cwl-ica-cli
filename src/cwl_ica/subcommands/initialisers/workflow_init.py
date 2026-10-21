#!/usr/bin/env python3

"""
Subclass of initialiser
"""

# External imports
from pathlib import Path

# Classes
from ...classes.item_version_workflow import ItemVersionWorkflow
from ...classes.item_workflow import ItemWorkflow

# Utils
from ...utils.logging import get_logger
from ...utils.repo import get_workflow_yaml_path, get_workflows_dir
from ...utils.errors import CheckArgumentError

# Locals
from . import Initialiser

# Set logger
logger = get_logger()


class WorkflowInitialiser(Initialiser):
    """Usage:
    cwl-ica [options] workflow-init help
    cwl-ica [options] workflow-init (--workflow-path /path/to/workflow.cwl)
                                [--categories="comma,separated,list"]


Description:
    Add in a workflow to 'workflow.yaml' in the configuration folder.
    The should have been created with cwl-ica create-workflow-from-template and then validated with workflow-validate.
    We will also run a validation on the workflow.


Options:
    --workflow-path=<the workflow path>                         Required, the path to the cwl workflow
    --categories=<a list of categories for this workflow>   A list of categories, a short summary of the project

Example:
    cwl-ica workflow-init --workflow-path "workflows/samworkflows-fastq/1.10/samworkflows-fastq__1.10.cwl"
    cwl-ica workflow-init --workflow-path "workflows/samworkflows-fastq/1.10/samworkflows-fastq__1.10.cwl" --categories 'File Format Conversion'
    """

    def __init__(self, command_argv):
        # Call super class
        super(WorkflowInitialiser, self).__init__(
            command_argv,
            item_dir=get_workflows_dir(),
            item_yaml_path=get_workflow_yaml_path(non_existent_ok=True),
            item_type_key="workflows",
            item_type="workflow",
            item_suffix="cwl"
        )

    def __call__(self):
        # Call the super class' call function
        super(WorkflowInitialiser, self).__call__()

    # Methods implemented in subclass
    def check_args(self):
        """
        Checks --workflow-path exists
        :return:
        """

        # We will have a name and a version for this workflow/expression/workflow etc.

        # Check --workflow-path argument
        cwl_path = self.args.get("--workflow-path", None)

        if cwl_path is None:
            logger.error("--workflow-path not specified")
            raise CheckArgumentError

        # Convert to path type
        cwl_path = Path(cwl_path)

        self.check_cwl_path(cwl_path)

        self.cwl_file_path = cwl_path

        if not cwl_path.is_file():
            logger.error(f"--workflow-path argument \"{cwl_path} could not be found")
            raise CheckArgumentError

        # Get the name and version attributes
        self.set_name_and_version_from_file_path()

        # Set categories
        self.set_categories_list()

    def create_item_object(self):
        """
        This creates the item object along with the first version of the item
        This also calls create_item_version and assigns item_version attribute
        :return:
        """
        return ItemWorkflow(
            name=self.name,
            path=Path(self.name),
            versions=[self.create_item_version_object()],
            categories=self.categories_list
        )

    @staticmethod
    def get_item_obj_from_dict(item_dict):
        """
        Read in an item object from a dictionary
        :return:
        """

        return ItemWorkflow.from_dict(item_dict)

    def create_item_version_object(self):
        """
        Create the item version for self.item and assign to item_version
        :return:
        """
        item_version = ItemVersionWorkflow(
            name=self.version,
            path=Path(self.version) / Path(self.cwl_file_path.resolve().name),
            md5sum=None,
            cwl_file_path=self.cwl_file_path
        )

        # We need to call the 'item version' to collect the md5sum attribute
        item_version()

        return item_version
