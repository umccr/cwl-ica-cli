#!/usr/bin/env python3

"""
Use libica v2 where possible.

Otherwise run command manually through curl
"""
import tempfile
import requests

from libica.openapi.v2.api.project_analysis_api import ProjectAnalysisApi
from libica.openapi.v2.api.region_api import RegionApi
from libica.openapi.v2.api.user_api import UserApi
from libica.openapi.v2.model.analysis import Analysis
from libica.openapi.v2.model.analysis_step import AnalysisStep
from libica.openapi.v2.model.analysis_step_list import AnalysisStepList
from libica.openapi.v2.model.analysis_step_logs import AnalysisStepLogs
from libica.openapi.v2.model.create_cwl_analysis import CreateCwlAnalysis
from libica.openapi.v2.model.create_data import CreateData
from libica.openapi.v2.model.data import Data
from libica.openapi.v2.model.pipeline import Pipeline
from libica.openapi.v2.model.project import Project
from libica.openapi.v2.model.project_data import ProjectData
from libica.openapi.v2.model.project_data_paged_list import ProjectDataPagedList
from libica.openapi.v2.model.region import Region
from libica.openapi.v2.model.user import User

from utils.cwl_helper_utils import get_fragment_from_cwl_id
from utils.globals import ICAV2_DEFAULT_BASE_URL

import os
import json
from urllib.parse import urlparse

import libica
import libica.openapi.v2
from libica.openapi.v2 import Configuration, ApiClient, ApiException
from libica.openapi.v2.api.project_data_api import ProjectDataApi
from libica.openapi.v2.api.project_api import ProjectApi
from libica.openapi.v2.api.analysis_storage_api import AnalysisStorageApi
from libica.openapi.v2.model.analysis_input_data_mount import AnalysisInputDataMount
from libica.openapi.v2.api.pipeline_api import PipelineApi
from libica.openapi.v2.model.pipeline_list import PipelineList

from utils.miscell import check_shlex_arg
from utils.subprocess_handler import run_subprocess_proc
from utils.globals import ICAv2AnalysisStorageSize
from pathlib import Path
from uuid import UUID


from typing import List, Dict, Union, Any, Tuple

from datetime import datetime
import hashlib

from zipfile import ZipFile
from tempfile import TemporaryDirectory

from utils.logging import get_logger

logger = get_logger()


def create_workflow_from_zip_path(zip_path: Path, project_id: str, analysis_storage_id: str, configuration: Configuration) -> Tuple[str, str]:
    # Create tempdir
    extraction_tempdir = TemporaryDirectory()

    # Check zip path exists
    if not zip_path.is_file():
        logger.error(f"Tried to extract {zip_path} which does not exist")
        raise FileNotFoundError

    # loading the temp.zip and creating a zip object
    with ZipFile(zip_path, 'r') as zip_obj:
        # Extracting all the members of the zip 
        # into a specific location.
        zip_obj.extractall(
            path=extraction_tempdir.name
        )

    # Get workflow files
    workflow_files = [
        workflow_file
        for workflow_file in (Path(extraction_tempdir.name) / Path(zip_path.stem)).rglob("*")
        if workflow_file.is_file()
    ]

    workflow_file = list(filter(lambda x: x.name == "workflow.cwl", workflow_files))[0]
    params_xml_file = list(filter(lambda x: x.name == "params.xml", workflow_files))[0]
    tool_files = list(filter(lambda x: x.name not in ["workflow.cwl", "params.xml"], workflow_files))

    # Get code
    date_str = datetime.today().strftime("%Y%m%d%H%M%S")
    md5sum = hashlib.md5(open(zip_path, 'rb').read()).hexdigest()

    code = "--".join([
        zip_path.stem.replace(".", "_"),
        date_str,
        md5sum
    ])

    # Check code is valid
    check_shlex_arg("workflow code", code)

    curl_command_list = [
        "curl",
        "--fail", "--silent", "--location",
        "--request", "POST",
        "--header", "Accept: application/vnd.illumina.v3+json",
        "--header", f"Authorization: Bearer {configuration.access_token}",
        "--header", "Content-Type: multipart/form-data",
        "--url", f"https://ica.illumina.com/ica/rest/api/projects/{project_id}/pipelines:createCwlPipeline",
        "--form", f"code={code}",
        "--form", f"description=nulldescription",  # FIXME
        "--form", f"workflowCwlFile=@{workflow_file};filename=workflow.cwl",
        "--form", f"parametersXmlFile=@{params_xml_file};filename=params.xml;type=text/xml",
        "--form", f"analysisStorageId={analysis_storage_id}"
    ]

    for tool_file in tool_files:
        curl_command_list.extend([
            "--form",
            f"toolCwlFiles=@{tool_file};filename={tool_file.relative_to(Path(extraction_tempdir.name) / Path(zip_path.stem))}"
        ])

    command_returncode, command_stdout, command_stderr = run_subprocess_proc(curl_command_list, capture_output=True)
    pipeline_id = json.loads(command_stdout).get("pipeline").get("id")

    return pipeline_id, code


