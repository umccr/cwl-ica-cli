#!/usr/bin/env python3

"""
Again CWL helpers that have been WET Types all over the shop.
"""
import re
from copy import deepcopy
#from types import UnionType
from typing import List, Dict, Union, Optional, Any, cast, Tuple
from pathlib import Path

from ruamel import yaml

from classes.cwl import CWL

from utils.repo import join_run_path_from_caller_path

from urllib.parse import urlparse, urldefrag

from cwl_utils.parser.cwl_v1_0 import \
    RecordSchema as RecordSchema_v1_0, \
    InputEnumSchema as InputEnumSchema_v1_0, \
    InputArraySchema as InputArraySchema_v1_0, \
    InputRecordSchema as InputRecordSchema_v1_0, \
    OutputEnumSchema as OutputEnumSchema_v1_0, \
    OutputArraySchema as OutputArraySchema_v1_0, \
    OutputRecordSchema as OutputRecordSchema_v1_0, \
    ArraySchema as ArraySchema_v1_0, \
    EnumSchema as EnumSchema_v1_0, \
    InlineJavascriptRequirement as InlineJavascriptRequirement_v1_0

from cwl_utils.parser.cwl_v1_1 import \
    RecordSchema as RecordSchema_v1_1, \
    InputEnumSchema as InputEnumSchema_v1_1, \
    InputArraySchema as InputArraySchema_v1_1, \
    InputRecordSchema as InputRecordSchema_v1_1, \
    OutputEnumSchema as OutputEnumSchema_v1_1, \
    OutputArraySchema as OutputArraySchema_v1_1, \
    OutputRecordSchema as OutputRecordSchema_v1_1, \
    ArraySchema as ArraySchema_v1_1, \
    EnumSchema as EnumSchema_v1_1, \
    InlineJavascriptRequirement as InlineJavascriptRequirement_v1_1

from cwl_utils.parser.cwl_v1_2 import \
    RecordSchema as RecordSchema_v1_2, \
    InputEnumSchema as InputEnumSchema_v1_2, \
    InputArraySchema as InputArraySchema_v1_2, \
    InputRecordSchema as InputRecordSchema_v1_2, \
    OutputEnumSchema as OutputEnumSchema_v1_2, \
    OutputArraySchema as OutputArraySchema_v1_2, \
    OutputRecordSchema as OutputRecordSchema_v1_2, \
    ArraySchema as ArraySchema_v1_2, \
    EnumSchema as EnumSchema_v1_2, \
    InlineJavascriptRequirement as InlineJavascriptRequirement_v1_2

from cwl_utils.parser.latest import \
    WorkflowInputParameter, \
    WorkflowOutputParameter, \
    shortname, \
    RecordSchema

from cwl_utils.parser import \
    Workflow, \
    WorkflowStep, \
    CommandLineTool, \
    load_document_by_uri

RecordSchema = Union[
    RecordSchema_v1_0,
    RecordSchema_v1_1,
    RecordSchema_v1_2
]

InputEnumSchema = Union[
    InputEnumSchema_v1_0,
    InputEnumSchema_v1_1,
    InputEnumSchema_v1_2
]

InputArraySchema = Union[
    InputArraySchema_v1_0,
    InputArraySchema_v1_1,
    InputArraySchema_v1_2
]

InputRecordSchema = Union[
    InputRecordSchema_v1_0,
    InputRecordSchema_v1_1,
    InputRecordSchema_v1_2
]

OutputEnumSchema = Union[
    OutputEnumSchema_v1_0,
    OutputEnumSchema_v1_1,
    OutputEnumSchema_v1_2
]

OutputArraySchema = Union[
    OutputArraySchema_v1_0,
    OutputArraySchema_v1_1,
    OutputArraySchema_v1_2
]

OutputRecordSchema = Union[
    OutputRecordSchema_v1_0,
    OutputRecordSchema_v1_1,
    OutputRecordSchema_v1_2
]

ArraySchema = Union[
    ArraySchema_v1_0,
    ArraySchema_v1_1,
    ArraySchema_v1_2
]

EnumSchema = Union[
    EnumSchema_v1_0,
    EnumSchema_v1_1,
    EnumSchema_v1_2
]

InlineJavascriptRequirement = Union[
    InlineJavascriptRequirement_v1_0,
    InlineJavascriptRequirement_v1_1,
    InlineJavascriptRequirement_v1_2
]

WorkflowParameter = Union[
    WorkflowInputParameter,
    WorkflowOutputParameter
]

from utils.logging import get_logger

logger = get_logger()


