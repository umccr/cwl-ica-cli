#!/usr/bin/env python

"""
V2 helpers
"""
from __future__ import annotations
import os
from pathlib import Path
from hashlib import md5
from typing import List, Tuple, Dict, Optional
from urllib.parse import urlparse

from libica.openapi.v2 import Configuration, ApiClient, ApiException
from libica.openapi.v2.api.bundle_api import BundleApi
from libica.openapi.v2.api.pipeline_api import PipelineApi
from libica.openapi.v2.model.create_bundle import CreateBundle
from libica.openapi.v2.model.bundle import Bundle
from libica.openapi.v2.model.data import Data
from libica.openapi.v2.model.link import Link
from libica.openapi.v2.model.links import Links
from libica.openapi.v2.model.pipeline import Pipeline
from libica.openapi.v2.model.project_data import ProjectData

from utils.errors import ProjectNotFoundError, BunchNotFoundError
from utils.globals import ICAV2_DEFAULT_BASE_URL
from utils.icav2_helpers import get_icav2_configuration, get_data_obj_by_id, \
    convert_icav2_uri_to_data_obj, is_data_id, get_files_from_directory_id_recursively
from utils.logging import get_logger
from ruamel.yaml import YAML, CommentedMap, CommentedSeq

# Type hinting
from typing import TYPE_CHECKING

from utils.subprocess_handler import run_subprocess_proc

if TYPE_CHECKING:
    from classes.icav2_bunch_classes import \
        Bunch, Dataset

logger = get_logger()


def get_icav2_config_yaml_path() -> Path:
    from utils.repo import get_configuration_path

    return get_configuration_path() / "icav2.yaml"


def read_config_yaml() -> CommentedMap:
    yaml_obj = YAML()
    config_yaml_path = get_icav2_config_yaml_path()

    data = CommentedMap()
    if config_yaml_path.is_file():
        with open(config_yaml_path, 'r') as yaml_h:
            data: CommentedMap = yaml_obj.load(yaml_h)

    return data


def write_config_yaml(data: CommentedMap):
    yaml_obj = YAML()

    yaml_obj.block_seq_indent = 2
    yaml_obj.sequence_indent = 4

    config_yaml_path = get_icav2_config_yaml_path()

    with open(config_yaml_path, 'w') as yaml_h:
        yaml_obj.dump(data, yaml_h)


def add_tenant_to_config_yaml(tenant_name: str):
    data = read_config_yaml()

    if data is None:
        data = CommentedMap()

    if data.get("tenants") is None:
        data["tenants"] = CommentedSeq()
        data.yaml_set_comment_before_after_key(
            key="tenants",
            before="\nList of tenants that datasets / bunches / bundles can be attached to"
        )

    data.yaml_set_comment_before_after_key(
        key="tenants",
        after="\n"
    )

    # Append tenant
    data["tenants"].append(
        {
            "tenant_name": tenant_name
        }
    )

    # Write back to yaml path
    write_config_yaml(data)


def generate_data_id_md5sum(data_list: List[Data]) -> str:
    sorted_data_list_ids = list(
        map(
            # Get the path from the sorted list
            lambda file_item: file_item.id,
            # data list sorted by the path attribute
            sorted(
                data_list,
                key=lambda x: x.id
            )
        )
    )

    data_ids_str = "\n".join(sorted_data_list_ids) + "\n"

    # Now generate the md5sum of this hypothetical text file
    data_ids_md5sum = md5(data_ids_str.encode('utf-8')).hexdigest()

    return data_ids_md5sum


def generate_e_tag_md5sum_from_file_list(data_list: List[Data]) -> str:
    sorted_data_list_etags = list(
        map(
            # Get the etag from the sorted list
            lambda file_item: file_item.details.object_e_tag,
            # data list sorted by the path attribute
            sorted(
                data_list,
                key=lambda x: x.details.path
            )
        )
    )

    # Now append over a new line as if this were the contents of a text file
    # Make sure we add a trailing slash to the end too
    etags_str = "\n".join(sorted_data_list_etags) + "\n"

    # Now generate the md5sum of this hypothetical text file
    etags_md5sum = md5(etags_str.encode('utf-8')).hexdigest()

    return etags_md5sum


