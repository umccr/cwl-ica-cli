#!/usr/bin/env python3

"""
Build workflow release assets

Creates a zip file of workflow along with packed
With markdown based documentation added to release notes

Triggered by tag

Steps

1. Collect workflow path of interest from GitHub tag
2. Pack and zip workflow simultaneously and set as output files
3. Create dot image for workflow and any possible subworkflows
3a. Upload images as release assets
4. Create input json template
5. Create overrides template
6. Create description.txt inside zipped workflow
7. Create markdown with the following attributes
    * Workflow Documentation
    * Inputs Documentation
    * Steps Documentation
    * Links to workflows / tools used in catalogue
    * Visual Overview (linking in plots as release assets)
    * Outputs Documentation
    * Inputs Template
    * Overrides Template
"""

# External imports
import json
import os
from os import environ
import re
from argparse import ArgumentError
from json import JSONDecodeError
from tempfile import TemporaryDirectory, NamedTemporaryFile
from urllib.parse import urldefrag
from zipfile import ZipFile
from time import sleep
from ruamel.yaml import CommentedSeq, YAML
from pathlib import Path
from typing import Optional, List, Tuple, Dict
from mdutils import MdUtils

# CWL Utils
from cwl_utils.parser import load_document_by_uri

# Utils
from ...utils.cwl_helper_utils import (
    create_template_from_workflow_inputs, create_template_from_workflow_outputs,
    get_workflow_overrides_steps_dict, get_type_from_cwl_io_object
)
from ...utils.cwl_workflow_helper_utils import (
    zip_workflow, create_packed_workflow_from_zipped_workflow_path,
    create_cwl_inputs_schema_gen
)
from ...utils.dockstore_helpers import (
    append_workflow_to_dockstore_yaml, get_dockstore_yaml_path, workflow_path_name_to_dockstore_name
)
from ...utils.gh_helpers import (
    get_gh_release_output_path, get_github_url, get_releases_url
)
from ...utils.globals import ICAV2_DEFAULT_BASE_URL
from ...utils.icav2_gh_helpers import (
    read_config_yaml, write_config_yaml, get_icav2_config_yaml_path,
    get_project_id_from_project_name, get_project_name_from_project_id,
    get_tenant_access_token, get_pipeline_code_from_pipeline_id
)
from ...utils.logging import get_logger
from ...utils.miscell import (
    get_name_version_tuple_from_cwl_file_path,
    get_items_dir_from_cwl_file_path, cwl_id_to_path
)
from ...utils.pydot_utils import get_step_path_from_step_obj
from ...utils.repo import get_workflows_dir, get_dockstore_dir, get_cwl_ica_repo_path
from ...utils.subprocess_handler import run_subprocess_proc

# Classes
from ...classes.command import Command
from ...classes.cwl_workflow import CWLWorkflow
from ...classes.icav2_bunch_classes import Bunch, BunchVersion, Bundle

# Set logger
logger = get_logger()