def get_include_items(cwl_item: CWL) -> List[Path]:
    cwl_obj = cwl_item.cwl_obj
    include_items = []
    # Check if there are include items
    requirements = cwl_obj.requirements

    # Check there are requirements
    if requirements is None:
        return []

    # Check inline javascript is a requirement
    try:
        inline_javascript_requirement: InlineJavascriptRequirement = next(
            filter(
                lambda requirement: isinstance(requirement, InlineJavascriptRequirement),
                requirements
            )
        )
    except StopIteration:
        # Did not find InlineJavaScript Requirement
        return []

    # Check we have an expression lib, and it is a list
    expression_lib = inline_javascript_requirement.expressionLib
    if expression_lib is None or not isinstance(expression_lib, List):
        logger.debug(f"Expected expression lib to be a list, not {type(expression_lib)}")
        return []

    # Iterate through list, only want includes
    for lib_item in expression_lib:
        # Must be a dict
        if not isinstance(lib_item, Dict):
            continue

        # Iterate through dict
        # Look for keys that equal $include
        # And return value of that key
        for key, value in lib_item.items():
            if key == "$include":
                value_path: Path = Path(value)
                include_items.append(join_run_path_from_caller_path(cwl_item.cwl_file_path, value_path))

    return include_items


def create_template_from_workflow_inputs(workflow_inputs: List[WorkflowInputParameter]):
    """
    List inputs by template
    :param workflow_inputs:
    :return:
    """
    input_type_dict = {}

    for workflow_input in workflow_inputs:
        input_type_dict.update(
            {
                shortname(workflow_input.id): get_workflow_input_type(workflow_input)
            }
        )

    return input_type_dict


def create_template_from_workflow_outputs(workflow_outputs: List[WorkflowOutputParameter]):
    """
    List outputs by template
    :param workflow_outputs:
    :return:
    """
    output_type_dict = {}

    for workflow_output in workflow_outputs:
        output_type_dict.update(
            {
                shortname(workflow_output.id): get_workflow_output_type(workflow_output)
            }
        )

    return output_type_dict


def get_workflow_input_type(workflow_input: WorkflowInputParameter):
    if isinstance(workflow_input.type, str):
        return get_workflow_input_type_from_str_type(workflow_input)
    elif isinstance(workflow_input.type, InputEnumSchema):
        return get_workflow_input_type_from_enum_schema(workflow_input)
    elif isinstance(workflow_input.type, InputArraySchema):
        return get_workflow_input_type_from_array_schema(workflow_input)
    elif isinstance(workflow_input.type, InputRecordSchema):
        return get_workflow_input_type_from_record_schema(workflow_input)
    elif isinstance(workflow_input.type, List):
        return get_workflow_input_type_from_array_type(workflow_input)
    else:
        logger.warning(f"Don't know what to do here with {type(workflow_input.type)}")


def get_workflow_output_type(workflow_output: WorkflowOutputParameter):
    if isinstance(workflow_output.type, str):
        return get_workflow_output_type_from_str_type(workflow_output)
    elif isinstance(workflow_output.type, OutputEnumSchema):
        return get_workflow_output_type_from_enum_schema(workflow_output)
    elif isinstance(workflow_output.type, OutputArraySchema):
        return get_workflow_output_type_from_array_schema(workflow_output)
    elif isinstance(workflow_output.type, OutputRecordSchema):
        return get_workflow_output_type_from_record_schema(workflow_output)
    elif isinstance(workflow_output.type, List):
        return get_workflow_output_type_from_array_type(workflow_output)
    else:
        logger.warning(f"Don't know what to do here with {type(workflow_output.type)}")
        

def get_workflow_parameter_type_from_enum_schema(workflow_parameter: WorkflowParameter):
    """
    Workflow input type is an enum type
    :param workflow_parameter:
    :return:
    """
    workflow_parameter_type: InputEnumSchema = workflow_parameter.type
    return shortname(workflow_parameter_type.symbols[0])


def get_workflow_input_type_from_enum_schema(workflow_input: WorkflowInputParameter):
    """
    Workflow input type is an enum type
    :param workflow_input:
    :return:
    """
    return get_workflow_parameter_type_from_enum_schema(workflow_input)


def get_workflow_output_type_from_enum_schema(workflow_output: WorkflowOutputParameter):
    """
    Workflow output type is an enum type
    :param workflow_output:
    :return:
    """
    return get_workflow_output_type_from_enum_schema(workflow_output)


def get_workflow_type_from_array_schema(workflow_parameter: WorkflowInputParameter):
    """
    Workflow input type is an array schema
    items attribute may be a file uri
    :param workflow_parameter:
    :return:
    """

    workflow_parameter_new = deepcopy(workflow_parameter)

    workflow_parameter_new.type = workflow_parameter.type.items

    return [
        get_workflow_input_type(workflow_parameter_new)
    ]