def generate_folder_structure_md5sum_from_file_list(data_list: List[Data], parent_folder_path: Path) -> str:
    sorted_data_list_paths = list(
        map(
            # Get the path from the sorted list
            lambda file_item: str(Path(file_item.details.path).relative_to(parent_folder_path)),
            # data list sorted by the path attribute
            sorted(
                data_list,
                key=lambda x: x.details.path
            )
        )
    )

    # Now append over a new line as if this were the contents of a text file
    # Make sure we add a trailing slash to the end too
    paths_str = "\n".join(sorted_data_list_paths) + "\n"

    # Now generate the md5sum of this hypothetical text file
    paths_str_md5sum = md5(paths_str.encode('utf-8')).hexdigest()

    return paths_str_md5sum


def get_folder_specific_dataset_attributes(data_obj: Data) -> Dict:
    """
    Get the following data attributes for a data item of data-type FOLDER
    * num_files
    * folder_size_in_bytes
    * object_e_tag_md5sum
    * folder_structure_md5sum
    :return:
    """
    # Get owning project id from the data object attribute
    project_id = data_obj.details.owning_project_id

    # All subfiles
    all_files = get_files_from_directory_id_recursively(project_id, data_obj.id, get_icav2_configuration())

    # Step 1 -> Find all files within a folder
    num_files = len(all_files)

    # Step 2 -> Calculate file size of all files within a folder
    folder_size_in_bytes = sum(map(lambda file_item: file_item.details.file_size_in_bytes, all_files))

    # Step 3 -> Calculate md5sum from etag list
    object_e_tag_md5sum = generate_e_tag_md5sum_from_file_list(all_files)

    # Step 4 -> Calculate md5sum from folder structure
    folder_structure_md5sum = generate_folder_structure_md5sum_from_file_list(all_files, Path(data_obj.details.path))

    return {
        "num_files": num_files,
        "folder_size_in_bytes": folder_size_in_bytes,
        "object_e_tag_md5sum": object_e_tag_md5sum,
        "folder_structure_md5sum": folder_structure_md5sum
    }


def get_file_specific_dataset_attributes(data_obj: Data) -> Dict:
    """
    Get the following data attributes for a data item of data-type FILE
    :return:
    """

    return {
        "file_size_in_bytes": data_obj.details.file_size_in_bytes,
        "object_e_tag": data_obj.details.object_e_tag
    }


def get_dataset_attributes(data_obj: Data, creator_name_map: Dict) -> Dict:
    """
    Get the data object and return a dict of data set attributes
    :param data_obj:
    :param creator_name_map:
    :return:
    """
    # Generic non-datatype specific
    data_map = {
        "data_id": data_obj.id,
        "data_type": data_obj.details.data_type,
        "owning_project_id": data_obj.details.owning_project_id,
        "owning_project_name": data_obj.details.owning_project_name,
        "data_uri": f"icav2://{data_obj.details.owning_project_name}{data_obj.details.path}",
        "creation_time": data_obj.details.time_created.isoformat(timespec='seconds').replace("+00:00", "Z"),
        "modification_time": data_obj.details.time_modified.isoformat(timespec='seconds').replace("+00:00", "Z")
    }

    if hasattr(data_obj.details, "creator_id"):
        data_map.update(
            {
                "creator_id": data_obj.details.creator_id
            }
        )
        if data_obj.details.creator_id in creator_name_map.keys():
            data_map.update(
                {
                    "creator_name": creator_name_map[data_obj.details.creator_id]
                }
            )

    return data_map


def get_dataset_id_hash(dataset_items):
    object_e_tag_list = []

    # data list sorted by the path attribute
    sorted_dataset_items = sorted(
        dataset_items,
        key=lambda x: urlparse(x.data_uri).netloc + "__" + urlparse(x.data_uri).path
    )

    for dataset_item in sorted_dataset_items:
        if dataset_item.data_type.lower() == "folder":
            object_e_tag_list.append(dataset_item.object_e_tag_md5sum)
        else:
            object_e_tag_list.append(md5(dataset_item.object_e_tag.encode('utf-8')).hexdigest())

    dataset_hash_str = "\n".join(object_e_tag_list) + "\n"

    # Now generate the md5sum of this hypothetical text file
    dataset_id_hash = md5(dataset_hash_str.encode('utf-8')).hexdigest()

    return dataset_id_hash