def get_icav2_configuration() -> Configuration:
    host = os.environ.get("ICAV2_BASE_URL", ICAV2_DEFAULT_BASE_URL)
    access_token = os.environ.get("ICAV2_ACCESS_TOKEN", None)

    if access_token is None:
        logger.error(
            "Could not get ICAV2_ACCESS_TOKEN env var\n"
            "You can source the ICAV2_ACCESS_TOKEN in your bashrc or equivalent with the following command\n"
            "`yq '.access-token' \"$HOME/.icav2/.session.ica.yaml\"`"
        )

    return Configuration(
        host=host,
        access_token=access_token
    )


def get_project_id_from_project_name(project_name: str, configuration: Configuration) -> str:
    with ApiClient(configuration) as api_client:
        # Create an instance of the API class
        api_instance = ProjectApi(api_client)
        include_hidden_projects = True  # bool, none_type | Include hidden projects. (optional) if omitted the server will use the default value of False
        # Dont expect over 1000 projects tbh
        page_size = 1000  # str | The amount of rows to return. Use in combination with the offset or cursor parameter to get subsequent results. (optional)

        # example passing only required values which don't have defaults set
        # and optional values
        try:
            # Retrieve a list of projects.
            api_response = api_instance.get_projects(
                search=project_name,
                include_hidden_projects=include_hidden_projects,
                page_size=str(page_size)
            )
        except libica.openapi.v2.ApiException as e:
            raise ValueError("Exception when calling ProjectApi->get_projects: %s\n" % e)

    project_list: List = api_response.items
    project_list = list(filter(lambda x: x.name == project_name, project_list))

    if len(project_list) == 0:
        raise ValueError("Could not find project")
    elif len(project_list) == 1:
        return project_list[0].id
    else:
        raise ValueError(f"Got multiple IDs for project name {project_name}")


def is_project_id_format(project_id: str) -> bool:
    try:
        _ = UUID(project_id, version=4)
        return True
    except ValueError:
        return False


def get_pipeline_id_from_pipeline_code(pipeline_code: str, configuration: Configuration) -> str:
    # Enter a context with an instance of the API client
    with libica.openapi.v2.ApiClient(configuration) as api_client:
        # Create an instance of the API class
        api_instance = PipelineApi(api_client)

        # example, this endpoint has no required or optional parameters
        try:
            # Retrieve a list of pipelines.
            api_response: PipelineList = api_instance.get_pipelines()
        except libica.openapi.v2.ApiException as e:
            raise ValueError("Exception when calling PipelineApi->get_pipelines: %s\n" % e)

    pipeline_obj: Pipeline
    for pipeline_obj in api_response.items:
        if pipeline_obj.code == pipeline_code:
            return pipeline_obj.id
    else:
        raise ValueError(f"Could not find pipeline with code {pipeline_code}")


