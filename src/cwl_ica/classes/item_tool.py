#!/usr/bin/env python3

"""
ItemTool is the subclass of Item.

ItemTool implements the following:
  * name
  * path
  * versions
"""

# External imports
from pathlib import Path

# Utils
from ..utils.repo import get_tools_dir
from ..utils.logging import get_logger
from ..utils.errors import ItemVersionAttributeError

# Locals
from .item import Item
from .item_version_tool import ItemVersionTool

# Set logger
logger = get_logger()


class ItemTool(Item):
    """
    ItemTool represents an element under tool.yaml etc.
    """

    def __init__(self, name, path, versions=None, categories=None):
        # Initialise super
        super(ItemTool, self).__init__(
            name,
            path,
            root_dir=get_tools_dir(),
            versions=versions,
            categories=categories
        )

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
            version["cwl_file_path"] = Path(get_tools_dir()) / Path(self.path) / Path(version["path"])
            if not version["cwl_file_path"].is_file():
                logger.warning(f"Could not find cwl file {version['cwl_file_path']}. Skipping file")
                continue
            version_objs.append(ItemVersionTool.from_dict(version))
        return version_objs