def get_workflow_input_type_from_array_schema(workflow_input: WorkflowInputParameter):
    """
    Workflow input type is an array schema
    items attribute may be a file uri
    :param workflow_input:
    :return:
    """

    return get_workflow_type_from_array_schema(workflow_input)


def get_workflow_output_type_from_array_schema(workflow_output: WorkflowOutputParameter):
    """
    Workflow output type is an array schema
    items attribute may be a file uri
    :param workflow_output:
    :return:
    """
    return get_workflow_type_from_array_schema(workflow_output)


def get_workflow_input_type_from_record_schema(workflow_input: WorkflowInputParameter):
    raise NotImplementedError


def get_workflow_output_type_from_record_schema(workflow_output: WorkflowOutputParameter):
    raise NotImplementedError


def get_workflow_type_from_array_type(workflow_parameter: WorkflowParameter):
    """
    Workflow input is type list -
    likely that the first input is 'null'
    :param workflow_parameter:
    :return:
    """
    if not workflow_parameter.type[0] == "null":
        logger.error("Unsure what to do with input of type list where first element is not null")
        raise ValueError
    workflow_input_new = deepcopy(workflow_parameter)
    workflow_input_new.type = workflow_parameter.type[1]
    return get_workflow_input_type(workflow_input_new)


def get_workflow_input_type_from_array_type(workflow_input: WorkflowInputParameter):
    """
    Workflow input is type list -
    likely that the first input is 'null'
    :param workflow_input:
    :return:
    """
    return get_workflow_type_from_array_type(workflow_input)


def get_workflow_output_type_from_array_type(workflow_output: WorkflowOutputParameter):
    """
    Workflow input is type list -
    likely that the first input is 'null'
    :param workflow_input:
    :return:
    """
    return get_workflow_type_from_array_type(workflow_output)


def get_workflow_parameter_type_from_str_type(workflow_parameter: WorkflowParameter):
    """
        Workflow input type is a string type
        :param workflow_input:
        :return: A list with the following attributes
          {

          }
        """
    from utils.cwl_schema_helper_utils import CWLSchemaObj
    if workflow_parameter.type.startswith("file://"):
        # This is a schema!
        return CWLSchemaObj.load_schema_from_uri(workflow_parameter.type).get_template()
    if "#" in workflow_parameter.type:
        original_path = Path(urlparse(workflow_parameter.id).path)
        full_uri_path = original_path.parent.joinpath(
            get_path_from_cwl_id(workflow_parameter.type)).resolve().absolute().as_uri()
        return CWLSchemaObj.load_schema_from_uri(full_uri_path).get_template()
    if workflow_parameter.type == "Directory":
        return {
            "class": "Directory",
            "location": "icav2://project_id/path/to/dir/"
        }
    elif workflow_parameter.type == "File":
        return {
            "class": "File",
            "location": "icav2://project_id/path/to/file"
        }
    elif workflow_parameter.type == "boolean":
        return workflow_parameter.default if workflow_parameter.default is not None else False
    elif workflow_parameter.type == "int":
        return workflow_parameter.default if workflow_parameter.default is not None else "string"
    elif workflow_parameter.type == "float":
        return workflow_parameter.default if workflow_parameter.default is not None else "string"
    elif workflow_parameter.type == "string":
        return workflow_parameter.default if workflow_parameter.default is not None else "string"
    else:
        logger.warning(f"Don't know what to do here with {workflow_parameter.type}")


def get_workflow_input_type_from_str_type(workflow_input: WorkflowInputParameter):
    """
    Workflow input type is a string type
    :param workflow_input:
    :return: A list with the following attributes
      {

      }
    """
    return get_workflow_parameter_type_from_str_type(workflow_input)


def get_workflow_output_type_from_str_type(workflow_output: WorkflowOutputParameter):
    """
    Workflow output type is a string type
    :param workflow_output:
    :return: A list with the following attributes
      {

      }
    """
    return get_workflow_parameter_type_from_str_type(workflow_output)