def get_set_analysis_storage_id_from_pipeline(pipeline_id: str, configuration: Configuration) -> str:
    # Enter a context with an instance of the API client
    with libica.openapi.v2.ApiClient(configuration) as api_client:
        # Create an instance of the API class
        api_instance = PipelineApi(api_client)

        # example passing only required values which don't have defaults set
        try:
            # Retrieve a pipeline.
            api_response: Pipeline = api_instance.get_pipeline(pipeline_id)
        except libica.openapi.v2.ApiException as e:
            raise ValueError("Exception when calling PipelineApi->get_pipeline: %s\n" % e)

    return api_response.analysis_storage.id


def create_download_url(project_id: str, data_id: str, configuration: Configuration) -> str:
    # Enter a context with an instance of the API client
    #  with ApiClient(configuration) as api_client:
    #      # Create an instance of the API class
    #      api_instance = ProjectDataApi(api_client)
    #      # example passing only required values which don't have defaults set
    #      try:
    #          # Retrieve a download URL for this data.
    #          api_response = api_instance.create_download_url_for_data(project_id, data_id)
    #      except libica.openapi.v2.ApiException as e:
    #          raise ValueError("Exception when calling ProjectDataApi->create_download_url_for_data: %s\n" % e)
    #  return api_response.url
    curl_command_list = [
        "curl",
        "--fail", "--silent", "--location",
        "--request", "POST",
        "--url", f"https://ica.illumina.com/ica/rest/api/projects/{project_id}/data/{data_id}:createDownloadUrl",
        "--header", "Accept: application/vnd.illumina.v3+json",
        "--header", f"Authorization: Bearer {configuration.access_token}",
        "--data", ""
    ]

    command_returncode, command_stdout, command_stderr = run_subprocess_proc(curl_command_list, capture_output=True)

    if not command_returncode == 0:
        logger.error(f"Could not create a download url for project id '{project_id}', data id '{data_id}'")
        raise ValueError

    return json.loads(command_stdout).get("url")


def write_icav2_file_contents(project_id: str, data_id, output_path: Path, configuration: Configuration):
    download_url = create_download_url(project_id, data_id, configuration)
    r = requests.get(download_url)
    with open(output_path, "wb") as f_h:
        f_h.write(r.content)


def get_files_from_directory_id_recursively(project_id: str, data_id: str, configuration: Configuration) -> List[Data]:
    """
    Get files from directory
    :param project_id:
    :param data_id:
    :param configuration:
    :return:
    """

    # Initialise return value
    data_items: List[Data] = []

    # Create instance
    with ApiClient(configuration) as api_client:
        # Create an instance of the API class
        api_instance = ProjectDataApi(api_client)

    next_page_token = None
    first_iter = True
    response_items: List[Data] = []
    page_size = 1000

    # Iterate through data list while page token is not none
    while next_page_token is not None or first_iter:
        # First iteration now false
        first_iter = False

        # example passing only required values which don't have defaults set
        try:
            # Retrieve the list of project data.
            api_response: ProjectDataPagedList = api_instance.get_project_data_list(
                project_id,
                page_token=next_page_token,
                parent_folder_id=[data_id],
                page_size=str(page_size)
            )
        except libica.openapi.v2.ApiException as e:
            raise ValueError("Exception when calling ProjectDataApi->get_project_data_list: %s\n" % e)

        # Get page tokmen
        next_page_token = api_response.next_page_token

        # Append response items
        response_items.extend(api_response.items)

    for data_item in response_items:
        data_type: str = data_item.get("data").get("details").get('data_type')  # One of FILE | FOLDER
        data_id = data_item.get("data").get("id")
        if data_type == "FILE":
            data_items.append(data_item)
        if data_type == "FOLDER":
            data_items.extend(get_files_from_directory_id_recursively(project_id, data_id, configuration))

    return data_items


