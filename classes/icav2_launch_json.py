#!/usr/bin/env python3

from libica.openapi.v2 import Configuration
from libica.openapi.v2.model.analysis_input_data_mount import AnalysisInputDataMount
from libica.openapi.v2.model.create_cwl_analysis import CreateCwlAnalysis
from libica.openapi.v2.model.analysis_tag import AnalysisTag
from libica.openapi.v2.model.cwl_analysis_input import CwlAnalysisInput

import json

from utils.globals import ICAV2_DEFAULT_ANALYSIS_STORAGE_SIZE
from utils.icav2_helpers import convert_icav2_uris_to_data_ids, get_icav2_configuration, \
    get_analysis_storage_id_from_analysis_storage_size, get_activation_id, get_set_analysis_storage_id_from_pipeline, \
    get_data_obj_from_project_id_and_path, create_data_obj_from_project_id_and_path
from utils.logging import get_logger
from pathlib import Path
from utils.miscell import sanitise_dict_keys
from typing import Optional, Dict, List, Any

logger = get_logger()


class ICAv2PipelineAnalysisTags:
    """
    List of tags
    """
    def __init__(self, technical_tags: List, user_tags: List, reference_tags: List):
        """
        List of tags to use in the pipeline
        :param technical_tags:
        :param user_tags:
        :param reference_tags:
        """
        self.technical_tags = technical_tags
        self.user_tags = user_tags
        self.reference_tags = reference_tags

    def __call__(self) -> AnalysisTag:
        return AnalysisTag(
            technical_tags=self.technical_tags,
            user_tags=self.user_tags,
            reference_tags=self.reference_tags
        )

    @classmethod
    def from_dict(cls, tags_dict):
        # Convert camel cases to snake cases
        tags_dict = sanitise_dict_keys(tags_dict)

        return cls(
                    technical_tags=tags_dict.get("technical_tags", []),
                    user_tags=tags_dict.get("user_tags", []),
                    reference_tags=tags_dict.get("reference_tags", [])
        )


class ICAv2EngineParameters:
    """
    The ICAv2 EngineParameters has the following properties
    *
    """
    def __init__(self, output_parent_folder_id: Optional[str], output_parent_folder_path: Optional[str],
                 tags: Dict,
                 analysis_storage_id: Optional[str], analysis_storage_size: Optional[str],
                 activation_id: Optional[str], cwltool_overrides: Dict,
                 # stream_all_files, stream_all_directories
                 ):

        self.output_parent_folder_id: Optional[str] = output_parent_folder_id
        self.output_parent_folder_path: Optional[Path] = output_parent_folder_path
        self.tags: ICAv2PipelineAnalysisTags = ICAv2PipelineAnalysisTags.from_dict(tags)
        self.analysis_storage_id: Optional[str] = analysis_storage_id
        self.analysis_storage_size: Optional[str] = analysis_storage_size
        self.activation_id: Optional[str] = activation_id
        self.cwltool_overrides: Dict = cwltool_overrides
        # self.stream_all_files: Optional[bool] = stream_all_files
        # self.stream_all_directories: Optional[bool] = stream_all_directories

    def update_engine_parameter(self, attribute_name: str, value: Any):
        self.__setattr__(attribute_name, value)

    def populate_empty_engine_parameters(self, project_id: str, pipeline_id: str, input_json: Dict,
                                         mount_list: List[AnalysisInputDataMount], configuration: Configuration):
        if self.analysis_storage_id is None:
            self.analysis_storage_id = get_set_analysis_storage_id_from_pipeline(
                pipeline_id,
                configuration=get_icav2_configuration()
            )
        if self.activation_id is None:
            self.activation_id = get_activation_id(
                project_id, pipeline_id, input_json,
                mount_list, configuration
            )

        if self.output_parent_folder_path is not None and self.output_parent_folder_id is None:
            self.output_parent_folder_path = Path(self.output_parent_folder_path)
            if not self.output_parent_folder_path.is_absolute():
                logger.error("Please ensure engine parameter output_folder_path is an absolute path")
            try:
                self.output_parent_folder_id = get_data_obj_from_project_id_and_path(
                    project_id,
                    str(self.output_parent_folder_path) + "/",
                    get_icav2_configuration()
                ).data.id
            except FileNotFoundError:
                self.output_parent_folder_id = create_data_obj_from_project_id_and_path(
                    project_id,
                    str(self.output_parent_folder_path) + "/",
                    get_icav2_configuration()
                )

    # from_dict - read in input
    @classmethod
    def from_dict(cls, engine_parameter_dict):
        """
        Create a ICAWorkflowVersion object from a dictionary
        :return:
        """

        # Convert camel cases to snake cases
        engine_parameter_dict = sanitise_dict_keys(engine_parameter_dict)

        return cls(
                    output_parent_folder_id=engine_parameter_dict.get("output_parent_folder_id", None),
                    output_parent_folder_path=engine_parameter_dict.get("output_parent_folder_path", None),
                    tags=engine_parameter_dict.get("tags", {}),
                    analysis_storage_id=engine_parameter_dict.get("analysis_storage_id", None),
                    analysis_storage_size=engine_parameter_dict.get("analysis_storage_size", None),
                    activation_id=engine_parameter_dict.get("activation_id", None),
                    cwltool_overrides=engine_parameter_dict.get("cwltool_overrides", {})
                   )


