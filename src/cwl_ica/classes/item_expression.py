#!/usr/bin/env python3

"""
Itemexpression is the subclass of Item.

Itemexpression implements the following:
  * name
  * path
  * versions
"""

# External imports
from pathlib import Path

# Utils
from ..utils.errors import ItemVersionAttributeError
from ..utils.logging import get_logger
from ..utils.repo import get_expressions_dir

# Local
from .item import Item
from .item_version_expression import ItemVersionExpression

# Get logger
logger = get_logger()


class ItemExpression(Item):
    """
    Itemexpression represents an element under expression.yaml etc.
    """

    def __init__(self, name, path, versions=None, categories=None):
        # Initialise super
        super(ItemExpression, self).__init__(name, path,
                                             root_dir=get_expressions_dir(),
                                             versions=versions,
                                             categories=categories)

    def get_versions(self, versions):
        """
        Converts versions into dicts
        :param versions:
        :return:
        """
        # Don't want to overwrite dict
        versions = versions.copy()
        # Initialise new version objects
        version_objs = []
        for version in versions.copy():
            if version.get("path", None) is None:
                logger.error("Path attribute not found")
                raise ItemVersionAttributeError
            # Need to add in the cwl file path
            version["cwl_file_path"] = Path(get_expressions_dir()) / Path(self.path) / Path(version["path"])
            if not version["cwl_file_path"].is_file():
                logger.warning(f"Could not find cwl file {version['cwl_file_path']}. Skipping file")
                continue
            version_objs.append(ItemVersionExpression.from_dict(version))
        return version_objs