def get_files_from_directory_id_non_recursively(project_id: str, data_id: str, configuration: Configuration) -> List[Data]:
    # Enter a context with an instance of the API client
    with ApiClient(configuration) as api_client:
        # Create an instance of the API class
        api_instance = ProjectDataApi(api_client)
        # file_path = [
        #    data_path,
        # ] # [str] | The paths of the files to filter on. (optional)
        # file_path_match_mode = "FULL_CASE_INSENSITIVE" # str | How the file paths are filtered:   - STARTS_WITH_CASE_INSENSITIVE: Filters the file path to start with the value of the 'filePath' parameter, regardless of upper/lower casing. This allows e.g. listing all data in a folder and all it's sub-folders (recursively).  - FULL_CASE_INSENSITIVE: Filters the file path to fully match the value of the 'filePath' parameter, regardless of upper/lower casing. Note that this can result in multiple results if e.g. two files exist with the same filename but different casing (abc.txt and ABC.txt). (optional) if omitted the server will use the default value of "STARTS_WITH_CASE_INSENSITIVE"
        page_size = 1000  # str | The amount of rows to return. Use in combination with the offset or cursor parameter to get subsequent results. (optional)

        # example passing only required values which don't have defaults set
        try:
            # Retrieve the list of project data.
            api_response = api_instance.get_project_data_list(
                project_id,
                parent_folder_id=[data_id],
                page_size=str(page_size)
            )
        except libica.openapi.v2.ApiException as e:
            raise ValueError("Exception when calling ProjectDataApi->get_project_data_list: %s\n" % e)

    project_data_list = api_response.items

    return project_data_list


def get_data_obj_from_project_id_and_path(project_id: str, data_path: str, configuration: Configuration) -> ProjectData:
    # Enter a context with an instance of the API client
    with ApiClient(configuration) as api_client:
        # Create an instance of the API class
        api_instance = ProjectDataApi(api_client)
        file_path = [
            data_path,
        ]  # [str] | The paths of the files to filter on. (optional)
        file_path_match_mode = "FULL_CASE_INSENSITIVE"  # str | How the file paths are filtered:   - STARTS_WITH_CASE_INSENSITIVE: Filters the file path to start with the value of the 'filePath' parameter, regardless of upper/lower casing. This allows e.g. listing all data in a folder and all it's sub-folders (recursively).  - FULL_CASE_INSENSITIVE: Filters the file path to fully match the value of the 'filePath' parameter, regardless of upper/lower casing. Note that this can result in multiple results if e.g. two files exist with the same filename but different casing (abc.txt and ABC.txt). (optional) if omitted the server will use the default value of "STARTS_WITH_CASE_INSENSITIVE"
        data_type = "FOLDER" if data_path.endswith("/") else "FILE"
        parent_folder_path = str(Path(data_path).parent) + "/"
        page_size = 1000  # str | The amount of rows to return. Use in combination with the offset or cursor parameter to get subsequent results. (optional)

        # example passing only required values which don't have defaults set
        try:
            # Retrieve the list of project data.
            api_response = api_instance.get_project_data_list(
                project_id,
                file_path=file_path,
                file_path_match_mode=file_path_match_mode,
                type=data_type,
                parent_folder_path=parent_folder_path,
                page_size=str(page_size)
            )
        except libica.openapi.v2.ApiException as e:
            raise ValueError("Exception when calling ProjectDataApi->get_project_data_list: %s\n" % e)

    project_data_list = api_response.items
    if len(project_data_list) == 0:
        raise FileNotFoundError(f"Could not find the file/directory {data_path} in project {project_id}")
    elif len(project_data_list) == 1:
        return project_data_list[0]
    else:
        raise FileNotFoundError(f"Found multiple results for {data_path} in project {project_id}")


def get_data_obj_by_id(project_id: str, data_id: str, configuration: Configuration) -> Data:
    # Enter a context with an instance of the API client
    with ApiClient(configuration) as api_client:
        # Create an instance of the API class
        api_instance = ProjectDataApi(api_client)

        # example passing only required values which don't have defaults set
        try:
            # Retrieve a project data.
            api_response = api_instance.get_project_data(project_id, data_id)
        except libica.openapi.v2.ApiException as e:
            raise ValueError("Exception when calling ProjectDataApi->get_project_data: %s\n" % e)
    return api_response.data