class ICAv2LaunchJson:
    """
    The ICAv2 Launch Json has the following properties
        * user_reference: str
        * input_json: Dict  (cwl_inputs)
        * engine_parameters: ICAv2EngineParameters
    """

    def __init__(self, user_reference: str, input_json: Dict, engine_parameters: Dict):
        """
        Initialise input
        :param user_reference:
        :param input_json:
        :param engine_parameters:
        """
        # Get parameters
        self.user_reference: str = user_reference
        self.input_json: Dict = input_json
        self.engine_parameters: ICAv2EngineParameters = ICAv2EngineParameters.from_dict(engine_parameters)

        # Other parts we set up later
        self.input_json_deferenced: Optional[Dict] = None
        self.data_ids: Optional[List[str]] = None
        self.mount_paths: Optional[List[AnalysisInputDataMount]] = None

    def update_engine_parameter(self, attribute_name, value):
        self.engine_parameters.update_engine_parameter(attribute_name, value)

    def populate_empty_engine_parameters(self, project_id: str, pipeline_id):
        # Update empty engine parameters
        self.engine_parameters.populate_empty_engine_parameters(
            project_id,
            pipeline_id,
            self.input_json_deferenced,
            self.mount_paths,
            get_icav2_configuration()
        )

    def collect_overrides_from_engine_parameters(self):
        # If overrides are in the engine parameters, put them in the input json
        input_json_cwltooloverrides = self.input_json.get("cwltool:overrides", {})
        engine_parameter_cwltooloverrides = self.engine_parameters.cwltool_overrides.copy()
        if engine_parameter_cwltooloverrides is None:
            # Nothing to do here
            return
        # Don't override existing overrides in the input json
        # We do this by first updating the engine parameter cwltooloverrides with the input json overrides
        # Then pulling them back again
        key: str
        value: Any
        for key, value in input_json_cwltooloverrides.items():
            if key in engine_parameter_cwltooloverrides.keys():
                engine_parameter_cwltooloverrides[key].update(value)
            else:
                engine_parameter_cwltooloverrides[key] = value
        # Now we pull them back in again
        for key, value in engine_parameter_cwltooloverrides.items():
            input_json_cwltooloverrides[key] = value
        if len(input_json_cwltooloverrides) == 0:
            # Nothing to set here, just return nothing
            return
        # Otherwise set the value in the cwltool:overrides attribute of the input json
        self.input_json["cwltool:overrides"] = input_json_cwltooloverrides
        # If weve already gone and dereferenced, we set that then too
        if self.input_json_deferenced is not None:
            self.input_json_deferenced["cwltool:overrides"] = input_json_cwltooloverrides

    def deference_input_json(self):
        self.input_json_deferenced, self.mount_paths = convert_icav2_uris_to_data_ids(
            self.input_json,
            configuration=get_icav2_configuration()
        )
        self.data_ids = list(map(lambda x: x.data_id, self.mount_paths))

    # from_dict - read in input
    @classmethod
    def from_dict(cls, launch_json_dict):
        """
        Create a ICAWorkflowVersion object from a dictionary
        :return:
        """
        # Convert camel cases to snake cases
        launch_json_dict = sanitise_dict_keys(launch_json_dict)

        return cls(
            user_reference=launch_json_dict.get(
                "user_reference",
                launch_json_dict.get(
                    "name",
                    None
                )
            ),
            input_json=launch_json_dict.get(
                "input",
                launch_json_dict.get(
                    "inputs",
                    {}
                )
            ),
            engine_parameters=launch_json_dict.get(
                "engine_parameters", {}
            )
        )

    def create_cwl_analysis_obj(self, pipeline_id: str) -> CreateCwlAnalysis:
        return CreateCwlAnalysis(
            user_reference=self.user_reference,
            pipeline_id=pipeline_id,
            tags=self.engine_parameters.tags(),
            activation_code_detail_id=self.engine_parameters.activation_id,
            analysis_input=CwlAnalysisInput(
                object_type="JSON",
                input_json=json.dumps(self.input_json_deferenced),
                mounts=self.mount_paths,
                data_ids=self.data_ids
            ),
            analysis_storage_id=self.engine_parameters.analysis_storage_id,
            output_parent_folder_id=self.engine_parameters.output_parent_folder_id
        )

    def __call__(self, pipeline_id: str) -> CreateCwlAnalysis:
        # Parse object command to send workflow
        return self.create_cwl_analysis_obj(pipeline_id)