def check_tenant_in_config_yaml(tenant_name: str) -> bool:
    # Open up icav2 config yaml
    data = read_config_yaml()

    # Check tenants in keys
    if data is None or "tenants" not in data.keys():
        return False

    if tenant_name in map(lambda x: x.get("tenant_name"), data.get("tenants")):
        return True

    return False


def check_project_in_config_yaml(tenant_name: str, project_name: str) -> bool:
    # Open up icav2 config yaml
    data = read_config_yaml()

    # Check tenants in keys
    if data is None or "projects" not in data.keys():
        return False

    tenant_project_list = list(
        map(
            lambda project_dict: project_dict.get("project_name"),
            filter(
                lambda project_dict: project_dict.get("tenant_name") == tenant_name,
                data.get("projects")
            )
        )
    )

    if project_name in tenant_project_list:
        return True

    return False


def add_project_to_config_yaml(tenant_name: str, project_name: str, project_id: str):
    data = read_config_yaml()

    # Check project in keys
    if data.get("projects") is None:
        data["projects"] = CommentedSeq()
        data.yaml_set_comment_before_after_key(
            key="projects",
            before="\nList of projects a bundle can be attached to"
        )

    data.yaml_set_comment_before_after_key(
        key="projects",
        after="\n"
    )

    data["projects"].append(
        {
            "project_name": project_name,
            "project_id": project_id,
            "tenant_name": tenant_name
        }
    )

    write_config_yaml(data)


def get_dataset_from_input_yaml(input_yaml_path: Path) -> Tuple[Optional[str], Optional[str], List[Data]]:
    # Get dataset name
    yaml_obj = YAML()

    # Check input yaml is an actual file
    if not input_yaml_path.is_file():
        logger.error(f"Could not open file {input_yaml_path}")
        raise FileNotFoundError

    # Initialise data
    with open(input_yaml_path, 'r') as yaml_h:
        input_yaml_map: CommentedMap = yaml_obj.load(yaml_h)

    # Dataset name
    if "dataset_name" in input_yaml_map.keys():
        dataset_name = input_yaml_map.get("dataset_name")
    else:
        dataset_name = None

    # Dataset name
    if "dataset_description" in input_yaml_map.keys():
        dataset_description = input_yaml_map.get("dataset_description")
    else:
        dataset_description = None

    dataset_list: List[Data] = []

    # Read data objects
    if "data" in input_yaml_map.keys():
        data: CommentedSeq = input_yaml_map.get("data")

        # Confirm data is a list type
        if not isinstance(data, List):
            logger.error(f"Expected data key to be a list but got '{type(data)}' instead")
            raise ValueError

        for data_item in data:
            if isinstance(data_item, str):
                # Must be of uri origin
                dataset_list.append(
                    get_data_obj_from_data_uri(data_item)
                )
            elif isinstance(data_item, Dict):
                data_attr = data_item.get("data", None)
                data_id_attr = data_item.get("data_id", None)
                data_uri_attr = data_item.get("data_uri", None)
                project_id_attr = data_item.get("project_id", None)
                # Get data id if specified
                if data_id_attr is not None:
                    if not is_data_id(data_id_attr):
                        logger.error(f"Got data_id attribute as {data_id_attr} but this is not a valid data id")
                    # Check project id
                    if project_id_attr is None:
                        logger.error(f"Cannot specfiy a data id {data_attr} without a project id attribute")
                        raise ValueError
                    # Get data item
                    dataset_list.append(
                        get_data_obj_by_id(project_id_attr, data_attr, get_icav2_configuration())
                    )
                # Get data attribute
                if data_attr is not None:
                    if is_data_id(data_attr):
                        # Check project id
                        if project_id_attr is None:
                            logger.error(f"Cannot specfiy a data id {data_attr} without a project id attribute")
                            raise ValueError
                        # Get data item
                        dataset_list.append(
                            get_data_obj_by_id(project_id_attr, data_attr, get_icav2_configuration())
                        )
                    else:
                        dataset_list.append(
                            get_data_obj_from_data_uri(data_attr)
                        )
                elif data_uri_attr is not None:
                    dataset_list.append(
                        get_data_obj_from_data_uri(data_uri_attr)
                    )
                else:
                    logger.error("Must specify one of data, data_id or data_uri keys")
                    raise ValueError

    return dataset_name, dataset_description, dataset_list


