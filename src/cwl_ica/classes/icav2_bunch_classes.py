#!/usr/bin/env python3

from __future__ import annotations

# External imports
import os
from collections import OrderedDict
from pathlib import Path
from typing import Optional, List, Dict
import pandas as pd
from ruamel.yaml import CommentedSeq
from datetime import datetime, timezone

# Libica imports
from libica.openapi.v2.model.data import Data
from libica.openapi.v2.model.region import Region

# Utils
from ..utils.errors import InvalidDataItem, InvalidBunchVersionName
from ..utils.icav2_gh_helpers import (
    generate_e_tag_md5sum_from_file_list, generate_folder_structure_md5sum_from_file_list, get_dataset_id_hash,
    read_config_yaml, write_config_yaml, generate_empty_bundle,
    add_pipeline_to_bundle, add_data_to_bundle, release_bundle, add_bundle_to_project, get_dataset_from_dataset_name,
    get_project_id_from_project_name
)
from ..utils.icav2_helpers import (
    get_creator_name_from_creator_id, get_icav2_configuration,
    get_files_from_directory_id_recursively, get_region_obj_from_project_id, get_data_obj_by_id
)
from ..utils.logging import get_logger
from ..utils.miscell import get_name_version_tuple_from_cwl_file_path
from ..utils.repo import get_cwl_ica_repo_path, get_workflows_dir

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
            data_obj: Optional[Data] = None,
            data_type: Optional[str] = None,
            **kwargs
    ):
        # Initialise data object
        self.data_obj = data_obj

        if create:
            # DataSet Item not initialised
            self.data_id: Optional[str] = data_obj.id
            self.owning_project_id: Optional[str] = data_obj.details.owning_project_id
            self.owning_project_name: Optional[str] = data_obj.details.owning_project_name
            self.data_uri: Optional[str] = f"icav2://{data_obj.details.owning_project_name}{data_obj.details.path}"
            self.creation_time: Optional[str] = data_obj.details.time_created.isoformat(
                timespec='seconds'
            ).replace("+00:00", "Z")
            self.modification_time: Optional[str] = data_obj.details.time_modified.isoformat(
                timespec='seconds'
            ).replace("+00:00", "Z")
            self.data_type: Optional[str] = data_type

            # Set creator id / creator name if not set for data item
            if hasattr(data_obj.details, "creator_id"):
                self.creator_id = data_obj.details.creator_id
            else:
                self.creator_id = None

            self.creator_name: Optional[str]
            if self.creator_id is not None:
                self.creator_name = get_creator_name_from_creator_id(self.creator_id, get_icav2_configuration())
            else:
                self.creator_name = None

            # Set either folder attributes or file attributes
            self.set_type_attributes(data_obj)
        else:
            for key, value in kwargs.items():
                setattr(self, key, value)

    def set_type_attributes(self, data_obj: Data):
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
    def from_dict(cls, dataset_dict: OrderedDict):
        """
        Import from yaml
        Implemented in subclass
        :return:
        """

        raise NotImplementedError

    def validate_dataset(self):
        """
        Validate dataset
        """
        # Implemented in subclass
        raise NotImplementedError

    def set_data_obj_attribute(self):
        # Required to validate dataset
        # Takes the data id from an already existing dataset item and sets the data_obj Data attribute
        if self.data_obj is not None:
            return

        self.data_obj = get_data_obj_by_id(self.owning_project_id, self.data_id, get_icav2_configuration())