def presign_cwl_directory(project_id: str, data_id: str, configuration: Configuration) -> List[
    Union[Dict[str, Union[Union[dict, str], Any]], Dict[str, Union[str, Any]]]]:
    # Data ids
    cwl_item_objs = []

    # List items noncursively
    file_obj_list = get_files_from_directory_id_non_recursively(project_id, data_id, configuration)

    # Collect file object list
    for file_item_obj in file_obj_list:
        data_type: str = file_item_obj.get("data").get("details").get('data_type')  # One of FILE | FOLDER
        data_id = file_item_obj.get("data").get("id")
        basename = file_item_obj.get("data").get("details").get("name")
        if data_type == "FOLDER":
            cwl_item_objs.append(
                {
                    "class": "Directory",
                    "basename": basename,
                    "listing": presign_cwl_directory(project_id, data_id, configuration)
                }
            )
        else:
            cwl_item_objs.append(
                {
                    "class": "File",
                    "basename": basename,
                    "location": create_download_url(project_id, data_id, configuration)
                }
            )

    return cwl_item_objs


def convert_icav2_uri_to_data_obj(uri: str, configuration) -> ProjectData:
    # Parse obj
    uri_obj = urlparse(uri)

    # Get project name or id
    project_name_or_id = uri_obj.netloc

    # Get data path
    data_path = uri_obj.path

    # Get project id
    if is_project_id_format(project_name_or_id):
        project_id = project_name_or_id
    else:
        project_id = get_project_id_from_project_name(project_name_or_id, configuration)

    # Get data path
    return get_data_obj_from_project_id_and_path(project_id, data_path, configuration)


def convert_icav2_uris_to_data_ids(input_obj: Union[str, int, bool, Dict, List], configuration) -> Tuple[
    Union[str, Dict, List], List[Dict]]:
    # Set default mount_list
    mount_list = []

    # Convert basic types
    if isinstance(input_obj, bool) or isinstance(input_obj, int) or isinstance(input_obj, str):
        return input_obj, mount_list

    # Convert dict or list types recursively
    if isinstance(input_obj, List):
        input_obj_new_list = []
        for input_item in input_obj:
            input_obj_new_item, mount_list_new = convert_icav2_uris_to_data_ids(input_item, configuration)
            mount_list.extend(mount_list_new)
            input_obj_new_list.append(input_obj_new_item)
        return input_obj_new_list, mount_list
    if isinstance(input_obj, Dict):
        if "class" in input_obj.keys() and input_obj["class"] in ["File", "Directory"]:
            if input_obj.get("location", "").startswith("icav2://"):
                # Get relative location path
                input_obj_new: ProjectData = convert_icav2_uri_to_data_obj(input_obj.get("location"), configuration)
                data_type: str = input_obj_new.get("data").get("details").get('data_type')  # One of FILE | FOLDER
                owning_project_id: str = input_obj_new.get("data").get("details").get("owning_project_id")
                data_id = input_obj_new.get("data").get("id")
                basename = input_obj_new.get("data").get("details").get("name")
                # Check presign, # FIXME also functionalise this, may need this for cross-tenant data collection later
                presign_list = list(filter(lambda x: x == "presign=true", urlparse(input_obj.get("location")).query.split("&")))
                if len(presign_list) > 0:
                    is_presign = True
                else:
                    is_presign = False

                # Set mount path
                mount_path = str(
                    Path(owning_project_id) /
                    Path(data_id) /
                    Path(basename)
                )

                # Check data types match
                if data_type == "FOLDER" and input_obj["class"] == "File":
                    logger.error("Got mismatch on data type and class for input object")
                    logger.error(f"Class of {input_obj.get('location')} is set to file but found directory id {data_id} instead")
                    raise ValueError
                if data_type == "FILE" and input_obj["class"] == "Directory":
                    logger.error("Got mismatch on data type and class for input object")
                    logger.error(f"Class of {input_obj.get('location')} is set to directory but found file id {data_id} instead")

                # Mount folder at top of directory
                if data_type == "FOLDER":
                    # Folders can only be mounted at the top dir now
                    # See https://github.com/umccr-illumina/ica_v2/issues/99
                    mount_path = str(Path(mount_path).name) + "/"

                # Set file to presigned url
                if data_type == "FILE" and is_presign:
                    input_obj["location"] = create_download_url(owning_project_id, data_id, configuration)
                # Set data folder as streamable recursively
                elif data_type == "FOLDER" and is_presign:
                    input_obj["location"] = mount_path
                    input_obj["listing"] = presign_cwl_directory(
                        owning_project_id, data_id, configuration
                    )
                else:
                    mount_list.append(
                        AnalysisInputDataMount(
                            data_id=data_id,
                            mount_path=mount_path
                        )
                    )

                    input_obj["location"] = mount_path

                return input_obj, mount_list
        else:
            input_obj_new = {}
            for key, value in input_obj.items():
                input_obj_new[key], mount_list_new = convert_icav2_uris_to_data_ids(value, configuration)
                mount_list.extend(mount_list_new)
            return input_obj_new, mount_list