def get_data_obj_from_data_uri(data_uri: str) -> Data | List[Data]:
    projectdata_obj: ProjectData = convert_icav2_uri_to_data_obj(data_uri, get_icav2_configuration())
    project_id = projectdata_obj.project_id
    data_obj = projectdata_obj.data
    if data_obj.details.data_type == "FILE":
        return data_obj
    else:
        return get_files_from_directory_id_recursively(project_id, data_obj.get("id"), get_icav2_configuration())


def get_data_obj_from_data_id(project_id: str, data_id: str) -> Data | List[Data]:
    data_obj = get_data_obj_by_id(project_id, data_id, get_icav2_configuration())
    if data_obj.details.data_type == "FILE":
        return data_obj
    else:
        return get_files_from_directory_id_recursively(
            project_id, data_obj.get("id"), get_icav2_configuration()
        )


def get_dataset_from_dataset_name(dataset_name: str) -> Dataset:
    """
    Collect a dataset from the icav2 configuration yaml file
    :param dataset_name:
    :return:
    """
    from classes.icav2_bunch_classes import Dataset
    icav2_datasets_list_dict: List[Dict] = read_config_yaml().get("datasets")

    dataset_dict = next(
        filter(
            lambda x: x.get("dataset_name") == dataset_name,
            icav2_datasets_list_dict
        )
    )

    return Dataset.from_dict(dataset_dict)


def get_bunch_attributes_from_input_yaml(input_yaml_path: Path) -> CommentedMap:
    """
    Get bunch from an input yaml
    :param input_yaml_path:
    :return:
    """
    yaml_obj = YAML()

    if not input_yaml_path.is_file():
        logger.error(f"Cannot read {input_yaml_path}")
        raise FileNotFoundError

    with open(input_yaml_path, 'r') as yaml_h:
        data: CommentedMap = yaml_obj.load(yaml_h)

    return data


def generate_empty_bundle(
        bundle_name: str, bundle_version: str,
        bundle_description: str, bundle_version_description: str,
        region_id: str, categories: List[str],
        pipeline_release_url: str,
        icav2_access_token: str
    ) -> Bundle:
    """
    Generate an empty bundle
    :param bundle_name:
    :param bundle_version:
    :param bundle_description:
    :param bundle_version_description:
    :param region_id:
    :param categories:
    :param pipeline_release_url
    :param icav2_access_token:
    :return:
    """
    # Configuration needs manual work with custom access token
    configuration = Configuration(
        host=os.environ.get("ICAV2_BASE_URL", ICAV2_DEFAULT_BASE_URL),
        access_token=icav2_access_token
    )

    with ApiClient(configuration) as api_client:
        # Create an instance of the API class
        api_instance = BundleApi(api_client)

    create_bundle = CreateBundle(
        name=bundle_name,
        short_description=bundle_description,
        bundle_release_version=bundle_version,
        bundle_version_comment=bundle_version_description,
        region_id=region_id,
        bundle_status="DRAFT",
        categories=categories,
        links=Links(
            links=[
                # Drop link while https://github.com/umccr-illumina/ica_v2/issues/156 is still active
                # Link(
                #     name="GitHub CWL-ICA Release Page",
                #     url=pipeline_release_url
                # )
            ],
            licenses=[],
            homepages=[],
            publications=[]
        )
    )

    # example passing only required values which don't have defaults set
    # and optional values
    try:
        # Create a new bundle
        api_response: Bundle = api_instance.create_bundle(create_bundle=create_bundle)
    except ApiException as e:
        logger.error("Exception when calling BundleApi->create_bundle: %s\n" % e)
        raise ApiException

    return api_response


