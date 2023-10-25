#!/usr/bin/env python3

"""
Dockstore object
"""
from pathlib import Path
from typing import Optional, List, Dict
from urllib.parse import urlparse

from cwl_utils.parser import load_document_by_uri, Workflow

from utils.gh_helpers import get_github_url
from utils.logging import get_logger
from utils.miscell import get_name_version_tuple_from_cwl_file_path
from utils.repo import get_workflows_dir, get_cwl_ica_repo_path

logger = get_logger()


class Dockstore:
    """
    Dockstore class will have the following attributes
     * name
     * cwl_file_path
     * subclass  # Always 'CWL'
     * primaryDescriptorPath  # same as the cwl file path
     * readMePath  # Will be the GitHub catalogue path to this workflow version
     * authors  # Scraped from the CWL File path under 'author' and 'maintainer' attributes.
     * filters / tags  # Since a workflow version may have multiple releases, each release extends the version / tag

    Has the following methods:

    * add_to_dockstore_yaml
      # Determines if an entry already exists for this workflow / version combination.
      # If so, extends the existing tags.
    """

    def __init__(
            self,
            create: bool,
            name: str,
            cwl_file_path: Path,
            subclass: str,
            primary_descriptor_path: Path,
            readme_path: Optional[str] = None,
            authors: Optional[List[Dict]] = None,
            tags: Optional[List[str]] = None
        ):

        self.name = name  # Is name__version?
        self.cwl_file_path = cwl_file_path
        self.subclass = subclass
        self.readme_path = readme_path
        self.authors = authors
        self.tags = tags

        if self.subclass is None:
            self.subclass = "CWL"

        if create and authors is None:
            self.update_authors_from_cwl_file_path()

        if create and readme_path is None:
            self.update_readme_path_from_cwl_file_path()

        if create and primary_descriptor_path is not None:
            self.primary_descriptor_path = primary_descriptor_path.relative_to(get_cwl_ica_repo_path())
        else:
            self.primary_descriptor_path = primary_descriptor_path

    def update_readme_path_from_cwl_file_path(self):
        """
        Generate the readme path from the cwl file path
        :return:
        """

        name, version = get_name_version_tuple_from_cwl_file_path(
            self.cwl_file_path,
            items_dir=get_workflows_dir()
        )

        self.readme_path = f"/.github/catalogue/docs/workflows/{name}/{version}/{name}__{version}.md"

    def update_authors_from_cwl_file_path(self):
        """
        # Metadata
            s:author:
                class: s:Person
                s:name: Alexis Lucattini
                s:email: Alexis.Lucattini@umccr.org
                s:identifier: https://orcid.org/0000-0001-9754-647X
        :return:
        """
        workflow: Workflow = load_document_by_uri(Path(urlparse(str(self.cwl_file_path)).path).absolute().resolve())

        author_as_ordered_dict = workflow.extension_fields.get("https://schema.org/author")

        author_as_ordered_dict_stripped = {}
        author_as_ordered_dict_stripped = {}
        for key, value in author_as_ordered_dict.items():
            new_key = key.rsplit(":", 1)[-1]
            if new_key in ["orcid", "name", "email", "role", "affiliation"]:
                author_as_ordered_dict_stripped[new_key] = value

        if len(author_as_ordered_dict_stripped) == 0:
            return

        if self.authors is None:
            self.authors = [
                author_as_ordered_dict_stripped
            ]
        else:
            self.authors.append(
                author_as_ordered_dict_stripped
            )

    def add_tags(self, tags: List[str]):
        """
        Add a tag to an existing dockstore yaml entry
        :param tag:
        :return:
        """
        if self.tags is None:
            self.tags = tags
        else:
            # Only append tags that are not already in tags
            for tag in tags:
                if tag not in self.tags:
                    self.tags.append(tag)

    def to_dict(self) -> Dict:
        """
        Write to dockstore.yml file
        :return:
        """
        return {
            "name": self.name,
            "subclass": "CWL",
            "primaryDescriptorPath": "/" + str(self.primary_descriptor_path),
            "readMePath": str(self.readme_path),
            "authors": self.authors,
            "filters": {
                "tags": self.tags
            }
        }

    @classmethod
    def from_dict(cls, dockstore_dict):
        """
        Read in from dockstore yaml
        :return:
        """
        # Calculate cwl file path
        cwl_file_path = \
            get_workflows_dir() / \
            Path(dockstore_dict.get("primaryDescriptorPath")).relative_to("/.dockstore")

        return cls(
            create=False,
            name=dockstore_dict.get("name"),
            cwl_file_path=cwl_file_path,
            subclass=dockstore_dict.get("subclass"),
            primary_descriptor_path=Path(dockstore_dict.get("primaryDescriptorPath")),
            readme_path=dockstore_dict.get("readMePath"),
            authors=dockstore_dict.get("authors"),
            tags=dockstore_dict.get("filters").get("tags")
        )