def get_activation_id(project_id: str, pipeline_id: str, input_json: Dict,
                      mount_list: List[AnalysisInputDataMount], configuration: Configuration) -> str:
    # Collect access token
    icav2_access_token = configuration.access_token

    # Curl command waiting on https://github.com/umccr-illumina/libica/issues/75 to be resolved
    curl_command_list = [
        "curl",
        "--fail", "--silent", "--location",
        "--request", "POST",
        "--url", "https://ica.illumina.com/ica/rest/api/activationCodes:findBestMatchingForCwl",
        "--header", "Accept: application/vnd.illumina.v3+json",
        "--header", f"Authorization: Bearer {icav2_access_token}",
        "--header", "Content-Type: application/vnd.illumina.v3+json",
        "--data", json.dumps(
            {

                "projectId": project_id,
                "pipelineId": pipeline_id,
                "analysisInput": {
                    "objectType": "JSON",
                    "inputJson": json.dumps(input_json),
                    "dataIds": list(map(lambda x: x.data_id, mount_list)),
                    "mounts": [
                        {
                            "dataId": mount_item.data_id,
                            "mountPath": mount_item.mount_path
                        }
                        for mount_item in mount_list
                    ]
                }
            }
        )
    ]

    command_returncode, command_stdout, command_stderr = run_subprocess_proc(curl_command_list, capture_output=True)

    return json.loads(command_stdout).get("id")


def get_analysis_storage_id_from_analysis_storage_size(analysis_storage_size: ICAv2AnalysisStorageSize, configuration: Configuration) -> str:
    with ApiClient(configuration) as api_client:
        # Create an instance of the API class
        api_instance = AnalysisStorageApi(api_client)

        # example, this endpoint has no required or optional parameters
        try:
            # Retrieve the list of analysis storage options.
            api_response = api_instance.get_analysis_storage_options()
        except libica.openapi.v2.ApiException as e:
            raise ValueError("Exception when calling AnalysisStorageApi->get_analysis_storage_options: %s\n" % e)

    analysis_storage_list = list(
        filter(lambda x: x.name == analysis_storage_size.value,
               api_response.items
               )
    )

    if len(analysis_storage_list) == 0:
        raise ValueError(f"Could not find analysis storage size {analysis_storage_size} in this region")

    return analysis_storage_list[0].id


def create_data_obj_from_project_id_and_path(project_id: str, data_path: str, configuration: Configuration) -> str:
    # Enter a context with an instance of the API client
    with libica.openapi.v2.ApiClient(configuration) as api_client:
        # Create an instance of the API class
        api_instance = ProjectDataApi(api_client)
        create_data = CreateData(
            name=Path(data_path).name,
            folder_path=str(Path(data_path).parent) + "/",
            data_type="FOLDER" if data_path.endswith("/") else "FILE",
        )  # CreateData | The data to create. (optional)

        # example passing only required values which don't have defaults set
        try:
            # Create data in this project.
            api_response: ProjectData = api_instance.create_data_in_project(project_id, create_data=create_data)
        except libica.openapi.v2.ApiException as e:
            raise ValueError("Exception when calling ProjectDataApi->create_data_in_project: %s\n" % e)

    return api_response.data.id