def add_pipeline_to_bundle(bundle_id: str, pipeline_id: str, icav2_access_token: str):
    """
    Given a bundle id and a pipeline id, add the pipeline to the bundle
    :param bundle_id:
    :param pipeline_id:
    :param icav2_access_token:
    :return:
    """
    # Create pipeline from GitHub release
    proc_environ = os.environ.copy()

    proc_environ.update(
        {
            "PYTHONPATH": f"{os.environ['ICAV2_CLI_PLUGINS_HOME']}/pyenv/lib/python3.10/site-packages/",
            "ICAV2_BASE_URL": ICAV2_DEFAULT_BASE_URL,
            "ICAV2_ACCESS_TOKEN": icav2_access_token
        }
    )

    link_pipeline_command = [
        f"{os.environ['ICAV2_CLI_PLUGINS_HOME']}/pyenv/bin/python",
        f"{os.environ['ICAV2_CLI_PLUGINS_HOME']}/plugins/bin/icav2-cli-plugins.py",
        "bundles",
        "add-pipeline",
        bundle_id,
        "--pipeline-id", pipeline_id
    ]

    link_pipeline_returncode, link_pipeline_stdout, link_pipeline_stderr = run_subprocess_proc(
        link_pipeline_command,
        env=proc_environ,
        capture_output=True
    )

    if not link_pipeline_returncode == 0:
        logger.error(f"{link_pipeline_stdout}")
        logger.error(f"{link_pipeline_stderr}")


def add_data_to_bundle(bundle_id, data_id, icav2_access_token: str):
    """
    Given a bundle id and a data id, add the data id to the bundle
    :param bundle_id:
    :param data_id:
    :return:
    """
    # Create pipeline from GitHub release
    proc_environ = os.environ.copy()

    proc_environ.update(
        {
            "PYTHONPATH": f"{os.environ['ICAV2_CLI_PLUGINS_HOME']}/pyenv/lib/python3.10/site-packages/",
            "ICAV2_BASE_URL": ICAV2_DEFAULT_BASE_URL,
            "ICAV2_ACCESS_TOKEN": icav2_access_token
        }
    )

    link_data_command = [
        f"{os.environ['ICAV2_CLI_PLUGINS_HOME']}/pyenv/bin/python",
        f"{os.environ['ICAV2_CLI_PLUGINS_HOME']}/plugins/bin/icav2-cli-plugins.py",
        "bundles",
        "add-data",
        bundle_id,
        "--data-id", data_id
    ]

    link_data_returncode, link_data_stdout, link_data_stderr = run_subprocess_proc(
        link_data_command,
        env=proc_environ,
        capture_output=True
    )

    if not link_data_returncode == 0:
        logger.error(f"{link_data_stdout}")
        logger.error(f"{link_data_stderr}")


def release_bundle(bundle_id: str, icav2_access_token: str):
    """
    Release a bundle
    :param bundle_id:
    :param icav2_access_token:
    :return:
    """
    # Create pipeline from GitHub release
    proc_environ = os.environ.copy()

    proc_environ.update(
        {
            "PYTHONPATH": f"{os.environ['ICAV2_CLI_PLUGINS_HOME']}/pyenv/lib/python3.10/site-packages/",
            "ICAV2_BASE_URL": ICAV2_DEFAULT_BASE_URL,
            "ICAV2_ACCESS_TOKEN": icav2_access_token
        }
    )

    release_bundle_command = [
        f"{os.environ['ICAV2_CLI_PLUGINS_HOME']}/pyenv/bin/python",
        f"{os.environ['ICAV2_CLI_PLUGINS_HOME']}/plugins/bin/icav2-cli-plugins.py",
        "bundles",
        "release",
        bundle_id
    ]

    release_bundle_returncode, release_bundle_stdout, release_bundle_stderr = run_subprocess_proc(
        release_bundle_command,
        env=proc_environ,
        capture_output=True
    )

    if not release_bundle_returncode == 0:
        logger.error(f"{release_bundle_stdout}")
        logger.error(f"{release_bundle_stderr}")


def add_bundle_to_project(project_id: str, bundle_id: str, icav2_access_token: str):
    """
    Add a bundle to a project
    :param project_id:
    :param bundle_id:
    :param icav2_access_token:
    :return:
    """
    # Create pipeline from GitHub release
    proc_environ = os.environ.copy()

    proc_environ.update(
        {
            "PYTHONPATH": f"{os.environ['ICAV2_CLI_PLUGINS_HOME']}/pyenv/lib/python3.10/site-packages/",
            "ICAV2_BASE_URL": ICAV2_DEFAULT_BASE_URL,
            "ICAV2_ACCESS_TOKEN": icav2_access_token
        }
    )

    add_bundle_to_project_command = [
        f"{os.environ['ICAV2_CLI_PLUGINS_HOME']}/pyenv/bin/python",
        f"{os.environ['ICAV2_CLI_PLUGINS_HOME']}/plugins/bin/icav2-cli-plugins.py",
        "bundles",
        "add-bundle-to-project",
        bundle_id,
        "--project", project_id
    ]

    add_bundle_to_project_returncode, add_bundle_to_project_stdout, add_bundle_to_project_stderr = run_subprocess_proc(
        add_bundle_to_project_command,
        env=proc_environ,
        capture_output=True
    )

    if not add_bundle_to_project_returncode == 0:
        logger.error(f"{add_bundle_to_project_stdout}")
        logger.error(f"{add_bundle_to_project_stderr}")