def get_workflow_overrides_steps_dict(workflow_steps: List[WorkflowStep],
                                      calling_relative_workflow_file_path: Path,
                                      calling_workflow_id: str,
                                      original_relative_directory: Path) -> List:

    """
    Get a list of steps that can be overridden
    :param workflow_steps:
    :param calling_relative_workflow_file_path:
    :param calling_workflow_id:
    :param original_relative_directory:
    :return:
    """

    from os.path import relpath

    override_steps = []

    for workflow_step in workflow_steps:
        # Get the run path
        # run_path = original_relative_directory.joinpath(
        #     relpath(
        #         urlparse(workflow_step.run).path,
        #         original_relative_directory
        #     )
        # ).resolve()
        run_path = original_relative_directory.joinpath(urlparse(workflow_step.run).path).absolute().resolve()

        # Get the short name
        step_name = shortname(workflow_step.id)

        # Get the full name to call
        step_id = f"{calling_relative_workflow_file_path}#{calling_workflow_id}/{step_name}"

        # Load step
        run_cwl_obj = load_document_by_uri(run_path)

        # Just create the step ID
        if isinstance(run_cwl_obj, CommandLineTool):
            override_steps.append(
                step_id
            )

        if isinstance(run_cwl_obj, Workflow):
            override_steps.extend(
                get_workflow_overrides_steps_dict(
                    workflow_steps=run_cwl_obj.steps,
                    calling_relative_workflow_file_path=Path(relpath(run_path, original_relative_directory)),
                    calling_workflow_id=shortname(run_cwl_obj.id),
                    original_relative_directory=original_relative_directory
                )
            )

    return override_steps


def get_type_from_cwl_io_object(cwl_item: Union[WorkflowInputParameter, WorkflowOutputParameter]):
    """
    Get the type from the input object
    :param cwl_item:
    :return:
    """
    i_o_type = cwl_item.type
    i_o_optional = False

    # If the instance type is a list, could be because its optional
    if isinstance(i_o_type, list):
        i_o_type_list = []

        for i_o_type_i in i_o_type:
            # This is an optional type
            if i_o_type_i == 'null':
                i_o_optional = True
                continue
            i_o_type_list.append(i_o_type_i)

        if len(i_o_type_list) == 1:
            i_o_type = i_o_type_list[0]
        else:
            i_o_type = i_o_type_list

    # Check if an array
    if isinstance(i_o_type, ArraySchema):
        recursion_level = 1
        max_iters = 10
        count = 0
        while True:
            count += 1
            if count > max_iters:
                logger.warning(f"Got stuck in infinite while loop whilst trying to determine the type for input/output"
                               f"of step with type {type(i_o_type)}")
                break
            if isinstance(i_o_type.items, str):
                i_o_type = str(get_fragment_from_cwl_id(i_o_type.items)) + "[]"*recursion_level
                break
            elif isinstance(i_o_type.items, ArraySchema):
                # Recursive array
                i_o_type = i_o_type.items
                recursion_level += 1
            else:
                logger.warning(f"Could not handle input/output of type {type(i_o_type)} with items of type {type(i_o_type.items)}")
                break

    # Check if item is an enum schema
    if isinstance(i_o_type, EnumSchema):
        symbols_list = list(
            map(
                lambda symbol: str(
                    get_fragment_from_cwl_id(symbol).relative_to(
                        get_fragment_from_cwl_id(cwl_item.id)
                    )
                ),
                i_o_type.symbols
            )
        )
        # Return the list of possible symbols
        i_o_type = f"[ {' | '.join(symbols_list)}  ]"

    return i_o_type, i_o_optional


def get_fragment_from_cwl_id(cwl_id: str) -> Path:
    """
    Returns the bit after '#' and converts to a path object
    :param cwl_id:
    :return:
    """
    return Path(str(urldefrag(cwl_id).fragment))


def get_path_from_cwl_id(cwl_id: str) -> Path:
    """
    Returns the bit before '#' and converts to a path object
    :param cwl_id: 
    :return: 
    """
    return Path(
        urlparse(
            str(urldefrag(cwl_id).url)
        ).path
    )


def split_cwl_id_to_path_and_fragment(cwl_id: str) -> Tuple[Path, Path]:
    """
    Split the CWL ID into path and fragment
    urldefrag('file:///e/Users/awluc/OneDrive/GitHub/UMCCR/cwl-ica/schemas/fastq-list-row/1.0.0/fastq-list-row__1.0.0.yaml#fastq-list-row')
    returns
    'file:///e/Users/awluc/OneDrive/GitHub/UMCCR/cwl-ica/schemas/fastq-list-row/1.0.0/fastq-list-row__1.0.0.yaml', fastq-list-row'
    urlparse('file:///e/Users/awluc/OneDrive/GitHub/UMCCR/cwl-ica/schemas/fastq-list-row/1.0.0/fastq-list-row__1.0.0.yaml').path
    returns /e/Users/awluc/OneDrive/GitHub/UMCCR/cwl-ica/schemas/fastq-list-row/1.0.0/fastq-list-row__1.0.0.yaml

    :param cwl_id:
    :return:
    """
    cwl_path, cwl_fragment = urldefrag(cwl_id)
    cwl_path = Path(urlparse(cwl_path).path)
    cwl_fragment = Path(cwl_fragment)
    return cwl_path, cwl_fragment


def get_authorship_from_workflow(cwl_workflow: Workflow):
    cwl_workflow.extension_fields