class DatasetItemFolder(DatasetItem):
    """
    Child class of Dataset item
    """
    def __init__(
        self,
        create: Optional[bool] = None,
        data_obj: Optional[Data] = None,
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

    def set_type_attributes(self, data_obj: Data):
        # Get owning project id from the data object attribute
        project_id = data_obj.details.owning_project_id

        # All subfiles
        all_files = get_files_from_directory_id_recursively(project_id, data_obj.id, get_icav2_configuration())

        # Step 1 -> Find all files within a folder
        self.num_files = len(all_files)

        # Step 2 -> Calculate file size of all files within a folder
        self.folder_size_in_bytes = sum(map(lambda file_item: file_item.details.file_size_in_bytes, all_files))

        # Step 3 -> Calculate md5sum from etag list
        self.object_e_tag_md5sum = generate_e_tag_md5sum_from_file_list(all_files)

        # Step 4 -> Calculate md5sum from folder structure
        self.folder_structure_md5sum = generate_folder_structure_md5sum_from_file_list(
            all_files,
            Path(data_obj.details.path)
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
        all_files = get_files_from_directory_id_recursively(
            self.owning_project_id,
            self.data_obj.id,
            get_icav2_configuration()
        )

        # Confirm we have the expected number of files in the folder
        if not len(all_files) == self.num_files:
            logger.error(f"Incorrect number of files in {self.data_uri}. "
                         f"Expected {self.num_files} but got {len(all_files)}")
            raise InvalidDataItem

        # Calculate the size of the folder is still the same
        folder_size_in_bytes = sum(map(lambda file_item: file_item.details.file_size_in_bytes, all_files))
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
            Path(self.data_obj.details.path)
        )
        if not folder_structure_md5sum == self.folder_structure_md5sum:
            logger.error(f"Got expected number of files and size of folder and file etags, "
                         f"but folder structure is different. "
                         f"Expected {self.folder_structure_md5sum} but got {folder_structure_md5sum}")
            raise InvalidDataItem

    @classmethod
    def from_dict(cls, dataset_dict: Dict):
        return cls(
            create=False,
            data_obj=dataset_dict.get("data_obj", None),
            num_files=dataset_dict.get("num_files", None),
            folder_size_in_bytes=dataset_dict.get("folder_size_in_bytes", None),
            object_e_tag_md5sum=dataset_dict.get("object_e_tag_md5sum", None),
            folder_structure_md5sum=dataset_dict.get("folder_structure_md5sum", None),
            **dataset_dict
        )


class DatasetItemFile(DatasetItem):
    """
    Child class of Dataset item
    """
    def __init__(self, create: Optional[bool], data_obj: Optional[Data],
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

    def set_type_attributes(self, data_obj: Data):
        self.file_size_in_bytes = data_obj.details.file_size_in_bytes
        self.object_e_tag = data_obj.details.object_e_tag

    def type_attributes_to_dict(self) -> OrderedDict:
        return OrderedDict({
            "file_size_in_bytes": self.file_size_in_bytes,
            "object_e_tag": self.object_e_tag
        })

    def validate_dataset(self):
        # Confirm that data obj etag matches etag
        self.set_data_obj_attribute()

        if not self.object_e_tag == self.data_obj.details.object_e_tag:
            logger.error("File object etag is different than expected")
            raise InvalidDataItem

    @classmethod
    def from_dict(cls, dataset_dict: Dict):
        return cls(
            create=False,
            data_obj=dataset_dict.get("data_obj", None),
            **dataset_dict
        )


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
            data_objs: Optional[List[Data]] = None,
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
            self.data_objs: Optional[List[Data]] = data_objs
            self.dataset_creation_time: Optional[datetime] = datetime.now().astimezone(timezone.utc)

            # Get the region id
            self.region_obj: Region = get_region_obj_from_project_id(
                data_objs[0].details.owning_project_id,
                get_icav2_configuration()
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
            if data_obj.details.data_type == "FILE"
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
    * projects:  # The projects the future bundle will be attached to
      - * project_name
        * project_id
    * categories:  # The categories we wish to add to the bundle, keywords within the workflow will also be included.
      - * category_str
    * bunch_versions:
      # An array of bunch version classes.
      * Each bunch version contains the following attributes
        * version: semantic version
        * version_description: <str> version description
        * version_creation_date: <datetime> version creation date
            - only the latest bunch version will be used to create a bundle.
        * datasets: <List[Dataset]>
          - For each dataset
          * dataset_name: <str> Name of the dataset
          * dataset_description: <str> A short description of the dataset
          * dataset_creation_time: <str> Creation time of the dataset in YYYYMMDDTHHMMSSZ format
          * dataset_id_hash: <str> The hash id of the dataset

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
        bunch_versions_dict: Optional[List[Dict]] = None,
        # Parameters only when create is set to true
        version: Optional[str] = None,
        version_description: Optional[str] = None,
        datasets: Optional[List[Dataset]] = None
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

        # Set inputs
        if create:
            # Expect a bunch version input parameters to be provided
            self.bunch_versions: List[BunchVersion] = []
            self.generate_bunch_version(
                version=version,
                version_description=version_description,
                datasets=datasets
            )

        else:
            self.bunch_versions: Optional[List[BunchVersion]] = list(
                map(
                    lambda x: BunchVersion.from_dict(self, x),
                    bunch_versions_dict
                )
            )

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
        bunch_versions_dict = list(
            map(
                lambda x: x.to_dict(),
                self.bunch_versions
            )
        )

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
            "bunch_versions": bunch_versions_dict
        }

    @classmethod
    def from_dict(cls, bunch_dict):
        """
        Read in bunch (and bunch versions from dictionary)
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
            bunch_versions_dict=bunch_dict.get("bunch_versions")
        )

    def get_bunch_versions(self) -> List[BunchVersion]:
        """
        List existing bunch versions
        :return:
        """
        return self.bunch_versions

    def generate_bunch_version(
        self,
        version: str,
        version_description: str,
        datasets: List[Dataset]
    ) -> BunchVersion:
        """
        Generate a bunch version.
        Appends to bunch_version attribute and returns version object
        :return:
        """

        # Create a new bunch version
        new_bunch_version = BunchVersion(
            parent_bunch=self,
            create=True,
            version=version,
            version_description=version_description,
            datasets=datasets,
        )

        # Is this the first bunch version?
        if self.bunch_versions is None:
            self.bunch_versions = [
                new_bunch_version
            ]
        else:
            self.bunch_versions.append(
                new_bunch_version
            )

        return new_bunch_version


class BunchVersion:
    """
    A bunch version is a semantic versioned array of datasets corresponding to a bunch (which contains a workflow path).

    A bunch version is used to generate a bundle by taking the pipeline path / id generated and generating a bundle
    with the datasets provided.

    A bundle version contains the following attributes
    * version: semantic version
    * version_description: <str> version description
    * version_creation_date: <datetime> version creation date
      - only the latest bunch version will be used to create a bundle.
    * datasets: <List[Dataset]>
      - For each dataset
      * dataset_name: <str> Name of the dataset
      * dataset_description: <str> A short description of the dataset
      * dataset_creation_time: <str> Creation time of the dataset in YYYYMMDDTHHMMSSZ format
      * dataset_id_hash: <str> The hash id of the dataset

    When an object of this class is initialised and intends to invoke the generate_bundle_from_bunch_version method,
    it is expected that the bunch object is provided with a pipeline id.

    The pipeline id is NOT tied to the bunch version as the bunch version defines the dataset to the workflow.
    The pipeline id IS tracked by the bundle configuration

    Methods include
    * to_dict
    * from_dict
    * validate_bunch_version
    * generate_bundle_from_bunch_version

    """

    def __init__(
        self,
        parent_bunch: Bunch,
        create: bool,
        version: str,
        version_description: str,
        version_creation_date: Optional[str] = None,
        datasets: Optional[List[Dataset]] = None,
    ):
        """
        Initialise bundle version attributes
        """
        self.parent_bunch = parent_bunch
        self.create = create
        self.version = version
        self.version_description = version_description
        self.version_creation_date = version_creation_date
        self.datasets = datasets
        if self.datasets is None:
            self.datasets = []
        if self.create:
            self.set_version_creation_date()
            self.confirm_unique()

    def set_version_creation_date(self):
        """
        Set version creation date as utc timestamp
        :return:
        """
        self.version_creation_date = datetime.utcnow().isoformat(sep="T", timespec="seconds") + "Z"

    def to_dict(self) -> Dict:
        """
        Write the bunch version to dictionary
        :return:
        """
        # Write out datasets to dictionaries
        datasets_as_dicts = list(
            map(
                lambda x: x.to_dict(),
                self.datasets
            )
        )

        # But don't need everything - don't want to overpopulate the configuration file just the following attributes
        datasets_trimmed = list(
            map(
                lambda x: {
                    "dataset_name": x.get("dataset_name"),
                    "dataset_creation_time": x.get("dataset_creation_time"),
                    "dataset_id_hash": x.get("dataset_id_hash")
                },
                datasets_as_dicts
            )
        )

        return {
                "version": self.version,
                "version_description": self.version_description,
                "version_creation_date": self.version_creation_date,
                "datasets": datasets_trimmed
        }

    @classmethod
    def from_dict(cls, parent_bunch, bunch_version_dict):
        """
        Collect a bunch version from dictionary.

        This is usually called by the parent bunch, so we expect the parent bunch to be an input parameter.
        :return:
        """

        # Get names from datasets listed in bunch version
        dataset_names = list(
            map(
                lambda x: x.get("dataset_name"),
                bunch_version_dict.get("datasets")
            )
        )

        # Get existing datasets in the configuration yaml
        existing_datasets = read_config_yaml().get("datasets")

        # Get datasets in config yaml that match those in bunch version names
        dataset_dicts = list(
            filter(
                lambda x: x.get("dataset_name") in dataset_names,
                existing_datasets
            )
        )

        # Read in datasets as Dataset objects
        dataset_objs = list(
            map(
                lambda x: Dataset.from_dict(x),
                dataset_dicts
            )
        )

        # Get datasets by name
        return cls(
            parent_bunch=parent_bunch,
            create=False,
            version=bunch_version_dict.get("version"),
            version_description=bunch_version_dict.get("version_description"),
            version_creation_date=bunch_version_dict.get("version_creation_date"),
            datasets=dataset_objs
        )

    def validate_bunch_version(self):
        """
        Confirm that the datasets in a bunch version exist by running validate_dataset
        :return:
        """
        for dataset in self.datasets:
            dataset.validate_dataset()

    def generate_bundle_description(self, pipeline_release_url) -> str:
        """
        Write out a description for the bundle

        Include the cwl-ica repository, the pipeline path etc
        :return:
        """
        return f"This bundle has been generated by the release of {self.parent_bunch.pipeline_path}. " \
               f"The pipeline can be found at {pipeline_release_url}.  "

    def generate_bundle_version(self, version_suffix: Optional[str] = None) -> str:
        """
        Generate a bundle name by the bunch_name + bunch_version with periods substituted for '_'
        Currently there is no way to append versions to bundles, so we must extend versions with a version suffix.

        If not provided the version suffix is the current utc time in YYYYMMDDHHMMSS format.
        :return:
        """
        bunch_version = self.version

        if version_suffix is None:
            version_suffix = datetime.utcnow().strftime("%Y%m%d%H%M%S")

        return bunch_version + "__" + version_suffix

    def generate_bundle_version_description(self):
        """
        Generate the bundle version description

        Include the release url
        :return:
        """
        return f"Bundle version description is currently redundant while we cannot append versions to bundles. " \
               f"Regardless - the bunch version is {self.version}"

    def generate_bundle_from_bunch_version(
        self,
        pipeline_commit_id: str,
        pipeline_release_url: str,
        pipeline_id: str,
        pipeline_checksum: str,
        pipeline_project_id: str,
        tenant_access_token: str,
    ) -> Bundle:
        """
        Generate a bundle from a bunch version object
        :param pipeline_commit_id:
        :param pipeline_release_url:
        :param pipeline_id:
        :param pipeline_checksum:
        :param pipeline_project_id:
        :param tenant_access_token:
        :return:
        """

        cwl_ica_repo_path = get_cwl_ica_repo_path()
        workflows_path = get_workflows_dir()

        abs_pipeline_path = cwl_ica_repo_path / self.parent_bunch.pipeline_path

        name, version = get_name_version_tuple_from_cwl_file_path(abs_pipeline_path, workflows_path)

        # Just get the timestamp from the version suffix
        # dragen-somatic-with-germline-pipeline/4.2.4__20231025233121
        version_suffix = os.environ["GITHUB_TAG"].split(",")[-1].rsplit("__", 1)[-1]

        bundle_obj = Bundle(
            create=True,
            bundle_name=self.generate_bundle_name(version_suffix=version_suffix),
            bundle_description=self.generate_bundle_description(pipeline_release_url),
            bundle_version=self.generate_bundle_version(version_suffix=version_suffix),
            bundle_version_description=self.generate_bundle_version_description(),
            bundle_region_id=self.parent_bunch.bunch_region_id,
            bundle_region_city_name=self.parent_bunch.bunch_region_city_name,
            tenant_name=self.parent_bunch.tenant_name,
            pipeline_path=abs_pipeline_path.relative_to(cwl_ica_repo_path),
            pipeline_name=name,
            pipeline_version=version,
            pipeline_release_url=pipeline_release_url,
            pipeline_commit_id=pipeline_commit_id,
            pipeline_checksum=pipeline_checksum,
            pipeline_project_id=pipeline_project_id,
            bunch_name=self.parent_bunch.bunch_name,
            bunch_version=self.version,
            bunch_datasets=self.datasets,
            bundle_categories=self.parent_bunch.categories,
            projects=self.parent_bunch.projects,
            bundle_pipeline_id=pipeline_id
        )

        bundle_obj.create_bundle_from_bunch_version(tenant_access_token)

        return bundle_obj

    def confirm_unique(self):
        """
        Confirm a bunch version name is unique if we're creating a new bunch version (through add-bunch)
        :return:
        """
        existing_version_names = list(
            map(
                lambda x: x.get("version"),
                self.parent_bunch.get_bunch_versions()
            )
        )

        if self.version in existing_version_names:
            logger.error(f"Bunch version {self.version} already exists for bunch {self.parent_bunch.bunch_name}")
            raise InvalidBunchVersionName

    def generate_bundle_name(self, version_suffix: Optional[str] = None) -> str:
        """
        Generate a bundle name by the bunch_name + bunch_version with periods substituted for '_'
        Currently there is no way to append versions to bundles, so we must extend versions with a version suffix.

        If not provided the version suffix is the current utc time in YYYYMMDDHHMMSS format.
        :return:
        """
        bunch_name = self.parent_bunch.bunch_name

        if version_suffix is None:
            version_suffix = datetime.utcnow().strftime("%Y%m%d%H%M%S")

        return bunch_name + "__" + version_suffix


class Bundle:
    """
    A bundle is an established bunch version in a tenant
    A bundle comprises the following information
    * bundle_name: <str>  # Derived from name of bunch plus bunch version name
    * bundle_description: <str>  # Derived from the bunch description
    * bundle_version: <str>  # Derived from name of bunch version with date timestamp
    * bundle_version_description: <str> # Derived from the bunch version description
    * bundle_region_id: <str> # The bundle region id
    * bundle_region_city_name: <str>  # The bundle region city name
    * tenant_name: <str>
    * pipeline_path: <str>  # The relative cwl-ica path for this pipeline
    * pipeline_name: <str>  # The name of the workflow
    * pipeline_version: <str> # The version of the workflow
    * pipeline_release_url: <str>  # The release url for this workflow
    * pipeline_commit_id: <str>  # The commit id of the release url
    * pipeline_checksum: <str>  # The checksum for this workflow
    * pipeline_project_id: str  # The project ID that this pipeline id was created in
    * bunch_name: <str>  # Name of the bunch this bundle has been derived from
    * bunch_version: <str>  # Name of the version this bunch has been derived from
    * bunch_datasets: List[<str>]  # Name of the datasets from this bunch version
    * bundle_categories: <str>  # The categories to specify for this bundle
    * projects: List<str>  # List of projects that this released bundle was added to
    * bundle_pipeline_id: <str>  # The icav2 pipeline id added to this bundle
    # Post creation attributes
    * bundle_id: <str>  # The bundle id
    * bundle_creation_time: <datetime>  # The creation time for this bundle
    * bundle_release_status: <enum>  # Has the bundle been released (should be true once written to configuration yaml)
    * bundle_data_ids: List<str>  # The data items that have been added to this bundle
    * bundle_url: <str>  # The url to access the bundle
                         # (if the bundle is available in your tenant)
                         # https://ica.illumina.com/ica/bundles/<bundle_id>/bundleDetails
    """
    def __init__(
        self,
        create: Optional[bool],
        bundle_name: Optional[str],
        bundle_description: Optional[str],
        bundle_version: Optional[str],
        bundle_version_description: Optional[str],
        bundle_region_id: Optional[str],
        bundle_region_city_name: Optional[str],
        tenant_name: Optional[str],
        pipeline_path: Optional[str],
        pipeline_name: Optional[str],
        pipeline_version: Optional[str],
        pipeline_release_url: Optional[str],
        pipeline_commit_id: Optional[str],
        pipeline_checksum: Optional[str],
        pipeline_project_id: Optional[str],
        bunch_name: Optional[str],
        bunch_version: Optional[str],
        bunch_datasets: Optional[List[Dataset]],
        bundle_categories: Optional[List[str]],
        projects: Optional[str],
        bundle_id: Optional[str] = None,
        bundle_creation_time: Optional[str] = None,
        bundle_release_status: Optional[str] = None,
        bundle_data_ids: Optional[List[str]] = None,
        bundle_pipeline_id: Optional[str] = None,
        bundle_url: Optional[str] = None
    ):
        """
        Initialise a bundle object
        """
        # Set standard attributes
        self.bundle_name = bundle_name
        self.bundle_description = bundle_description
        self.bundle_version = bundle_version
        self.bundle_version_description = bundle_version_description

        self.bundle_region_id = bundle_region_id
        self.bundle_region_city_name = bundle_region_city_name

        self.tenant_name = tenant_name

        # Pipeline attrs
        self.pipeline_path = pipeline_path
        self.pipeline_name = pipeline_name
        self.pipeline_version = pipeline_version
        self.pipeline_release_url = pipeline_release_url
        self.pipeline_commit_id = pipeline_commit_id
        self.pipeline_checksum = pipeline_checksum
        self.pipeline_project_id = pipeline_project_id

        # Bunch attributes
        self.bunch_name = bunch_name
        self.bunch_version = bunch_version
        self.bunch_datasets = bunch_datasets

        # Bundle bits and pieces
        self.bundle_pipeline_id = bundle_pipeline_id
        self.bundle_url = bundle_url
        self.bundle_categories = bundle_categories

        # Ownership
        self.projects = projects

        if not create:
            # Rare case
            self.bundle_creation_time = bundle_creation_time
            self.bundle_release_status = bundle_release_status
            self.bundle_id = bundle_id
            self.bundle_data_ids = bundle_data_ids
        else:
            self.bundle_creation_time = datetime.now().astimezone(timezone.utc).isoformat(
                timespec="seconds"
            ).replace("+00:00", "Z")
            self.bundle_release_status = "draft"
            self.bundle_id = None
            self.bundle_data_ids = []

    def create_bundle_from_bunch_version(self, icav2_access_token: str):
        """
        Generate bundle then add data and workflows to bundle
        :return:
        """

        bundle_obj = generate_empty_bundle(
            bundle_name=self.bundle_name,
            bundle_version=self.bundle_version,
            bundle_description=self.bundle_description,
            bundle_version_description=self.bundle_version_description,
            region_id=self.bundle_region_id,
            categories=self.bundle_categories,
            pipeline_release_url=self.pipeline_release_url,
            icav2_access_token=icav2_access_token,
        )

        # Get bundle id
        self.bundle_id = bundle_obj.id

        # Set bundle url
        self.bundle_url = f"https://ica.illumina.com/ica/bundles/{self.bundle_id}/bundleDetails"

        # Add workflow to bundle
        add_pipeline_to_bundle(self.bundle_id, self.bundle_pipeline_id, icav2_access_token)

        # Add data to bundle
        dataset: Dataset
        for dataset in self.bunch_datasets:
            data_item: DatasetItem
            for data_item in dataset.dataset_items:
                add_data_to_bundle(self.bundle_id, data_item.data_id, icav2_access_token)
                self.bundle_data_ids.append(data_item.data_id)

        # Release the bundle
        self.release_bundle(icav2_access_token)

        # Add the released bundle to the required projects
        project: str
        for project_name in self.projects:
            # Need to collect the project id from the icav2 configuration mapping
            project_id = get_project_id_from_project_name(self.tenant_name, project_name)

            # Then add the released bundle to the project
            self.add_released_bundle_to_project(project_id, icav2_access_token)

    def release_bundle(self, icav2_access_token):
        """
        Release a bundle once it has all the data and wo  kflow
        :return:
        """
        release_bundle(self.bundle_id, icav2_access_token)

    def add_released_bundle_to_project(self, project_id: str, icav2_access_token):
        """
        Add the bundle to the project specified by the bunch
        :return:
        """
        add_bundle_to_project(project_id, self.bundle_id, icav2_access_token)

    def to_dict(self):
        """
        Write the bundle to a dictionary (to be written to icav2 configuration file)
        Eventually we will consider methods to run validations from this configuration
        :return:
        """

        bunch_datasets = list(
            map(
                lambda dataset_map_iter: {
                    "dataset_name": dataset_map_iter.dataset_name,
                    "dataset_creation_time": dataset_map_iter.dataset_creation_time.isoformat(
                        timespec="seconds"
                    ).replace("+00:00", "Z"),
                    "dataset_id_hash": dataset_map_iter.dataset_id_hash
                },
                self.bunch_datasets
            )
        )

        return {
            "bundle_name": self.bundle_name,
            "bundle_description": self.bundle_description,
            "bundle_version": self.bundle_version,
            "bundle_version_description": self.bundle_version_description,
            "bundle_region_id": self.bundle_region_id,
            "bundle_region_city_name": self.bundle_region_city_name,
            "tenant_name": self.tenant_name,
            "pipeline_path": str(self.pipeline_path),
            "pipeline_name": self.pipeline_name,
            "pipeline_version": self.pipeline_version,
            "pipeline_release_url": self.pipeline_release_url,
            "pipeline_commit_id": self.pipeline_commit_id,
            "pipeline_checksum": self.pipeline_checksum,
            "pipeline_project_id": self.pipeline_project_id,
            "bundle_creation_time": self.bundle_creation_time,
            "bundle_release_status": self.bundle_release_status,
            "bunch_name": self.bunch_name,
            "bunch_version": self.bunch_version,
            "bunch_datasets": bunch_datasets,
            "bundle_id": self.bundle_id,
            "bundle_data_ids": self.bundle_data_ids,
            "bundle_pipeline_id": self.bundle_pipeline_id,
            "bundle_url": self.bundle_url,
            "bundle_categories": self.bundle_categories,
            "projects": self.projects
        }

    @classmethod
    def from_dict(cls, bundle_dict):
        """
        Rare (and yet-to-be-implemented) situation, but sometimes a bundle will already exist,
        we can generate as a bundle object.
        Use cases include adding new data to the bundle, or add the bundle to a new project
        :return:
        """
        bunch_datasets = list(
            map(
                lambda x: get_dataset_from_dataset_name(x.get("dataset_name")),
                bundle_dict.get("bunch_datasets")
            )
        )

        return cls(
            create=False,
            bundle_name=bundle_dict.get("bundle_name"),
            bundle_description=bundle_dict.get("bundle_description"),
            bundle_version=bundle_dict.get("bundle_version"),
            bundle_version_description=bundle_dict.get("bundle_version_description"),
            bundle_region_id=bundle_dict.get("bundle_region_id"),
            bundle_region_city_name=bundle_dict.get("bundle_region_city_name"),
            tenant_name=bundle_dict.get("tenant_name"),
            pipeline_path=bundle_dict.get("pipeline_path"),
            pipeline_name=bundle_dict.get("pipeline_name"),
            pipeline_version=bundle_dict.get("pipeline_version"),
            pipeline_release_url=bundle_dict.get("pipeline_release_url"),
            pipeline_commit_id=bundle_dict.get("pipeline_commit_id"),
            pipeline_checksum=bundle_dict.get("pipeline_checksum"),
            pipeline_project_id=bundle_dict.get("pipeline_project_id"),
            bundle_creation_time=bundle_dict.get("bundle_creation_time"),
            bundle_release_status=bundle_dict.get("bundle_release_status"),
            bunch_name=bundle_dict.get("bunch_name"),
            bunch_version=bundle_dict.get("bunch_version"),
            bunch_datasets=bunch_datasets,
            bundle_id=bundle_dict.get("bundle_id"),
            bundle_data_ids=bundle_dict.get("bundle_data_ids"),
            bundle_pipeline_id=bundle_dict.get("bundle_pipeline_id"),
            bundle_url=bundle_dict.get("bundle_url"),
            bundle_categories=bundle_dict.get("bundle_categories"),
            projects=bundle_dict.get("projects")
        )