class BuildWorkflowReleaseAsset(Command):
    """Usage:
    cwl-ica [options] github-actions-build-workflow-release-asset help
    cwl-ica [options] github-actions-build-workflow-release-asset (--workflow-path=<"path_to_output_file">)
                                                                  [--draft-release]

Description:
    Create a release for a given workflow path, this command is generally triggered by a tag.

Options:
    --workflow-path=<workflow path>          Required, path to CWL workflow to push
    --draft-release                          Optional, is this a draft release?

Example:
    cwl-ica github-actions-build-workflow-release-asset --workflow-path workflows/bcl-convert-with-qc-pipeline/4.0.3/bcl-convert-with-qc-pipeline__4.0.3.cwl

Environment Variables
    GITHUB_SERVER_URL     Name of server (https://github.com)
    GITHUB_REPOSITORY     This repository path (umccr/cwl-ica)
    GITHUB_TOKEN:         Secret GitHub token, used by gh cli to push release assets
    GITHUB_TAG:           The GitHub tag(s) that triggered this workflow
    ICAV2_ACCESS_TOKEN_<TENANT_NAME>    The icav2 access token for each given tenant, used to generate pipelines / bundles in each desired tenant
    """

    DEFAULT_OUTPUT_PATH = "cwl-ica-catalogue.md"
    DEFAULT_TITLE = "UMCCR CWL-ICA Catalogue"

    def __init__(self, command_argv):
        # Collect args from doc strings
        super().__init__(command_argv)

        # Initialise values
        self.cwl_file_path: Optional[Path] = None
        self.cwl_obj: Optional[CWLWorkflow] = None

        self.github_tag = None  # type: Optional[List[str]]
        self.release_name = None  # type: Optional[str]
        self.release_url = None  # type: Optional[str]
        self.is_draft_release = None  # type: Optional[bool]

        # ICAv2 assets
        self.bundle_tenants = None  # type: Optional[List[str]]
        self.bundle_objs = None  # type: Optional[List[Bundle]]

        # Release assets
        self.zipped_workflow_path = None  # type: Optional[Path]
        self.packed_workflow_path = None  # type: Optional[Path]
        self.json_schema_gen_path = None  # type: Optional[Path]
        self.input_template_json_path = None  # type: Optional[Path]
        self.input_template_yaml_path = None  # type: Optional[Path]
        self.overrides_template_json = None  # type: Optional[Path]
        self.overrides_template_yaml = None  # type: Optional[Path]
        self.zipped_cwl_obj = None  # type: Optional[CWLWorkflow]

        # Release artifacts
        self.release_artifacts_tmpdir = TemporaryDirectory()
        self.release_artifacts_path = None  # type: Optional[Path]
        self.artifacts_branch = None  # type: Optional[str]
        self.md_file_obj = None  # type: Optional[MdUtils]
        self.md_path_tmpdir = TemporaryDirectory()
        self.md_path = None  # type: Optional[Path]
        self.workflow_image_paths = None  # type: Optional[List[Tuple[str, Path, str]]]

        # Icav2
        self.pipeline_ids_by_project_by_tenant = None  # type: Optional[Dict]
        self.icav2_bundles_by_tenant = None  # type: Optional[Dict]

        # Check args
        self.check_args()

        # Create the zipped workflow object
        self.create_zipped_workflow_obj()

        # Create release assets
        self.create_compressed_packed_workflow()
        self.create_cwl_inputs_schema_gen()
        self.create_inputs_templates_as_release_assets()
        self.create_overrides_as_release_assets()

    def check_args(self):
        """
        Check if output path arg is set
        :return:
        """

        # Set output_path
        cwl_file_path_arg = self.args.get("--workflow-path", None)

        # Check workflow path actually exists
        if cwl_file_path_arg is None:
            logger.error(f"Could not get --workflow-path arg {cwl_file_path_arg}")
            raise ArgumentError
        self.cwl_file_path = Path(cwl_file_path_arg).absolute()

        if not self.cwl_file_path.is_file():
            logger.error(f"Could not find file {self.cwl_file_path}")
            raise FileNotFoundError

        # Get name, version from cwl file path
        name, version = get_name_version_tuple_from_cwl_file_path(
            self.cwl_file_path,
            items_dir=get_items_dir_from_cwl_file_path(self.cwl_file_path)
        )

        self.cwl_obj = CWLWorkflow(
            cwl_file_path=self.cwl_file_path,
            name=name,
            version=version
        )
        # Validate object
        self.cwl_obj()

        # Check GITHUB_TAG env var exist
        if os.environ.get("GITHUB_TAG", None) is not None:
            self.github_tag = os.environ["GITHUB_TAG"].split(",")
        else:
            logger.error("Could not find the GITHUB_TAG env var")
            raise ArgumentError
        # Check GITHUB TAG is split
        if not len(self.github_tag) == 2:
            logger.error("Expected two tags at this commit")
            raise ArgumentError
        # Check GITHUB Tags are as expected
        # dragen-pon-qc/3.9.3,dragen-pon-qc/3.9.3__221219235859
        full_github_tag_regex_obj = re.fullmatch(r"(\S+/\S+)__(\d+)", self.github_tag[1])
        if full_github_tag_regex_obj is None:
            logger.error(f"GITHUB_TAG env var '{','.join(self.github_tag)}' is not formatted as expected")
            raise ArgumentError
        if not full_github_tag_regex_obj.group(1) == self.github_tag[0]:
            logger.error(f"GITHUB_TAG env var '{','.join(self.github_tag)}' is not as expected")
            raise ArgumentError

        # Release name is cwl_file_path.name + __ + YYMMDDHHMMSS
        self.release_name = self.github_tag[1].replace("/", "__")
        self.release_url = self.get_release_url()
        self.artifacts_branch = f"{self.github_tag[1]}--release-artifacts"

        # Get zipped workflow path
        self.release_artifacts_path = Path(self.release_artifacts_tmpdir.name) / "release-artifacts"
        self.release_artifacts_path.mkdir(exist_ok=True, parents=True)
        self.zipped_workflow_path = self.release_artifacts_path / (self.release_name + ".zip")
        # packed_workflow_path
        self.packed_workflow_path = self.release_artifacts_path / (self.release_name + ".packed.cwl.json.gz")
        # json_schema_gen_path
        self.json_schema_gen_path = self.release_artifacts_path / (self.release_name + ".schema.json")
        # Inputs paths
        self.input_template_json_path = self.release_artifacts_path / (self.release_name + ".inputs.json")
        self.input_template_yaml_path = self.release_artifacts_path / (self.release_name + ".inputs.yaml")
        # Release assets
        self.overrides_template_yaml = self.release_artifacts_path / (self.release_name + ".zipped.overrides.yaml")
        self.overrides_template_json = self.release_artifacts_path / (self.release_name + ".zipped.overrides.json")

        # Get md path
        self.md_path = Path(self.md_path_tmpdir.name) / "ReleaseNotes.md"

    def __call__(self):
        """
        * Upload release assets (zip and packed workflow json) and then create release
        * Checkout the release artifacts branch
        * Generate the dockstore PR(s)
            * One to update the .dockstore.yml file
            * One to generate a tag for this workflow/version in dockstore with a packed cwl json
        * Add artifacts to a PR branch (pictures for the markdown object)
        * Create the commit for the dockstore workflow
        * Create the commit used for the images in the PR
        * Generate the v2 configuration yaml PR - generates pipelines and bundles (separate PR)
        * Now build the markdown file object
        * Then edit the release using the GH API
        :return:
        """
        # Checkout release artifacts branch
        self.checkout_release_artifacts_branch()

        # Create images
        self.workflow_image_paths = self.create_workflow_images()

        # Create release (with files but empty description)
        self.upload_release_assets_and_create_release()

        # Create packed workflow PR for dockstore artifacts
        self.create_dockstore_commit()

        # Commit and Create release artifacts branch
        self.create_and_commit_to_release_artifacts()

        # Generate bundles for icav2
        self.create_and_commit_v2_bundles()

        # Fast-forward tags
        self.fast_forward_tags()

        # Push commit
        self.push_branch_and_tags()

        # Create release artifacts PR
        self.create_release_artifacts_pr()

        # Create file object
        self.create_markdown_file_object()

        # Add description
        self.update_release_description()

    def get_repo_url_from_relative_repo_path(self, relative_path: Path) -> str:
        """
        Get repo url
        :param relative_path:
        :return:
        """
        blob = f"blob/{self.github_tag[1]}"

        return "/".join(map(str, [get_github_url(), blob, relative_path]))

    def get_release_artifact_output_path(self) -> Path:
        """
        Get the output path for the release asset
        """
        return get_gh_release_output_path() / self.release_name

    def checkout_release_artifacts_branch(self):
        """
        Checkout the release artifacts branch
        :return:
        """
        git_checkout_command = [
            "git", "checkout",
            "-b", self.artifacts_branch,
            self.github_tag[0]
        ]

        git_checkout_proc_returncode, git_checkout_proc_stdout, git_checkout_proc_stderr = run_subprocess_proc(
            git_checkout_command,
            capture_output=True
        )

        if not git_checkout_proc_returncode == 0:
            logger.error(f"Could not checkout branch {self.artifacts_branch}")
            logger.error(f"Stdout was {git_checkout_proc_stdout}")
            logger.error(f"Stderr was {git_checkout_proc_stderr}")
            raise ChildProcessError

    def update_release_description(self):
        """
        Add in the description text file with the following contents

        Please see <this url> for a detailed description of this workflow
        :return:
        """
        # Edit GitHub release with md-path, that contains the bundle objects and dockstore links
        gh_edit_release_command = [
            "gh", "release", "edit",
            self.github_tag[1],
            "--notes-file", str(self.md_path)
        ]

        gh_returncode, gh_stdout, gh_stderr = run_subprocess_proc(
            gh_edit_release_command,
            capture_output=True
        )

        # Add the release notes as their own asset
        gh_add_release_mdfile_command = [
            "gh", "release", "upload",
            self.github_tag[1],
            str(self.md_path)
        ]

        gh_returncode, gh_stdout, gh_stderr = run_subprocess_proc(
            gh_add_release_mdfile_command,
            capture_output=True
        )

    def get_release_url(self):
        return get_releases_url() + self.github_tag[1]

    def create_markdown_file_object(self):
        self.initialise_markdown_file()
        self.add_header_section()
        self.add_visual_section()
        self.add_inputs_template_section()
        self.add_outputs_template_section()
        self.add_overrides_template_section()
        self.add_inputs_section()
        self.add_steps_section()
        self.add_outputs_section()

        # Write out md file object
        logger.info("Writing out markdown file")
        self.md_file_obj.create_md_file()

        # Delete the top row of the md file
        with open(self.md_path, 'r+') as fp:
            # read and store all lines into list
            lines = fp.readlines()
            # move file pointer to the beginning of a file
            fp.seek(0)

            # truncate the file
            fp.truncate()

            # start writing lines except the first line
            # lines[3:] from line 4 to last line
            fp.writelines(lines[3:])

    def create_zipped_workflow_obj(self):
        """
        Create a zipped workflow object from the cwl object
        :return:
        """
        zip_workflow(self.cwl_obj, self.zipped_workflow_path)

    def create_compressed_packed_workflow(self):
        """
        Create a compressed packed json from the zipped workflow
        :return:
        """
        create_packed_workflow_from_zipped_workflow_path(
            self.zipped_workflow_path,
            self.packed_workflow_path
        )

    def create_cwl_inputs_schema_gen(self):
        """
        Create a JSON Schema for the inputs of a CWL workflow
        :return:
        """
        create_cwl_inputs_schema_gen(
            self.zipped_workflow_path,
            self.json_schema_gen_path
        )

    def create_inputs_templates_as_release_assets(self):
        # Write out yaml
        with open(self.input_template_yaml_path, 'w') as yaml_h:
            yaml_obj = YAML()
            yaml_obj.dump(
                create_template_from_workflow_inputs(self.cwl_obj.cwl_obj.inputs, output_format="yaml"),
                yaml_h
            )

        # Write out json
        with open(self.input_template_json_path, 'w') as json_h:
            json_h.write(
                json.dumps(
                    create_template_from_workflow_inputs(self.cwl_obj.cwl_obj.inputs),
                    indent=4
                )
            )

    def create_overrides_as_release_assets(self):
        from ...utils.cwl_helper_utils import shortname

        with TemporaryDirectory() as zipped_temp_dir, ZipFile(self.zipped_workflow_path, "r") as zip_h:
            # Extract zipped into tempdir
            zip_h.extractall(zipped_temp_dir)

            # Get workflow.cwl
            workflow_cwl_file_path = Path(zipped_temp_dir) / self.zipped_workflow_path.stem / "workflow.cwl"
            zipped_cwl_workflow_obj = load_document_by_uri(workflow_cwl_file_path)

            zipped_cwl_workflow_overrides = get_workflow_overrides_steps_dict(
                workflow_steps=zipped_cwl_workflow_obj.steps,
                calling_relative_workflow_file_path=Path(Path(workflow_cwl_file_path).name),
                calling_workflow_id=shortname(zipped_cwl_workflow_obj.id),
                original_relative_directory=workflow_cwl_file_path.parent
            )

        # Write out as yaml
        with open(self.overrides_template_yaml, 'w') as yaml_h:
            yaml_obj = YAML()
            yaml_obj.dump(
                zipped_cwl_workflow_overrides,
                yaml_h
            )

        # Write out json
        with open(self.overrides_template_json, 'w') as json_h:
            json_h.write(
                json.dumps(
                    zipped_cwl_workflow_overrides,
                    indent=4
                )
            )

    # MDUtils sections
    def initialise_markdown_file(self):
        """
        Initialise a markdown file -
        :return:
        """

        workflow_title = f"ID {self.release_name}"

        self.md_file_obj: MdUtils = MdUtils(
            file_name=str(self.md_path),
            title=workflow_title
        )

    def add_header_section(self):
        """
        Get the header section of the catalogue - literally just a manually generated table of contents
        :return:
        """

        self.md_file_obj.new_header(level=2, title="Overview", add_table_of_contents='n')
        self.md_file_obj.new_line(f"> MD5Sum: {self.cwl_obj.md5sum}")  # FIXME - should be packed md5sum

        self.md_file_obj.new_header(level=3, title="Documentation", add_table_of_contents='n')
        self.md_file_obj.new_paragraph(
            self.cwl_obj.cwl_obj.doc
        )

        self.md_file_obj.new_header(level=2, title="Dockstore", add_table_of_contents='n')
        self.md_file_obj.new_paragraph(
            "[Dockstore Version Link](https://dockstore.org/workflows/github.com/{org_repo}/{workflow_name}:{workflow_version})".format(
                org_repo=os.environ.get("GITHUB_REPOSITORY"),
                workflow_name=workflow_path_name_to_dockstore_name(self.cwl_file_path.name),
                workflow_version=self.github_tag[1]
            )
        )

        if self.pipeline_ids_by_project_by_tenant is None:
            pass
        else:
            self.md_file_obj.new_header(level=2, title="ICAv2", add_table_of_contents='n')

            pipeline_project_dict: Dict
            for tenant_name, tenant_bundle_list in self.icav2_bundles_by_tenant.items():
                self.md_file_obj.new_header(level=3, title=f"Tenant: {tenant_name}", add_table_of_contents='n')

                self.md_file_obj.new_paragraph("**Bundles Generated**")

                for bundle_id in tenant_bundle_list:
                    bundle_obj = next(
                        filter(
                            lambda bundle_obj_iter: bundle_obj_iter.bundle_id == bundle_id,
                            self.bundle_objs
                        )
                    )

                    # Header Is the Bundle Name
                    self.md_file_obj.new_header(
                        level=4,
                        title=f"Bundle Name: {bundle_obj.bundle_name} / Bundle Version {bundle_obj.bundle_version}",
                        add_table_of_contents='n'
                    )

                    self.md_file_obj.new_paragraph(f"> Description\n {bundle_obj.bundle_description}\n")
                    self.md_file_obj.new_paragraph(f"> Version Description\n {bundle_obj.bundle_version_description}\n")

                    self.md_file_obj.new_list([
                        f"**Bundle ID**:           {bundle_id}",
                        f"[**Bundle Link**]({bundle_obj.bundle_url})",
                        f"**Pipeline Project ID**: {bundle_obj.pipeline_project_id}",
                        f"**Pipeline Project Name**: {get_project_name_from_project_id(tenant_name, bundle_obj.pipeline_project_id)}",
                        f"**Pipeline ID**: {bundle_obj.bundle_pipeline_id}",
                        f"**Pipeline Code**: {get_pipeline_code_from_pipeline_id(bundle_obj.bundle_pipeline_id, get_tenant_access_token(tenant_name))}",
                    ])

                    if not len(bundle_obj.projects) == 0:
                        self.md_file_obj.new_line("\n**Projects**\n")

                        self.md_file_obj.new_list(
                            bundle_obj.projects
                        )

                    if not len(bundle_obj.bunch_datasets) == 0:
                        self.md_file_obj.new_line("\n**Datasets**\n")
                        self.md_file_obj.new_list(
                            list(
                                map(
                                    lambda dataset_obj: dataset_obj.dataset_name,
                                    bundle_obj.bunch_datasets
                                )
                            )
                        )

    def add_visual_section(self):
        """
        Add visual section
        :return:
        """
        self.md_file_obj.new_header(
            level=2, title="Visual Overview", add_table_of_contents="n"
        )

        self.md_file_obj.new_line("<details>")
        self.md_file_obj.new_line("<summary>Click to expand!</summary>\n")

        workflow_name: str
        workflow_image_path: Path
        workflow_image_url: str
        for index, (workflow_name, workflow_image_path, workflow_image_url) in enumerate(self.workflow_image_paths):
            # Dont go through subworkflow logic if this is the first image (main image)
            if index == 1:
                self.md_file_obj.new_header(
                    level=3, title="Subworkflows", add_table_of_contents="n"
                )
            # Dont add subworkflow header if this is the first (main) image
            if not index == 0:
                self.md_file_obj.new_header(
                    level=4, title=workflow_name, add_table_of_contents="n"
                )
            # Add the image
            self.md_file_obj.new_line(
                self.md_file_obj.new_inline_image(
                    path=workflow_image_url,
                    text=workflow_name
                )
            )

        self.md_file_obj.new_line("</details>\n")

    def add_inputs_template_section(self):
        self.md_file_obj.new_header(
            level=2, title="Inputs Template", add_table_of_contents="n"
        )

        # Yaml header
        self.md_file_obj.new_header(
            level=3, title="Yaml", add_table_of_contents="n"
        )

        self.md_file_obj.new_line("<details>")
        self.md_file_obj.new_line("<summary>Click to expand!</summary>\n")

        temp_file = NamedTemporaryFile(delete=False).name
        with open(temp_file, 'w') as temp_h:
            yaml_obj = YAML()
            yaml_obj.dump(
                create_template_from_workflow_inputs(self.cwl_obj.cwl_obj.inputs, output_format="yaml"),
                temp_h
            )
        with open(temp_file, 'r') as temp_h:
            self.md_file_obj.insert_code(
                temp_h.read()
            )
        self.md_file_obj.new_line("</details>\n")

        # JSon Template
        self.md_file_obj.new_header(
            level=3, title="Json", add_table_of_contents="n"
        )

        self.md_file_obj.new_line("<details>")
        self.md_file_obj.new_line("<summary>Click to expand!</summary>\n")

        self.md_file_obj.insert_code(
            json.dumps(
                create_template_from_workflow_inputs(self.cwl_obj.cwl_obj.inputs),
                indent=4
            )
        )

        self.md_file_obj.new_line("</details>\n")

    def add_outputs_template_section(self):
        self.md_file_obj.new_header(
            level=2, title="Outputs Template", add_table_of_contents="n"
        )

        self.md_file_obj.new_line("<details>")
        self.md_file_obj.new_line("<summary>Click to expand!</summary>\n")

        self.md_file_obj.insert_code(
            json.dumps(
                create_template_from_workflow_outputs(self.cwl_obj.cwl_obj.outputs),
                indent=4
            )
        )

        self.md_file_obj.new_line("</details>\n")

    def add_overrides_template_section(self):
        from ...utils.cwl_helper_utils import shortname

        self.md_file_obj.new_header(
            level=2, title="Overrides Template", add_table_of_contents="n"
        )

        self.md_file_obj.new_header(
            level=3, title="Zipped workflow", add_table_of_contents="n"
        )

        self.md_file_obj.new_line("<details>")
        self.md_file_obj.new_line("<summary>Click to expand!</summary>\n")

        # FIXME - place as function
        with TemporaryDirectory() as zipped_temp_dir, ZipFile(self.zipped_workflow_path, "r") as zip_h:
            # Extract zipped into tempdir
            zip_h.extractall(zipped_temp_dir)

            # Get workflow.cwl
            workflow_cwl_file_path = Path(zipped_temp_dir) / self.zipped_workflow_path.stem / "workflow.cwl"
            zipped_cwl_workflow_obj = load_document_by_uri(workflow_cwl_file_path)

            zipped_cwl_workflow_overrides = get_workflow_overrides_steps_dict(
                workflow_steps=zipped_cwl_workflow_obj.steps,
                calling_relative_workflow_file_path=Path(Path(workflow_cwl_file_path).name),
                calling_workflow_id=shortname(zipped_cwl_workflow_obj.id),
                original_relative_directory=workflow_cwl_file_path.parent
            )

            self.md_file_obj.insert_code(
                json.dumps(
                    zipped_cwl_workflow_overrides,
                    indent=4
                )
            )

        self.md_file_obj.new_line("</details>\n")

        self.md_file_obj.new_header(
            level=3, title="Packed workflow", add_table_of_contents="n"
        )

        self.md_file_obj.new_line("<details>")
        self.md_file_obj.new_line("<summary>Click to expand!</summary>\n")

        packed_cwl_workflow_overrides = []
        for step in zipped_cwl_workflow_overrides:
            base_path = Path(str(urldefrag(step).url)).name
            step_fragment_path = Path(str(urldefrag(step).fragment))
            if base_path == Path(workflow_cwl_file_path).name:
                # Rename workflow.cwl as 'main'
                base_path = "main"
                step_fragment_path = step_fragment_path.name
            packed_cwl_workflow_overrides.append(
                f"#{base_path}/{step_fragment_path}"
            )

        self.md_file_obj.insert_code(
            json.dumps(
                packed_cwl_workflow_overrides,
                indent=4
            )
        )
        self.md_file_obj.new_line("</details>\n")

    def add_inputs_section(self):
        self.md_file_obj.new_header(
            level=2, title="Inputs", add_table_of_contents="n"
        )

        self.md_file_obj.new_line("<details>")
        self.md_file_obj.new_line("<summary>Click to expand!</summary>\n")

        # Iterate through inputs
        for input_obj in self.cwl_obj.cwl_obj.inputs:
            input_type, is_optional = get_type_from_cwl_io_object(input_obj)

            self.md_file_obj.new_header(level=3, title=input_obj.label, add_table_of_contents='n')

            # Add new paragraph
            self.md_file_obj.new_paragraph("\n")

            self.md_file_obj.new_line(f"> ID: {cwl_id_to_path(input_obj.id).name}\n")
            self.md_file_obj.new_line(f"**Optional:** `{is_optional}`")
            self.md_file_obj.new_line(f"**Type:** `{input_type}`")
            self.md_file_obj.new_line(f"**Docs:**")
            self.md_file_obj.new_line(f"{input_obj.doc}\n", wrap_width=0)

        self.md_file_obj.new_line("\n")

        self.md_file_obj.new_line("</details>\n")

    def add_steps_section(self):
        """
        Get each step and the name / label of the step that runs
        :return:
        """

        self.md_file_obj.new_header(level=2, title=f"Steps", add_table_of_contents='n')

        self.md_file_obj.new_line("<details>")
        self.md_file_obj.new_line("<summary>Click to expand!</summary>\n")

        for step_obj in self.cwl_obj.cwl_obj.steps:
            # Get the step path
            step_path = get_step_path_from_step_obj(step_obj, self.cwl_file_path)
            items_dir = get_items_dir_from_cwl_file_path(step_path)

            step_type = re.sub(r"s$", "", str(items_dir.name))

            # Add in step header
            self.md_file_obj.new_header(level=3, title=step_obj.label, add_table_of_contents='n')

            # Add in id and doc and the step type
            self.md_file_obj.new_paragraph()
            self.md_file_obj.new_line(f"> ID: {cwl_id_to_path(step_obj.id)}\n")
            self.md_file_obj.new_line(f"**Step Type:** {step_type}")
            self.md_file_obj.new_line(f"**Docs:**\n")
            self.md_file_obj.new_line(f"{step_obj.doc}", wrap_width=0)

        self.md_file_obj.new_line("</details>\n")

    def add_outputs_section(self):
        """
        Add the outputs section
        :return:
        """

        # Create output section
        self.md_file_obj.new_header(level=2, title="Outputs", add_table_of_contents='n')

        self.md_file_obj.new_line("<details>")
        self.md_file_obj.new_line("<summary>Click to expand!</summary>\n")

        # Iterate through outputs
        for output_obj in self.cwl_obj.cwl_obj.outputs:
            output_type, is_optional = get_type_from_cwl_io_object(output_obj)
            self.md_file_obj.new_header(level=3, title=output_obj.label, add_table_of_contents='n')
            self.md_file_obj.new_paragraph("\n")
            self.md_file_obj.new_line(f"> ID: {cwl_id_to_path(output_obj.id)}")
            self.md_file_obj.new_line("\n")
            self.md_file_obj.new_line(f"**Optional:** `{is_optional}`")
            self.md_file_obj.new_line(f"**Output Type:** `{output_type}`")
            self.md_file_obj.new_line(f"**Docs:**")
            self.md_file_obj.new_line(f"{output_obj.doc}", wrap_width=0)
            self.md_file_obj.new_line("\n")

        self.md_file_obj.new_line("\n")

        self.md_file_obj.new_line("</details>\n")

    def create_workflow_images(self) -> List[Tuple[str, Path, str]]:
        """
        Create the workflow images

        Workflows are added in under
        .github/releases/<release_name>/images/

        Return an array of workflow / subworkflow label names and their associated github url paths
        :return:
        """

        # Iterate through subworkflows to generate workflow object
        main_workflow_image_path = self.get_release_artifact_output_path() / "workflow.svg"
        self.get_release_artifact_output_path().mkdir(parents=True, exist_ok=True)
        main_workflow_image_url = self.get_repo_url_from_relative_repo_path(main_workflow_image_path)
        # First image is always the main image
        workflow_paths = [
            (self.cwl_obj.name, main_workflow_image_path, main_workflow_image_url)
        ]
        self.cwl_obj.generate_workflow_image(
            main_workflow_image_path
        )

        for workflow in self.cwl_obj.get_subworkflows():
            workflow_image_path = self.get_release_artifact_output_path() / (workflow.stem + ".svg")
            workflow_image_url = self.get_repo_url_from_relative_repo_path(workflow_image_path)
            name, version = workflow.stem.split("__", 1)
            workflow_obj = CWLWorkflow(
                cwl_file_path=get_workflows_dir() / name / version / (name + "__" + version + ".cwl"),
                name=name,
                version=version)
            workflow_obj(validate=False)
            try:
                workflow_obj.generate_workflow_image(
                    workflow_image_path
                )
            except Exception as e:
                logger.error(f"Could not generate image for {workflow_image_path} - {e}")
                continue
            workflow_paths.append(
                (workflow.name, workflow_image_path, workflow_image_url)
            )

        return workflow_paths

    def create_and_commit_to_release_artifacts(self):
        """
        Create the release artifacts branch
        :return:
        """
        # Quick respite for the filesystem before checking git changes
        sleep(3)

        # Add outputs
        git_add_command = [
            "git", "add", self.get_release_artifact_output_path()
        ]

        git_add_returncode, git_add_stdout, git_add_stderr = run_subprocess_proc(
            git_add_command,
            capture_output=True
        )

        if not git_add_returncode == 0:
            logger.error(f"Got a non-zero exit code when running git add")
            logger.error(f"Stdout: {git_add_stdout}")
            logger.error(f"Stderr: {git_add_stderr}")
            raise ChildProcessError

        # Now check changes
        git_diff_command = [
            "git", "diff", "--name-only", "--cached", "--quiet"
        ]

        git_diff_returncode, git_diff_stdout, git_diff_stderr = run_subprocess_proc(
            git_diff_command,
            capture_output=True
        )

        if git_diff_returncode not in [0, 1]:
            logger.error(f"Got a non-zero exit code when running git diff")
            logger.error(f"Stdout: {git_diff_stdout}")
            logger.error(f"Stderr: {git_diff_stderr}")
            raise ChildProcessError

        if git_diff_returncode == 0:
            logger.info("No release artifacts to commit - skipping")
            return
        # Exit code 1 means there were changes to check

        # Commit files
        git_commit_command = [
            "git", "commit",
            "-m", f"Uploading visual images for {self.release_name} release"
        ]

        git_commit_returncode, git_commit_stdout, git_commit_stderr = run_subprocess_proc(
            git_commit_command,
            capture_output=True
        )

        if not git_commit_returncode == 0:
            logger.error(f"Got a non-zero exit code when running git acommit")
            logger.error(f"Stdout: {git_commit_stdout}")
            logger.error(f"Stderr: {git_commit_stderr}")
            raise ChildProcessError

    def fast_forward_tags(self):
        """
        Fast-forward tags after commit
        :return:
        """
        for tag in self.github_tag:
            git_tag_command = [
                "git", "tag",
                "--annotate",
                "--message", f"Release of {self.release_name}",
                "--force", tag
            ]

            # Set configuration so user is associated with the tags
            proc_environ = environ.copy()

            proc_environ.update(
                {
                    "GIT_AUTHOR_NAME": environ.get("_GIT_AUTHOR_NAME"),
                    "GIT_AUTHOR_EMAIL": environ.get("_GIT_AUTHOR_EMAIL")
                }
            )

            git_tag_returncode, git_tag_stdout, git_tag_stderr = run_subprocess_proc(
                git_tag_command,
                env=proc_environ,
                capture_output=True
            )

            if not git_tag_returncode == 0:
                logger.error(f"Got a non-zero exit code when running git tag")
                logger.error(f"Stdout: {git_tag_stdout}")
                logger.error(f"Stderr: {git_tag_stderr}")
                raise ChildProcessError

    def push_branch_and_tags(self):
        """
        Push branch and tags
        :return:
        """
        # Set configuration so user is associated with the push event
        proc_environ = environ.copy()

        proc_environ.update(
            {
                "GIT_AUTHOR_NAME": environ.get("_GIT_AUTHOR_NAME"),
                "GIT_AUTHOR_EMAIL": environ.get("_GIT_AUTHOR_EMAIL")
            }
        )

        git_push_command = [
            "git", "push",
            "--set-upstream", "origin",
            self.artifacts_branch
        ]
        git_push_returncode, git_push_stdout, git_push_stderr = run_subprocess_proc(
            git_push_command,
            env=proc_environ,
            capture_output=True
        )

        if not git_push_returncode == 0:
            logger.error(f"Got a non-zero exit code when running git push")
            logger.error(f"Stdout: {git_push_stdout}")
            logger.error(f"Stderr: {git_push_stderr}")
            raise ChildProcessError

        git_push_tags_command = [
            "git", "push", "--tags", "--force"
        ]
        git_push_tags_returncode, git_push_tags_stdout, git_push_tags_stderr = run_subprocess_proc(
            git_push_tags_command,
            env=proc_environ,
            capture_output=True
        )

        if not git_push_tags_returncode == 0:
            logger.error(f"Got a non-zero exit code when running git push tags")
            logger.error(f"Stdout: {git_push_tags_stdout}")
            logger.error(f"Stderr: {git_push_tags_stderr}")
            raise ChildProcessError

    def upload_release_assets_and_create_release(self):
        """
        Create the release asset
        :return:
        """
        # Ensure second tag exists first
        git_tag_command = [
            "git", "tag", "--force", self.github_tag[1]
        ]
        git_tag_returncode, git_tag_stdout, git_tag_stderr = run_subprocess_proc(
            git_tag_command,
            capture_output=True
        )

        if not git_tag_returncode == 0:
            logger.error(f"Got a non-zero exit code when running git tag")
            logger.error(f"Stdout: {git_tag_stdout}")
            logger.error(f"Stderr: {git_tag_stderr}")
            raise ChildProcessError

        # And push it
        git_push_tags_command = [
            "git", "push", "--tags", "--force"
        ]
        git_push_tags_returncode, git_push_tags_stdout, git_push_tags_stderr = run_subprocess_proc(
            git_push_tags_command,
            capture_output=True
        )

        if not git_push_tags_returncode == 0:
            logger.error(f"Got a non-zero exit code when running git tag")
            logger.error(f"Stdout: {git_push_tags_stdout}")
            logger.error(f"Stderr: {git_push_tags_stderr}")
            raise ChildProcessError

        gh_create_release_command = [
            "gh", "release", "create",
            self.github_tag[1],
            "--title", self.github_tag[1]
        ]

        if self.is_draft_release:
            gh_create_release_command.append("--prerelease")

        gh_create_release_command.extend(
            [
                self.packed_workflow_path,
                self.zipped_workflow_path,
                self.json_schema_gen_path,
                self.input_template_json_path,
                self.input_template_yaml_path,
                self.overrides_template_json,
                self.overrides_template_yaml
            ]
        )

        gh_returncode, gh_stdout, gh_stderr = run_subprocess_proc(
            gh_create_release_command,
            capture_output=True
        )

        if not gh_returncode == 0:
            logger.error(
                "Did not successfully create release"
            )
            logger.error(f"Stdout was {gh_stdout}")
            logger.error(f"Stderr was {gh_stderr}")
            raise ChildProcessError

    def create_release_artifacts_pr(self):
        """
        Create release artifacts PR
        :return:
        """
        gh_pr_command = [
            "gh", "pr", "create",
            "--base", "main",  # FIXME - use dev if this is a pre-release
            "--head", self.artifacts_branch,
            "--title", f"[GitHub Actions] Images and configuration commits for release {self.release_name}",
            "--body", f"See {self.release_url} for more information."
        ]

        gh_pr_returncode, gh_pr_stdout, gh_pr_stderr = run_subprocess_proc(
            gh_pr_command,
            capture_output=True
        )

        if not gh_pr_returncode == 0:
            logger.error(
                "Did not successfully create release"
            )
            logger.error(f"Stdout was {gh_pr_stdout}")
            logger.error(f"Stderr was {gh_pr_stderr}")
            raise ChildProcessError

    def create_dockstore_commit(self):
        """
        Appends the workflows section of the .dockstore.yml file in the top directory of the repository
        with the following attributes.

        If the item already exists in the dockstore yaml file, we append with a new version of the latest tag

        - name: workflow__version ('.' substituted for '_' in version)
          subclass: CWL
          primaryDescriptorPath: path/to/.dockstore/<workflow>/<version>/workflow__version.dockstore.cwl.packed.json
          readMePath: .github/catalog/<workflow>/<version>/workflow__version.md
          authors:
            - # From maintainer and authorship attributes of the file
          latestTagAsDefault: true  # Not sure how this will affect things - is this the bottom tag?
          filters:
            tags:
             - <workflow>/<version>
             - <workflow>/<version>__<epoch>
             - __append new version if new tag pushed__
        :return:

        We commit, tag, and create a PR for the dockstore.yml file
        """

        # Update Dockstore yaml file
        append_workflow_to_dockstore_yaml(self.cwl_file_path, self.packed_workflow_path, self.github_tag)

        # Quick respite for the filesystem before checking for changes
        sleep(3)

        # Add files
        git_add_command = [
            "git", "add", get_dockstore_yaml_path(), get_dockstore_dir()
        ]

        git_add_returncode, git_add_stdout, git_add_stderr = run_subprocess_proc(
            git_add_command,
            capture_output=True
        )

        if not git_add_returncode == 0:
            logger.error(f"Got a non-zero exit code when running git add")
            logger.error(f"Stdout: {git_add_stdout}")
            logger.error(f"Stderr: {git_add_stderr}")
            raise ChildProcessError

        # Check if there were any differences
        git_diff_command = [
            "git", "diff", "--name-only", "--cached", "--quiet"
        ]

        git_diff_returncode, git_diff_stdout, git_diff_stderr = run_subprocess_proc(
            git_diff_command,
            capture_output=True
        )

        if git_diff_returncode not in [0, 1]:
            logger.error(f"Got a non-zero exit code when running git diff")
            logger.error(f"Stdout: {git_diff_stdout}")
            logger.error(f"Stderr: {git_diff_stderr}")
            raise ChildProcessError

        if git_diff_returncode == 0:
            logger.info("No dockstore changes to commit - skipping")
            return
        # Exit code 1 means there where changes to commit

        # Commit
        git_commit_command = [
            "git", "commit",
            "-m",
            f"Updated .dockstore.yml and packed json to include {self.cwl_file_path} with tags {', '.join(self.github_tag)}"
        ]

        git_commit_returncode, git_commit_stdout, git_commit_stderr = run_subprocess_proc(
            git_commit_command,
            capture_output=True
        )

        if not git_commit_returncode == 0:
            logger.error(f"Got a non-zero exit code when running git commit")
            logger.error(f"Stdout: {git_commit_stdout}")
            logger.error(f"Stderr: {git_commit_stderr}")
            raise ChildProcessError

    def create_and_commit_v2_bundles(self):
        """
        This will create a bundle object from a bunch

        The bundle object will be written back to the icav2 configuration yaml if a bunch exists for this workflow.

        We need a PR to accept the bundle configuration that was generated and the projects it was added to.

        In future, the bundle generation will trigger validation data workflows
        :return:
        """
        # Iterate through bunches - see if any contain this cwl file path
        bunches = list(
            map(
                lambda bunch_dict: Bunch.from_dict(bunch_dict),
                read_config_yaml().get("bunches", [])
            )
        )

        bunches_filtered = list(
            filter(
                lambda bunch_iter: bunch_iter.pipeline_path == self.cwl_file_path.relative_to(get_cwl_ica_repo_path()),
                bunches
            )
        )

        if len(bunches_filtered) == 0:
            # No bunches to PR
            return

        # Create a pipeline for each tenant / pipeline project combination
        # Pipelines are then generated for each combination and stored in a map
        tenants = list(
            set(
                map(
                    lambda bunch_iter: bunch_iter.tenant_name,
                    bunches_filtered
                )
            )
        )

        create_cwl_workflow_from_github_release_command = [
            f"{os.environ['ICAV2_CLI_PLUGINS_HOME']}/pyenv/bin/python",
            f"{os.environ['ICAV2_CLI_PLUGINS_HOME']}/pyenv/bin/icav2-cli-plugins.py",
            "projectpipelines",
            "create-cwl-pipeline-from-github-release",
            self.release_url,
            "--json"  # Return pipeline_id
        ]

        release_pipeline_command_prefix = [
            f"{os.environ['ICAV2_CLI_PLUGINS_HOME']}/pyenv/bin/python",
            f"{os.environ['ICAV2_CLI_PLUGINS_HOME']}/pyenv/bin/icav2-cli-plugins.py",
            "projectpipelines",
            "release",
        ]

        pipeline_ids_by_project_by_tenant = {}
        icav2_bundles_by_tenant_by_project = {}

        # Iterate over tenants
        for tenant_name in tenants:
            # Iterate over pipeline projects for this tenant
            # One pipeline is made per project-name per tenant
            # Bunches that use the same project-name in the same tenant will share pipeline ids
            # This is intentional
            pipeline_project_names_in_tenant = list(
                set(
                    map(
                        lambda bunch_map_iter: bunch_map_iter.pipeline_project_name,
                        filter(
                            lambda bunch_filter_iter: bunch_filter_iter.tenant_name == tenant_name,
                            bunches_filtered
                        )
                    )
                )
            )

            pipeline_ids_by_project_by_tenant[tenant_name] = {}
            icav2_bundles_by_tenant_by_project[tenant_name] = []

            for pipeline_project_name in pipeline_project_names_in_tenant:
                pipeline_project_id = get_project_id_from_project_name(tenant_name, pipeline_project_name)

                # Create pipeline from GitHub release
                proc_environ = os.environ.copy()

                proc_environ.update(
                    {
                        "ICAV2_BASE_URL": ICAV2_DEFAULT_BASE_URL,
                        "ICAV2_PROJECT_ID": pipeline_project_id,
                        "ICAV2_ACCESS_TOKEN": get_tenant_access_token(tenant_name)
                    }
                )

                (
                    create_cwl_workflow_from_github_release_returncode,
                    create_cwl_workflow_from_github_release_stdout,
                    create_cwl_workflow_from_github_release_stderr
                ) = run_subprocess_proc(
                    create_cwl_workflow_from_github_release_command,
                    env=proc_environ,
                    capture_output=True
                )

                if not create_cwl_workflow_from_github_release_returncode == 0:
                    logger.error(f"{create_cwl_workflow_from_github_release_stdout}")
                    logger.error(f"{create_cwl_workflow_from_github_release_stderr}")
                    raise ChildProcessError

                # Collect pipeline
                try:
                    pipeline_id_json_dict = json.loads(create_cwl_workflow_from_github_release_stdout)
                except JSONDecodeError:
                    logger.error(f"Could not get release from {create_cwl_workflow_from_github_release_stdout}")
                    raise JSONDecodeError

                if 'pipeline_id' not in pipeline_id_json_dict:
                    logger.error(f"Could not get pipeline id key {pipeline_id_json_dict}")
                    raise KeyError
                pipeline_id = pipeline_id_json_dict.get("pipeline_id")

                # Release pipeline
                release_pipeline_command = release_pipeline_command_prefix + [pipeline_id]

                (
                    release_pipeline_returncode,
                    release_pipeline_stdout,
                    release_pipeline_stderr
                ) = run_subprocess_proc(
                    release_pipeline_command,
                    env=proc_environ,
                    capture_output=True
                )

                if not release_pipeline_returncode == 0:
                    logger.error(f"{release_pipeline_stdout}")
                    logger.error(f"{release_pipeline_stderr}")
                    raise ChildProcessError

                # Update pipeline list
                pipeline_ids_by_project_by_tenant[tenant_name][pipeline_project_id] = pipeline_id

        self.pipeline_ids_by_project_by_tenant = pipeline_ids_by_project_by_tenant

        # Create bundles
        bundle_objs = []

        for bunch in bunches_filtered:
            # Make a bundle for each bunch that contains the cwl file path
            # May be multiple, reference bunches, validation bunches etc.

            # Get latest bunch version
            latest_bunch_version: BunchVersion = bunch.bunch_versions[-1]

            pipeline_project_id = get_project_id_from_project_name(bunch.tenant_name, bunch.pipeline_project_name)

            bundle_obj = latest_bunch_version.generate_bundle_from_bunch_version(
                pipeline_commit_id=self.github_tag[1],
                pipeline_release_url=self.release_url,
                pipeline_id=pipeline_ids_by_project_by_tenant[bunch.tenant_name][pipeline_project_id],
                pipeline_checksum=self.cwl_obj.md5sum,
                pipeline_project_id=pipeline_project_id,
                tenant_access_token=get_tenant_access_token(bunch.tenant_name),
            )

            bundle_objs.append(
                bundle_obj
            )

            icav2_bundles_by_tenant_by_project[bunch.tenant_name].append(bundle_obj.bundle_id)

        self.icav2_bundles_by_tenant = icav2_bundles_by_tenant_by_project
        self.bundle_objs = bundle_objs

        # Write out bunch objects to icav2 configuration yaml
        config_yaml_obj = read_config_yaml()

        if "bundles" not in config_yaml_obj.keys():
            bundles_list_dict = CommentedSeq()
            config_yaml_obj.yaml_set_comment_before_after_key(
                key="bundles",
                before="\nList of generated bundles"
            )
        else:
            bundles_list_dict = config_yaml_obj.get("bundles")

        # Append new bundle objs to list
        for bundle in bundle_objs:
            bundles_list_dict.append(bundle.to_dict())

        config_yaml_obj["bundles"] = bundles_list_dict

        write_config_yaml(config_yaml_obj)

        # Allow the file system to catch up on changes
        sleep(3)

        # Add / commit file
        git_add_command = [
            "git", "add", get_icav2_config_yaml_path()
        ]

        git_add_returncode, git_add_stdout, git_add_stderr = run_subprocess_proc(
            git_add_command,
            capture_output=True
        )

        if not git_add_returncode == 0:
            logger.error(f"Got a non-zero exit code when running git add")
            logger.error(f"Stdout: {git_add_stdout}")
            logger.error(f"Stderr: {git_add_stderr}")
            raise ChildProcessError

        # Check if there are any differences
        git_diff_command = [
            "git", "diff", "--name-only", "--cached", "--quiet"
        ]

        git_diff_returncode, git_diff_stdout, git_diff_stderr = run_subprocess_proc(
            git_diff_command,
            capture_output=True
        )

        if git_diff_returncode not in [0, 1]:
            logger.error(f"Got a non-zero exit code when running git diff")
            logger.error(f"Stdout: {git_diff_stdout}")
            logger.error(f"Stderr: {git_diff_stderr}")
            raise ChildProcessError

        if git_diff_returncode == 0:
            logger.info("No bundle configurations to commit - skipping")
            return

        # Exit code 1 when using --quiet parameter means changes have been found

        # Now commit
        git_commit_command = [
            "git", "commit",
            "-m", f"Updated config/icav2.yaml to include new bundles"
        ]

        git_commit_returncode, git_commit_stdout, git_commit_stderr = run_subprocess_proc(
            git_commit_command,
            capture_output=True
        )

        if not git_commit_returncode == 0:
            logger.error(f"Got a non-zero exit code when running git commit")
            logger.error(f"Stdout: {git_commit_stdout}")
            logger.error(f"Stderr: {git_commit_stderr}")
            raise ChildProcessError