def launch_workflow(
        project_id: str,
        cwl_analysis: CreateCwlAnalysis,
        configuration: Configuration) -> Tuple[str, str]:
    # Enter a context with an instance of the API client
    with libica.openapi.v2.ApiClient(configuration) as api_client:
        # Create an instance of the API class
        api_instance = ProjectAnalysisApi(api_client)

        # example passing only required values which don't have defaults set
        try:
            # Create and start an analysis for a CWL pipeline.
            api_response: Analysis = api_instance.create_cwl_analysis(project_id, create_cwl_analysis=cwl_analysis)
        except libica.openapi.v2.ApiException as e:
            raise ValueError("Exception when calling ProjectAnalysisApi->create_cwl_analysis: %s\n" % e)

    return api_response.id, api_response.user_reference


def get_workflow_steps(project_id: str, analysis_id: str, configuration: Configuration) -> List[AnalysisStep]:
    # Enter a context with an instance of the API client
    with libica.openapi.v2.ApiClient(configuration) as api_client:
        # Create an instance of the API class
        api_instance = ProjectAnalysisApi(api_client)

        # example passing only required values which don't have defaults set
        try:
            # Retrieve the individual steps of an analysis.
            api_response: AnalysisStepList = api_instance.get_analysis_steps(
                project_id,
                analysis_id
            )
        except libica.openapi.v2.ApiException as e:
            raise ValueError("Exception when calling ProjectAnalysisApi->get_analysis_steps: %s\n" % e)

    return api_response.items


def filter_analysis_steps(workflow_steps: List[AnalysisStep], show_technical_steps=False) -> List[Dict]:
    # Filter steps
    workflow_steps_filtered: List[Dict] = []
    for workflow_step in workflow_steps:
        # Skip technical steps if required
        if workflow_step.technical and not show_technical_steps:
            continue

        workflow_step_dict = {
            "name": get_fragment_from_cwl_id(workflow_step.name),
            "status": workflow_step.status
        }

        for date_item in ["queue_date", "start_date", "end_date"]:
            if hasattr(workflow_step, date_item) and getattr(workflow_step, date_item) is not None:
                date_obj: datetime = getattr(workflow_step, date_item)
                workflow_step_dict[date_item] = date_obj.strftime("%Y-%m-%dT%H:%M:%SZ")

        workflow_steps_filtered.append(
            workflow_step_dict
        )

    return workflow_steps_filtered


def write_analysis_step_logs(step_logs: AnalysisStepLogs, project_id: str, log_name: str, output_path: Path, configuration: Configuration, is_cwltool_log=False):
    # Check if we're getting our log from a stream
    is_stream = False
    log_stream = None
    log_data_id = ""

    non_empty_log_attrs = []
    # Check attributes of log obj
    for attr in dir(step_logs):
        if attr.startswith('_'):
            continue
        if getattr(step_logs, attr) is None:
            continue
        non_empty_log_attrs.append(attr)

    if log_name == "stdout":
        if hasattr(step_logs, "std_out_stream") and step_logs.std_out_stream is not None:
            is_stream = True
            log_stream = step_logs.std_out_stream
        elif hasattr(step_logs, "std_out_data") and step_logs.std_out_data is not None:
            log_data_id: str = step_logs.std_out_data.id
        else:
            logger.error("Could not get either file output or stream of logs")
            logger.error(f"The available attributes were {', '.join(non_empty_log_attrs)}")
            raise AttributeError
    else:
        if hasattr(step_logs, "std_err_stream") and step_logs.std_err_stream is not None:
            is_stream = True
            log_stream = step_logs.std_err_stream
        elif hasattr(step_logs, "std_err_data") and step_logs.std_err_data is not None:
            log_data_id: str = step_logs.std_err_data.id
        else:
            logger.error("Could not get either file output or stream of logs")
            logger.error(f"The available attributes were {', '.join(non_empty_log_attrs)}")
            raise AttributeError
    if is_stream:
        from utils.icav2_websocket_helpers import write_websocket_to_file, convert_html_to_text
        if is_cwltool_log:
            temp_html_obj = tempfile.NamedTemporaryFile()
            write_websocket_to_file(log_stream,
                                    output_file=Path(temp_html_obj.name))
            convert_html_to_text(Path(temp_html_obj.name), output_path)
        else:
            write_websocket_to_file(log_stream,
                                    output_file=output_path)
    else:
        write_icav2_file_contents(project_id, log_data_id, output_path, configuration)


