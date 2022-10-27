#!/usr/bin/env python3

"""
This is entirely the wrong spot for this, but the code was already all here!

Takes an input json, a name (or user-reference) and then a set of engine parameters

activation_id: can be left blank and will instead search for best match
storage_id: can be left blank, if set overrides default or any value in storage_size
storage_size: can be left blank and default used, or specify storage id instead otherwise one of small, medium or large
cwltool_overrides: can be left blank or be stored in the input section under "cwltool:overrides"

Converts icav2:// reference schemas to local paths and adds fil.id / fol.id to data ids to mount

Then launches the workflow in the specific icav2 project context
"""

from libica.openapi.v2.model.create_cwl_analysis import CreateCwlAnalysis

from utils.icav2_helpers import get_project_id_from_project_name, \
    get_icav2_configuration, is_project_id_format, \
    get_analysis_storage_id_from_analysis_storage_size, \
    get_pipeline_id_from_pipeline_code, get_data_obj_from_project_id_and_path, \
    create_data_obj_from_project_id_and_path, \
    launch_workflow, recursively_build_open_api_body_from_libica_item

from classes.command import Command
from classes.icav2_launch_json import ICAv2LaunchJson
from utils.logging import get_logger
from pathlib import Path
from argparse import ArgumentError
from utils.globals import ICAv2AnalysisStorageSize
from utils.errors import CheckArgumentError
from typing import Optional, Dict
import json


logger = get_logger()


