#!/usr/bin/env python3

from __future__ import annotations

# External imports
from collections import OrderedDict
from pathlib import Path
from typing import Optional, List, Dict
import pandas as pd
from ruamel.yaml import CommentedSeq
from datetime import datetime, timezone

# Libica imports
from libica.openapi.v2.model.project_data import ProjectData
from libica.openapi.v2.model.region import Region

# Wrapica imports
from wrapica.user import get_user_name_from_user_id
from wrapica.project_data import get_project_data_obj_by_id, find_project_data_bulk
from wrapica.region import get_region_obj_from_project_id

# Local imports
# Utils
from ..utils.errors import InvalidDataItem
from ..utils.icav2_gh_helpers import (
    generate_e_tag_md5sum_from_file_list, generate_folder_structure_md5sum_from_file_list, get_dataset_id_hash,
    read_config_yaml, write_config_yaml
)
from ..utils.logging import get_logger
from ..utils.repo import get_cwl_ica_repo_path

# Set logger
logger = get_logger()


class DatasetItem:
    """
    A dataset item comprises the following information
    data_id
    owning_project_id
    owning_project_name
    data_uri
    creation_time
    modification_time
    creator_id
    creator_name
    data_type

    Plus the following attributes if a FILE
      * file_size_in_bytes
      * object_e_tag

    Plus the following attributes if a FOLDER
      * num_files
      * folder_size_in_bytes
      * object_e_tag_md5sum
      * folder_structure_md5sum
    """
    def __init__(
            self,
            create: bool = True,
            data_obj: Optional[ProjectData] = None,
            data_type: Optional[str] = None,
            **kwargs
    ):
        # Initialise data object
        self.data_obj = data_obj

        if create:
            # DataSet Item not initialised
            self.data_id: Optional[str] = data_obj.data.id
            self.owning_project_id: Optional[str] = data_obj.data.details.owning_project_id
            self.owning_project_name: Optional[str] = data_obj.data.details.owning_project_name
            self.data_uri: Optional[str] = f"icav2://{data_obj.data.details.owning_project_name}{data_obj.data.details.path}"
            self.creation_time: Optional[str] = data_obj.data.details.time_created.isoformat(
                timespec='seconds'
            ).replace("+00:00", "Z")
            self.modification_time: Optional[str] = data_obj.data.details.time_modified.isoformat(
                timespec='seconds'
            ).replace("+00:00", "Z")
            self.data_type: Optional[str] = data_type

            # Set creator id / creator name if not set for data item
            if hasattr(data_obj.data.details, "creator_id"):
                self.creator_id = data_obj.data.details.creator_id
            else:
                self.creator_id = None

            self.creator_name: Optional[str]
            if self.creator_id is not None:
                self.creator_name = get_user_name_from_user_id(self.creator_id)
            else:
                self.creator_name = None

            # Set either folder attributes or file attributes
            self.set_type_attributes(data_obj)
        else:
            for key, value in kwargs.items():
                setattr(self, key, value)

    def set_type_attributes(self, data_obj: ProjectData):
        # Implemented in subclass
        raise NotImplementedError

    def type_attributes_to_dict(self) -> OrderedDict:
        # Implemented in subclass
        raise NotImplementedError

    def to_dict(self):
        """
        Write to dictionary
        :return:
        """
        data_map = {
          "data_id": self.data_id,
          "owning_project_id": self.owning_project_id,
          "owning_project_name": self.owning_project_name,
          "data_uri": self.data_uri,
          "creation_time": self.creation_time,
          "modification_time": self.modification_time,
          "creator_id": self.creator_id,
          "creator_name": self.creator_name,
          "data_type": self.data_type
        }

        data_map.update(self.type_attributes_to_dict())

        return data_map

    @classmethod
    def from_dict(cls, dataset_dict: Dict):
        return cls(
            create=False,
            data_obj=dataset_dict.get("data_obj", None),
            **dataset_dict
        )

    def validate_dataset(self):
        """
        Validate dataset
        """
        # Implemented in subclass
        raise NotImplementedError

    def set_data_obj_attribute(self):
        # Required to validate dataset
        # Takes the data id from an already existing dataset item and sets the data_obj ProjectData attribute
        if self.data_obj is not None:
            return

        self.data_obj = get_project_data_obj_by_id(self.owning_project_id, self.data_id)