def get_projects_from_v2_config_yaml() -> List[Dict]:
    return read_config_yaml().get("projects")


def get_project_id_from_project_name(tenant_name: str, project_name: str) -> Optional[str]:
    """
    Read in the project configuration from the v2 configuration yaml
    Then return the project id for a given project name
    :param tenant_name:
    :param project_name:
    :return:
    """

    try:
        return next(
                filter(
                    lambda project_dict:
                        project_dict.get("project_name") == project_name and
                        project_dict.get("tenant_name") == tenant_name,
                    get_projects_from_v2_config_yaml()
                )
            ).get("project_id")
    except StopIteration:
        logger.error(f"Could not get project id from {tenant_name} / {project_name}")
        raise ProjectNotFoundError


def get_bunch_names() -> List[str]:
    v2_config_yaml = read_config_yaml()

    return list(
        map(
            lambda bunch_dict: bunch_dict.get("bunch_name"),
            v2_config_yaml.get("bunches", [])
        )
    )


def get_bunch_from_bunch_name(bunch_name: str) -> Bunch:
    from classes.icav2_bunch_classes import Bunch

    v2_config_yaml = read_config_yaml()

    if bunch_name not in get_bunch_names():
        logger.error(f"Cannot get bunch object from bunch name '{bunch_name}'")
        raise BunchNotFoundError

    bunch_dict: Dict = next(
        filter(
            lambda bunch_item: bunch_item.get("bunch_name") == bunch_name,
            v2_config_yaml.get("bunches")
        )
    )

    return Bunch.from_dict(bunch_dict)


def get_project_name_from_project_id(tenant_name: str, project_id: str) -> str:
    """
    Get project name / project id
    :param tenant_name:
    :param pipeline_project_id:
    :return:
    """
    try:
        return next(
                filter(
                    lambda project_dict:
                        project_dict.get("project_id") == project_id and
                        project_dict.get("tenant_name") == tenant_name,
                    get_projects_from_v2_config_yaml()
                )
            ).get("project_name")
    except StopIteration:
        logger.error(f"Could not get project id from {tenant_name} / {project_id}")
        raise ProjectNotFoundError


def get_pipeline_code_from_pipeline_id(pipeline_id, icav2_access_token) -> str:
    """
    Given a pipeline name,
    :param pipeline_id:
    :param icav2_access_token:
    :return:
    """
    configuration = Configuration(
        host=os.environ.get("ICAV2_BASE_URL", ICAV2_DEFAULT_BASE_URL),
        access_token=icav2_access_token
    )

    # Enter a context with an instance of the API client
    with ApiClient(configuration) as api_client:
        # Create an instance of the API class
        api_instance = PipelineApi(api_client)

        # example passing only required values which don't have defaults set
        try:
            # Retrieve a pipeline.
            api_response: Pipeline = api_instance.get_pipeline(pipeline_id)
        except ApiException as e:
            logger.error("Exception when calling PipelineApi->get_pipeline: %s\n" % e)
            raise ApiException

    return api_response.code


def get_tenant_access_token(tenant_name) -> str:
    tenant_env_var_name = f"ICAV2_ACCESS_TOKEN_{tenant_name.replace('-', '_').upper()}"
    tenant_env_var = os.environ.get(tenant_env_var_name, None)

    if tenant_env_var is not None:
        return tenant_env_var

    # Check if standard token is available
    standard_env_var = os.environ.get("ICAV2_ACCESS_TOKEN", None)

    if standard_env_var is not None:
        return standard_env_var

    logger.error(f"Could not get env var '{tenant_env_var_name}' or ICAV2_ACCESS_TOKEN")
    raise EnvironmentError
