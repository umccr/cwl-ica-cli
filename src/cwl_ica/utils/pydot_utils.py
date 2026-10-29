#!/usr/bin/env python

"""
Functions to assist with building the cwl graph in the markdown report

build_cwl_dot -> Runs the cwltool --print-dot and writes to tmp file

edit_cwl_dot -> reads in the dot file and updates inputs / steps and outputs
             -> Updates links by setting urls in each

build_cwl_workflow_image_from_dot -> takes in a dot file and generates an svg file through the graphviz binary
"""

# External imports
import json
import subprocess
from cwl_utils.parser import WorkflowStep
from pydot import graph_from_dot_file, Dot
from tempfile import NamedTemporaryFile
from pathlib import Path
from ruamel.yaml import YAML

# Local imports
from .cwl_helper_utils import get_fragment_from_cwl_id, split_cwl_id_to_path_and_fragment
from .subprocess_handler import run_subprocess_proc
from .logging import get_logger
from .repo import get_cwl_ica_repo_path
from ..classes.cwl import CWL
from .miscell import get_name_version_tuple_from_cwl_file_path, get_items_dir_from_cwl_file_path, \
    get_blob_url_to_markdown_file_from_cwl_path

# Set logger
logger = get_logger()


def _collect_graph_names(obj, names):
    """Collect every 'name' / 'id' defined anywhere in the packed document."""
    if isinstance(obj, dict):
        for key in ("name", "id"):
            value = obj.get(key)
            if isinstance(value, str):
                names.add(value.lstrip("#"))
        for value in obj.values():
            _collect_graph_names(value, names)
    elif isinstance(obj, list):
        for value in obj:
            _collect_graph_names(value, names)


def _collect_import_targets(obj, targets):
    """Collect every intra-document '#...' $import target in the packed document."""
    if isinstance(obj, dict):
        import_target = obj.get("$import")
        if isinstance(import_target, str) and import_target.startswith("#"):
            targets.add(import_target.lstrip("#"))
        for value in obj.values():
            _collect_import_targets(value, targets)
    elif isinstance(obj, list):
        for value in obj:
            _collect_import_targets(value, targets)


def _build_record_definition(target: str, repo_path: Path, cache: dict):
    """
    Recover a record definition for a dangling $import target from its source
    schema yaml. The target has the packed form '<schema-file-name>/<record-name>'.
    Nested $imports inside the record (to other schema files) are rewritten to the
    same document-local '#<schema-file-name>/<record-name>' form so they resolve
    against the sibling definitions we also inline.
    """
    if target in cache:
        return cache[target]

    schema_file_name = target.split("/")[0]
    matches = list(repo_path.glob(f"schemas/**/{schema_file_name}"))
    if len(matches) == 0:
        logger.warning(f"Could not find source schema '{schema_file_name}' to repair packed workflow")
        return None

    yaml = YAML(typ="safe")
    schema_data = yaml.load(matches[0].read_text())
    if not isinstance(schema_data, dict) or not schema_data.get("type") == "record":
        logger.warning(f"Source schema '{schema_file_name}' is not a record, cannot repair")
        return None

    def rewrite_nested_imports(node):
        if isinstance(node, dict):
            import_target = node.get("$import")
            if (
                isinstance(import_target, str) and
                "#" in import_target and
                not import_target.startswith("#")
            ):
                path_part, _, fragment = import_target.partition("#")
                return {"$import": f"#{Path(path_part).name}/{fragment}"}
            return {key: rewrite_nested_imports(value) for key, value in node.items()}
        if isinstance(node, list):
            return [rewrite_nested_imports(value) for value in node]
        return node

    schema_data = rewrite_nested_imports(schema_data)
    # cwltool emits the document-local id for inlined records
    schema_data["name"] = "#" + target

    cache[target] = schema_data
    return schema_data


def repair_packed_schema_imports(packed_file_path: Path) -> bool:
    """
    Work around https://github.com/common-workflow-language/cwltool/issues/2167.

    cwltool --pack can leave a SchemaDefRequirement record as a dangling intra-document
    '$import' (e.g. '#dragen-qc-coverage__1.0.0.yaml/dragen-qc-coverage') without ever
    emitting that record's definition into the packed document. The pack then cannot be
    re-parsed by cwltool (--print-dot / --validate both fail with
    'Reference ... not found in file').

    This repairs the packed json in place: for each SchemaDefRequirement.types list, any
    dangling '$import' entry is replaced with an inline record definition recovered from
    the source schema, matching how cwltool inlines the records it handles correctly.
    Every other '$import' that references the same record then resolves against that
    inlined definition.

    Returns True if the file was modified.
    """
    packed_obj = json.loads(packed_file_path.read_text())

    defined_names = set()
    _collect_graph_names(packed_obj, defined_names)
    import_targets = set()
    _collect_import_targets(packed_obj, import_targets)

    dangling_targets = {
        target
        for target in import_targets
        if target not in defined_names
    }

    if len(dangling_targets) == 0:
        return False

    logger.warning(
        "Packed workflow contains dangling schema imports "
        "(cwltool/cwltool#2167), repairing before building graph: "
        f"{', '.join(sorted(dangling_targets))}"
    )

    repo_path = get_cwl_ica_repo_path()
    record_cache = {}
    inlined_count = 0

    def repair_schema_def_requirements(node):
        nonlocal inlined_count
        if isinstance(node, dict):
            if (
                node.get("class") == "SchemaDefRequirement" and
                isinstance(node.get("types"), list)
            ):
                new_types = []
                for type_entry in node["types"]:
                    if (
                        isinstance(type_entry, dict) and
                        isinstance(type_entry.get("$import"), str) and
                        type_entry["$import"].lstrip("#") in dangling_targets
                    ):
                        record = _build_record_definition(
                            type_entry["$import"].lstrip("#"), repo_path, record_cache
                        )
                        if record is not None:
                            new_types.append(record)
                            inlined_count += 1
                            continue
                    new_types.append(type_entry)
                node["types"] = new_types
            for value in node.values():
                repair_schema_def_requirements(value)
        elif isinstance(node, list):
            for value in node:
                repair_schema_def_requirements(value)

    repair_schema_def_requirements(packed_obj)

    if inlined_count == 0:
        logger.warning("Could not repair any dangling schema imports in packed workflow")
        return False

    packed_file_path.write_text(json.dumps(packed_obj, indent=2, ensure_ascii=False) + "\n")
    logger.info(f"Repaired {inlined_count} dangling schema import(s) in packed workflow")
    return True