class DatasetItemFolder(DatasetItem):
    """
    Child class of Dataset item
    """
    def __init__(
        self,
        create: Optional[bool] = None,
        data_obj: Optional[ProjectData] = None,
        num_files: Optional[str] = None,
        folder_size_in_bytes: Optional[int] = None,
        object_e_tag_md5sum: Optional[str] = None,
        folder_structure_md5sum: Optional[str] = None,
        **kwargs
    ):

        # Initialise folder parameters
        self.num_files = num_files
        self.folder_size_in_bytes = folder_size_in_bytes
        self.object_e_tag_md5sum = object_e_tag_md5sum
        self.folder_structure_md5sum = folder_structure_md5sum
        self.data_type = "FOLDER"
        _ = kwargs.pop("data_type", None)

        # Collect args from super set
        super().__init__(create, data_obj, self.data_type, **kwargs)

    def set_type_attributes(self, data_obj: ProjectData):
        # Get owning project id from the data object attribute
        project_id = data_obj.data.details.owning_project_id

        # All subfiles
        all_files = find_project_data_bulk(
            project_id=project_id,
            parent_folder_id=data_obj.data.id,
            data_type="FILE",
        )

        # Step 1 -> Find all files within a folder
        self.num_files = len(all_files)

        # Step 2 -> Calculate file size of all files within a folder
        self.folder_size_in_bytes = sum(map(lambda file_item: file_item.data.details.file_size_in_bytes, all_files))

        # Step 3 -> Calculate md5sum from etag list
        self.object_e_tag_md5sum = generate_e_tag_md5sum_from_file_list(all_files)

        # Step 4 -> Calculate md5sum from folder structure
        self.folder_structure_md5sum = generate_folder_structure_md5sum_from_file_list(
            all_files,
            Path(data_obj.data.details.path)
        )

    def type_attributes_to_dict(self) -> OrderedDict:
        return OrderedDict({
            "num_files": self.num_files,
            "folder_size_in_bytes": self.folder_size_in_bytes,
            "object_e_tag_md5sum": self.object_e_tag_md5sum,
            "folder_structure_md5sum": self.folder_structure_md5sum
        })

    def validate_dataset(self):
        # Set data obj attribute
        self.set_data_obj_attribute()

        # Check number of files
        all_files = find_project_data_bulk(
            project_id=self.owning_project_id,
            parent_folder_id=self.data_obj.id,
            data_type="FILE"
        )

        # Confirm we have the expected number of files in the folder
        if not len(all_files) == self.num_files:
            logger.error(f"Incorrect number of files in {self.data_uri}. "
                         f"Expected {self.num_files} but got {len(all_files)}")
            raise InvalidDataItem

        # Calculate the size of the folder is still the same
        folder_size_in_bytes = sum(map(lambda file_item: file_item.data.details.file_size_in_bytes, all_files))
        if not folder_size_in_bytes == self.folder_size_in_bytes:
            logger.error(f"Got expected number of files in {self.data_uri} but folder is a different size. "
                         f"Expected {self.folder_size_in_bytes} but got {folder_size_in_bytes}")
            raise InvalidDataItem

        # Calculate the object e tag md5sum and confirm matches
        object_e_tag_md5sum = generate_e_tag_md5sum_from_file_list(all_files)
        if not object_e_tag_md5sum == self.object_e_tag_md5sum:
            logger.error(f"Got expected number of files and size of folder, but object etags are different. "
                         f"Expected {self.object_e_tag_md5sum} but got {object_e_tag_md5sum}")
            raise InvalidDataItem

        # Calculate the folder structure md5sum
        folder_structure_md5sum = generate_folder_structure_md5sum_from_file_list(
            all_files,
            Path(self.data_obj.data.details.path)
        )
        if not folder_structure_md5sum == self.folder_structure_md5sum:
            logger.error(f"Got expected number of files and size of folder and file etags, "
                         f"but folder structure is different. "
                         f"Expected {self.folder_structure_md5sum} but got {folder_structure_md5sum}")
            raise InvalidDataItem