class LaunchV2Workflow(Command):
    """Usage:
    cwl-ica [options] icav2-launch-pipeline-analysis help
    cwl-ica [options] icav2-launch-pipeline-analysis (--launch-json=<input-json-path>)
                                                     (--pipeline-code=<pipeline_code> | --pipeline-id=<pipeline_id>)
                                                     (--project-name=<project_name> | --project-id=<project_id>)
                                                     [--output-parent-folder-path=<output_parent_folder_path> | --output-parent-folder-id=<output_parent_folder_id>]
                                                     [--analysis-storage-size=<analysis_storage_size> | --analysis-storage-id=<analysis_storage_id>]
                                                     [--activation-id=<activation_id>]
                                                     [--create-cwl-analysis-json-output-path=<output_path>]

Description:
    Launch an analysis on icav2 specifying a project context, and pipeline code.

    Your input json should contain the following keys:
      * name | user_reference | userReference  (the name of the pipeline analysis run)
      * input | inputs (the CWL input json dict)
      * engine_parameters | engineParameters:
        * Which comprises the following keys:
          * output_parent_folder_id | outputParentFolderId (Optional, can also be specified on cli)
          * output_parent_folder_path | outputParentFolderPath (Optional, can also be specified on cli, will be created if it doesn't exist)
          * tags (Optional, a dictionary of lists with the following keys)
            * technical_tags | technicalTags  (Optional array of technical tags to attach to this pipeline analysis)
            * user_tags | userTags (Optional array of user tags to attach to this pipeline analysis)
            * reference_tags | referenceTags (Optional array of reference tags to attach to this pipeline analysis)
          * analysis_storage_id | analysisStorageId (Optional, can also be specified on cli or inferred by cwl-ica)
          * analysis_storage_size | analysisStorageSize (Optional, can also be specified on cli or inferred by cwl-ica)
          * activation_id | activationId (Optional, can also be specified on cli or inferred by cwl-ica)
          * cwltool_overrides | cwltoolOverrides (Optional, can also be specified in input as "cwltool:overrides")
          * stream_all_files | streamAllFiles (Optional, convert all files in the inputs to presigned url)  :construction:
          * stream_all_directories | streamAllDirectories (Optional, convert all directories in the inputs to presigned urls) :construction:

    When specifying files or directories in your input.json, you can set the location attribute to the following URI syntax:
      * icav2://project_id/data_path or
      * icav2://project_name/data_path
    These will then be mounted into your analysis at runtime.

Options:
    --launch-json=<launch_json>                                Required, input json similar to v1
    --pipeline-id=<pipeline_id>                              Optional, id of the pipeline you wish to launch
    --pipeline-code=<pipeline_code>                          Optional, name of the pipeline you wish to launch
                                                             Must specify one (and only one of) --pipeline-id and --pipeline-code
    --project-id=<project_id>                                Optional, id of project context you wish to launch the pipeline analysis.
    --project-name=<project_name>                            Optional, name of the project context you wish to launch the pipeline analysis.
                                                             Must specify one (and only one of) --project-name and --project-id
    --output-parent-folder-id=<output_parent_folder_id>      Optional, the id of the parent folder to write outputs to
    --output-parent-folder-path=<output_parent_folder_path>  Optional, the path to the parent folder to write outputs to (will be created if it doesn't exist)
                                                             Cannot specify both --output-parent-folder-id AND --output-parent-folder-path
    --analysis-storage-id=<analysis_storage_id>              Optional, analysis storage id, overrides default analysis storage size
    --analysis-storage-size=<analysis_storage_size>          Optional, analysis storage size, one of Small, Medium, Large
                                                             Cannot specify both --analysis-storage-id AND --analysis-storage-size
    --activation-id=<activation_id>                          Optional, the activation id used by the pipeline analysis
    --create-cwl-analysis-json-output-path=<output_path>     Optional, Path to output a json file that contains the body for a create cwl analysis (https://ica.illumina.com/ica/api/swagger/index.html#/Project%20Analysis/createCwlAnalysis)


Environment:
    ICAV2_ACCESS_TOKEN

Example:
    cwl-ica icav2-launch-pipeline-analysis --launch-json /path/to/input.json --pipeline-code bclconvert_with_qc_pipeline__4_0_3 --project-name playground_v2
    """
    
    def __init__(self, command_argv):

        # Collect args from doc strings
        super(LaunchV2Workflow, self).__init__(command_argv)

        # Initialise parameters
        self.launch_json_path: Optional[Path] = None
        self.input_launch_json: Optional[ICAv2LaunchJson] = None
        self.pipeline_id: Optional[str] = None
        self.pipeline_code: Optional[str] = None
        self.project_id: Optional[str] = None
        self.project_name: Optional[str] = None
        self.output_parent_folder_id: Optional[str] = None
        self.output_parent_folder_path: Optional[Path] = None
        self.analysis_storage_id: Optional[str] = None
        self.analysis_storage_size: Optional[str] = None
        self.activation_id: Optional[str] = None
        self.create_cwl_analysis_json_output_path: Optional[Path] = None

        # Check if help has been called
        if self.args["help"]:
            self._help()

        # Confirm 'required' arguments are present and valid
        try:
            logger.debug("Checking args")
            self.check_args()
        except ArgumentError:
            self._help(fail=True)

    def check_args(self):
        # Check defined and assign properties
        # Get input json
        logger.info("Checking input args")
        self.launch_json_path = Path(self.args.get("--launch-json", None))
        if self.launch_json_path is None:
            logger.error("--launch-json not defined")
            raise CheckArgumentError
        if not self.launch_json_path.is_file():
            logger.error(f"--launch-json parameter {self.launch_json_path} not found")
            raise FileNotFoundError

        # Get pipeline id
        self.pipeline_id = self.args.get("--pipeline-id", None)
        self.pipeline_code = self.args.get("--pipeline-code", None)
        if self.pipeline_id is not None:
            # Just checks its UUID4 format
            if not is_project_id_format(self.pipeline_id):
                logger.error(f"Got --pipeline-id parameter as {self.pipeline_id} but is not in pipeline-id format")
                raise CheckArgumentError
        if self.pipeline_id is None and self.pipeline_code is None:
            logger.error("Must set one of --pipeline-id or --pipeline-code")
            raise CheckArgumentError
        if self.pipeline_id is None and self.pipeline_code is not None:
            self.pipeline_id = get_pipeline_id_from_pipeline_code(self.pipeline_code, get_icav2_configuration())

        # Get project id
        self.project_id = self.args.get("--project-id", None)
        self.project_name = self.args.get("--project-name", None)
        if self.project_id is not None:
            if not is_project_id_format(self.project_id):
                logger.error(f"Got --project-id parameter as {self.project_id} but is not in project-id format")
                raise CheckArgumentError
        if self.project_id is None and self.project_name is None:
            logger.error("Must set one of --project-id or --project-name")
            raise CheckArgumentError
        if self.project_id is None and self.project_name is not None:
            self.project_id = get_project_id_from_project_name(self.project_name, get_icav2_configuration())

        # Get output parent folder path / id
        # Create output path if it doesn't exist
        self.output_parent_folder_id = self.args.get("--output-parent-folder-id", None)
        self.output_parent_folder_path = self.args.get("--output-parent-folder-path", None)
        if self.output_parent_folder_id is not None:
            # Just checks its UUID4 format
            if not is_project_id_format(self.output_parent_folder_id):
                logger.error(f"Got --output-parent-folder-id parameter as {self.output_parent_folder_id} but is not in pipeline-id format")
                raise CheckArgumentError
        if self.output_parent_folder_id is None and self.output_parent_folder_path is not None:
            self.output_parent_folder_path = Path(self.output_parent_folder_path)
            # Ensure output parent folder path is absolute
            # FIXME - duplicate script
            if not self.output_parent_folder_path.is_absolute():
                logger.error("Please ensure --output-folder-path parameter is absolute")
            try:
                self.output_parent_folder_id = get_data_obj_from_project_id_and_path(
                    self.project_id,
                    str(self.output_parent_folder_path) + "/",
                    get_icav2_configuration()
                ).data.id
            except FileNotFoundError:

                self.output_parent_folder_id = create_data_obj_from_project_id_and_path(
                    self.project_id,
                    str(self.output_parent_folder_path) + "/",
                    get_icav2_configuration()
                )

        # Get analysis storage size
        self.analysis_storage_id = self.args.get("--analysis-storage-id", None)
        self.analysis_storage_size = self.args.get("--analysis-storage-size", None)
        if self.analysis_storage_id is not None:
            # Just checks its UUID4 format
            if not is_project_id_format(self.analysis_storage_id):
                logger.error(f"Got --analysis-storage-id parameter as {self.analysis_storage_id} "
                             f"but is not in pipeline-id format")
                raise CheckArgumentError
        if self.analysis_storage_id is None and self.analysis_storage_size is None:
            pass
        elif self.analysis_storage_id is None and self.analysis_storage_size is not None:
            self.analysis_storage_id = get_analysis_storage_id_from_analysis_storage_size(
                ICAv2AnalysisStorageSize(self.analysis_storage_size), get_icav2_configuration()
            )

        # Check activation id
        self.activation_id = self.args.get("--activation-id", None)

        # Check if create_cwl_analysis_json_output_path is setl
        self.create_cwl_analysis_json_output_path = Path(self.args.get("--create-cwl-analysis-json-output-path", None))
        # If it is specified, ensure parent exists and ensure file itself does not exist
        if self.create_cwl_analysis_json_output_path is not None:
            if not self.create_cwl_analysis_json_output_path.parent.is_dir():
                logger.error(f"Please ensure the parent directory to {self.create_cwl_analysis_json_output_path} exists")
                raise CheckArgumentError
            if self.create_cwl_analysis_json_output_path.is_dir():
                self.create_cwl_analysis_json_output_path = self.create_cwl_analysis_json_output_path / "createcwlanalysis.json"
            if self.create_cwl_analysis_json_output_path.is_file():
                logger.error(f"Output path to {self.create_cwl_analysis_json_output_path} already exists, please delete")
                raise CheckArgumentError

        # CLI is good, now import json
        self.import_json_dict()

    def import_json_dict(self):
        # Import json object
        with open(self.launch_json_path, "r") as json_h:
            self.input_launch_json = ICAv2LaunchJson.from_dict(json.load(json_h))
            if self.output_parent_folder_id is not None:
                self.input_launch_json.update_engine_parameter(
                    "output_parent_folder_id", self.output_parent_folder_id
                )
            if self.analysis_storage_id is not None:
                self.input_launch_json.update_engine_parameter(
                    "analysis_storage_id", self.output_parent_folder_id
                )
            if self.activation_id is not None:
                self.input_launch_json.update_engine_parameter(
                    "activation_id", self.output_parent_folder_id
                )

    def launch_workflow(self):
        # Update engine parameters
        self.input_launch_json.collect_overrides_from_engine_parameters()

        # Deference input json
        logger.info("Dereferencing input json and collecting mount paths")
        self.input_launch_json.deference_input_json()

        # Collect empty engine parameters
        logger.info("Populating empty engine parameters (if any)")
        self.input_launch_json.populate_empty_engine_parameters(
            self.project_id,
            self.pipeline_id
        )

        # Collect analysis
        logger.info("Creating CWL Analysis object")
        cwl_analysis: CreateCwlAnalysis = self.input_launch_json(
            self.pipeline_id
        )

        if self.create_cwl_analysis_json_output_path is not None:
            logger.info(f"Dumping payload to {self.create_cwl_analysis_json_output_path}")
            with open(self.create_cwl_analysis_json_output_path, "w") as create_analysis_h:
                create_analysis_h.write(json.dumps(recursively_build_open_api_body_from_libica_item(cwl_analysis), indent=2))
                create_analysis_h.write("\n")

        # Launch workflow
        logger.info("Launching analysis")
        analysis_id, user_reference = launch_workflow(
            self.project_id,
            cwl_analysis,
            configuration=get_icav2_configuration()
        )

        logger.info(f"Successfully launched analysis pipeline '{self.pipeline_id}' with analysis id '{analysis_id}' and user reference '{user_reference}'")

    def __call__(self):
        self.launch_workflow()