def recursively_build_open_api_body_from_libica_item(libica_item: Any) -> Union[Dict, Any]:
    if not isinstance(libica_item, object) or isinstance(libica_item, str):
        return libica_item
    open_api_body_dict = {}
    for key, value in libica_item._data_store.items():
        if isinstance(value, List):
            output_value = [
                recursively_build_open_api_body_from_libica_item(value_item)
                for value_item in value
            ]
        elif isinstance(value, object) and hasattr(value, "_data_store"):
            output_value = recursively_build_open_api_body_from_libica_item(value)
        else:
            output_value = value
        open_api_body_dict[libica_item.attribute_map.get(key)] = output_value
    return open_api_body_dict


def get_region_obj_from_project_id(project_id: str, configuration: Configuration) -> Region:
    """
    Collect the region object from the project id
    :param project_id:
    :param configuration:
    :return:
    """
    with ApiClient(configuration) as api_client:
        api_instance = ProjectApi(api_client)

    try:
        api_response = api_instance.get_project(project_id)
    except ApiException as e:
        logger.error("Exception when calling ProjectApi->get_project: %s\n" % e)
        raise ApiException

    return api_response.region


def is_data_id(data_str: str) -> bool:
    if data_str.startswith("fil.") or data_str.startswith("fol."):
        return True
    return False


def get_creator_name_from_creator_id(creator_id: str,  configuration: Configuration) -> str:
    """

    :param creator_id:
    :param configuration:
    :return:
    """
    with ApiClient(configuration) as api_client:
        # Create an instance of the API class
        api_instance = UserApi(api_client)

    # example passing only required values which don't have defaults set
    try:
        # Retrieve a user.
        api_response: User = api_instance.get_user(creator_id)
    except ApiException as e:
        logger.error("Exception when calling UserApi->get_user: %s\n" % e)
        raise ApiException

    return api_response.username


def get_regions(configuration: Configuration) -> List[Region]:
    """
    Return a list of regions
    :return:
    """
    with ApiClient(configuration) as api_client:
        # Create an instance of the API class
        api_instance = RegionApi(api_client)

    # example, this endpoint has no required or optional parameters
    try:
        # Retrieve a list of regions. Only the regions the user has access to through his/her entitlements are returned.
        api_response = api_instance.get_regions()
    except ApiException as e:
        logger.error("Exception when calling RegionApi->get_regions: %s\n" % e)
        raise ApiException

    return api_response.items


def check_project_has_data_sharing_enabled(project_id: str) -> bool:
    """
    Check a project has data-sharing enabled before creating a dataset with that project
    :param project_id: 
    :return: 
    """

    configuration = get_icav2_configuration()

    with ApiClient(configuration) as api_client:
        # Create an instance of the API class
        api_instance = ProjectApi(api_client)

    # example passing only required values which don't have defaults set
    try:
        # Retrieve a project.
        api_response: Project = api_instance.get_project(project_id)
    except libica.openapi.v2.ApiException as e:
        logger.error("Exception when calling ProjectApi->get_project: %s\n" % e)

    return api_response.data_sharing_enabled