class DatasetItemFile(DatasetItem):
    """
    Child class of Dataset item
    """
    def __init__(self, create: Optional[bool], data_obj: Optional[ProjectData],
                 file_size_in_bytes: Optional[int] = None,
                 object_e_tag: Optional[str] = None,
                 **kwargs):

        # Initialise folder parameters
        self.file_size_in_bytes: Optional[int] = file_size_in_bytes
        self.object_e_tag: Optional[str] = object_e_tag
        self.data_type = "FILE"
        _ = kwargs.pop("data_type", None)

        # Collect args from super set
        super().__init__(create, data_obj, self.data_type, **kwargs)

    def set_type_attributes(self, data_obj: ProjectData):
        self.file_size_in_bytes = data_obj.data.details.file_size_in_bytes
        self.object_e_tag = data_obj.data.details.object_e_tag

    def type_attributes_to_dict(self) -> OrderedDict:
        return OrderedDict({
            "file_size_in_bytes": self.file_size_in_bytes,
            "object_e_tag": self.object_e_tag
        })

    def validate_dataset(self):
        # Confirm that data obj etag matches etag
        self.set_data_obj_attribute()

        if not self.object_e_tag == self.data_obj.data.details.object_e_tag:
            logger.error("File object etag is different than expected")
            raise InvalidDataItem


class Dataset:
    """
    A dataset comprises the following information
    * dataset_tenant_name
    * dataset_name
    * dataset_description
    * cwl_username
    * dataset_region_id
    * dataset_region_city_name
    * dataset_creation_time
    * dataset_id_hash

    Plus for each data item, data_type specific attributes
    * data_id
    * owning_project_id
    * owning_project_name
    * data_uri
    * creation_time
    * modification_time
    * creator_id
    * creator_name
    * data_type

    FILES ONLY
    * file_size_in_bytes
    * object_e_tag

    FOLDERS ONLY
    * num_files (number of files in folder - recursively)
    * folder_size_in_bytes (sum of file_size_in_bytes for all files in the directory)
    * object_e_tag_md5sum (md5sum of the object_e_tag list (sorted by file path))
    * folder_structure_md5sum (md5sum of the folder structure (sorted by file path))

    """
    def __init__(
            self,
            dataset_name: str,
            dataset_description: str,
            username: str,
            tenant_name: str,
            create: bool,
            dataset_items: Optional[List[DatasetItem]] = None,
            data_objs: Optional[List[ProjectData]] = None,
            dataset_creation_time: Optional[datetime] = None,
            region_obj: Optional[Region] = None,
            dataset_region_id: Optional[str] = None,
            dataset_region_city_name: Optional[str] = None,
            dataset_id_hash: Optional[str] = None
    ):
        # Initialise arguments
        self.dataset_name: str = dataset_name
        self.dataset_description: str = dataset_description
        self.username: str = username
        self.tenant_name: str = tenant_name

        # Items if dataset exists
        if not create:
            self.dataset_items: Optional[List[DatasetItem]] = dataset_items
            self.dataset_creation_time: Optional[datetime] = dataset_creation_time
            self.region_obj = region_obj
            self.dataset_id_hash = dataset_id_hash
            self.dataset_region_id = dataset_region_id
            self.dataset_region_city_name = dataset_region_city_name
        else:
            # Items if dataset does not exist
            self.data_objs: Optional[List[ProjectData]] = data_objs
            self.dataset_creation_time: Optional[datetime] = datetime.now().astimezone(timezone.utc)

            # Get the region id
            self.region_obj: Region = get_region_obj_from_project_id(
                data_objs[0].data.details.owning_project_id,
            )
            self.dataset_region_id = self.region_obj.id
            self.dataset_region_city_name = self.region_obj.city_name

            # Set dataset_items
            self.set_dataset_items()

            self.set_dataset_id_hash()

    # Set dataset items
    def set_dataset_items(self):
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
            for data_obj in self.data_objs
        ]

    # Set dataset_id_hash
    def set_dataset_id_hash(self):
        """
        The id hash is the md5sum of the ordered list of files / folders
        :return:
        """
        self.dataset_id_hash = get_dataset_id_hash(self.dataset_items)

    # to_dict - write out input, output and engine_parameters in base64
    def to_dict(self):
        """
        Return an ordered dictionary
        :return:
        """

        return {
            "dataset_tenant_name": self.tenant_name,
            "dataset_name": self.dataset_name,
            "dataset_description": self.dataset_description,
            "cwl_username": self.username,
            "dataset_region_id": self.dataset_region_id,
            "dataset_region_city_name": self.dataset_region_city_name,
            "dataset_creation_time": self.dataset_creation_time.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "dataset_id_hash": self.dataset_id_hash,
            "data": [
                data.to_dict()
                for data in self.dataset_items
            ]
        }

    def validate_dataset(self):
        # Validate each dataset item and return if all are valid.
        for dataset_item in self.dataset_items:
            dataset_item.validate_dataset()

    def to_v2_config_yaml(self):
        """
        Open and add to an icav2 configuration file (if this is in create mode)
        :return:
        """

        data = read_config_yaml()

        if data.get("datasets") is None:
            data["datasets"] = CommentedSeq()
            data.yaml_set_comment_before_after_key(
                key="datasets",
                before="\nList of datasets"
            )

        # Append dataset
        data["datasets"].append(
            self.to_dict()
        )

        # Write back to yaml path
        write_config_yaml(data)

    @classmethod
    def from_dict(cls, dataset_dict):
        """
        Import from yaml
        :return:
        """

        dataset_items = list(
            map(
                lambda dataset_item: DatasetItemFile.from_dict(dict(dataset_item))
                if dataset_item.get("data_type") == "FILE"
                else DatasetItemFolder.from_dict(dict(dataset_item)),
                dataset_dict.get("data")
            )
        )

        return cls(
            create=False,
            data_objs=None,
            dataset_name=dataset_dict.get("dataset_name"),
            dataset_description=dataset_dict.get("dataset_description"),
            username=dataset_dict.get("username"),
            tenant_name=dataset_dict.get("tenant_name"),
            dataset_items=dataset_items,
            dataset_creation_time=pd.to_datetime(dataset_dict.get("dataset_creation_time")),
            dataset_region_id=dataset_dict.get("dataset_region_id"),
            dataset_region_city_name=dataset_dict.get("dataset_region_city_name"),
            dataset_id_hash=dataset_dict.get("dataset_id_hash"),
        )