def build_cwl_dot(cwl_item: CWL, dot_out_path: Path):
    """
    Run cwltool --print-dot and write to file
    :return:
    """

    # First pack the cwl file (adds consistency in the dot object)
    cwl_packed_temp_file = NamedTemporaryFile(delete=False)
    cwl_item.run_cwltool_pack(cwl_packed_temp_file)

    # Work around cwltool/cwltool#2167: packing complex workflows can leave dangling
    # intra-document schema '$import' references that cwltool cannot re-parse. Inline
    # the missing record definitions before handing the packed file to --print-dot.
    try:
        repair_packed_schema_imports(Path(cwl_packed_temp_file.name))
    except Exception as repair_error:
        logger.warning(f"Could not run packed-schema repair step: {repair_error}")

    # Build dot object
    with open(str(dot_out_path), 'w') as write_h:
        build_dot_returncode, _, build_dot_stderr = run_subprocess_proc(
            [
                "cwltool", "--debug", "--no-doc-cache",
                "--print-dot", cwl_packed_temp_file.name
            ],
            stdout=write_h, stderr=subprocess.PIPE
        )

        if not build_dot_returncode == 0:
            logger.error(f"Could not build dot file, got returncode {build_dot_returncode}")
            logger.error(f"Stderr was {build_dot_stderr}")
            raise ChildProcessError


def edit_cwl_dot(cwl_item, cwl_obj, dot_path: Path):
    """
    Edit inputs / outputs:
      set 'tool tip' to be the doc string for each input and output

    Edit steps:
      Set the url of each node to be the markdown file of said tool / workflow
      Set the tool tip of each node to be the documentation of said step
      Colour node light purple if step is a workflow
    :return:
    """
    # Use pydot to open the dot object
    dot_obj: Dot = graph_from_dot_file(dot_path)[0]

    # Set tool tip on inputs and outputs
    for graph in dot_obj.get_subgraph_list():
        for node in graph.get_nodes():
            # Check inputs
            for i_o in cwl_obj.inputs + cwl_obj.outputs:
                if get_fragment_from_cwl_id(i_o.id).name == get_fragment_from_cwl_id(node.get_name().strip('"')).name:
                    # Set tooltip as input doc
                    node.set_tooltip(i_o.doc)
                    break

    # Iterate through graph nodes and cwl steps
    for node in dot_obj.get_nodes():
        for step in cwl_obj.steps:
            if get_fragment_from_cwl_id(step.id).name == get_fragment_from_cwl_id(node.get_name().strip('"')).name:
                # Colour node if workflow or expression?
                # Get step cwl object
                step_path = get_step_path_from_step_obj(step, cwl_item.cwl_file_path)
                # Get items dir from step path
                items_dir = get_items_dir_from_cwl_file_path(step_path)
                # Get step url from step path
                step_name, step_version = get_name_version_tuple_from_cwl_file_path(step_path, items_dir)
                # Get the path to the markdown file
                node.set_URL(get_blob_url_to_markdown_file_from_cwl_path(step_path))
                # Set the tool tip as the step doc
                node.set_tooltip(step.doc)
                # Get CWL step object
                step_cwl_obj = CWL(step_path, step_name, step_version)
                # Get step cwl object
                if step_cwl_obj.cwl_obj.class_ == "CommandLineTool":
                    continue
                elif step_cwl_obj.cwl_obj.class_ == "Workflow":
                    node.set_fillcolor("orchid2")
                elif step_cwl_obj.cwl_obj.class_ == "ExpressionTool":
                    node.set_fillcolor("orange2")

    try:
        dot_obj.write_dot(str(dot_path))
    except AssertionError:
        logger.warning("Generation of dot file failed")


def get_step_path_from_step_obj(cwl_step_object: WorkflowStep, cwl_file_path: Path) -> Path:
    """
    # Get the absolute path to the step
    step_object:
    :return:
    """
    rel_step_path, _ = split_cwl_id_to_path_and_fragment(cwl_step_object.run)
    step_cwl_path = cwl_file_path.parent.absolute().joinpath(rel_step_path).resolve()

    return step_cwl_path


def build_cwl_workflow_image_from_dot(dot_file, output_file_path, ratio_value, image_format="svg"):
    """
    Build the svg file from the edited dot file to the path specified using graphviz
    We calculate the svg size by estimating the inputs / outputs to get the length
    :return:
    """
    dot_return_code, dot_stdout, dot_stderr = run_subprocess_proc(
        [
            "dot",
            f"-Gratio={ratio_value}",
            f"-T{image_format}",
            f"-o{output_file_path}",
            f"{dot_file}"
        ],
        capture_output=True
    )