class Bunch:
    """
    A bunch comprises the following information
    * bunch_name
    * bunch_description
    * tenant_name
    * pipeline_path
    * pipeline_project_name: <str> The project name the pipeline is to be installed into
    * bunch_region_id
    * bunch_region_city_name
    * projects:  # The projects the pipeline will be linked to
      - * project_name
        * project_id
    * categories:  # The categories we wish to add to the pipeline, keywords within the workflow will also be included.
      - * category_str

    """
    def __init__(
        self,
        create: bool,
        bunch_name: str,
        bunch_description: str,
        tenant_name: str,
        pipeline_path: Path,
        pipeline_project_name: str,
        bunch_region_id: str,
        bunch_region_city_name: str,
        projects: Optional[List[Dict]] = None,
        categories: Optional[List[str]] = None,
    ):
        """
        Initialise a bunch class object
        """
        self.create: bool = create

        self.bunch_name: Optional[str] = bunch_name
        self.bunch_description: Optional[str] = bunch_description
        self.tenant_name: Optional[str] = tenant_name
        self.pipeline_path: Optional[Path] = pipeline_path
        self.pipeline_project_name: Optional[str] = pipeline_project_name
        self.projects: Optional[List[str]] = projects
        self.categories = categories
        self.bunch_region_id: Optional[str] = bunch_region_id
        self.bunch_region_city_name: Optional[str] = bunch_region_city_name

    def validate_bunch(self):
        """
        Confirm bunch's workflow path exists
        :return:
        """
        if not self.pipeline_path.is_file():
            logger.error(
                f"Could not find path to bunch origin workflow path "
                f"'{self.pipeline_path.relative_to(get_cwl_ica_repo_path())}'"
            )
            raise FileNotFoundError

    def to_dict(self):
        """
        Write out bunch to dictionary
        :return:
        """
        return {
            "bunch_name": self.bunch_name,
            "bunch_description": self.bunch_description,
            "tenant_name": self.tenant_name,
            "pipeline_path": str(self.pipeline_path),
            "pipeline_project_name": self.pipeline_project_name,
            "bunch_region_id": self.bunch_region_id,
            "bunch_region_city_name": self.bunch_region_city_name,
            "projects": self.projects,
            "categories": self.categories,
        }

    @classmethod
    def from_dict(cls, bunch_dict):
        """
        Read in bunch from dictionary.

        Legacy configuration files may still contain a 'bunch_versions' key, this is silently ignored.
        :return:
        """

        return cls(
            create=False,
            bunch_name=bunch_dict.get("bunch_name"),
            bunch_description=bunch_dict.get("bunch_description"),
            tenant_name=bunch_dict.get("tenant_name"),
            pipeline_path=Path(bunch_dict.get("pipeline_path")),
            pipeline_project_name=bunch_dict.get("pipeline_project_name"),
            bunch_region_id=bunch_dict.get("bunch_region_id"),
            bunch_region_city_name=bunch_dict.get("bunch_region_city_name"),
            projects=bunch_dict.get("projects"),
            categories=bunch_dict.get("categories"),
        )
