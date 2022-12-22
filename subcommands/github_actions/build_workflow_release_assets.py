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
import gzip
import json
import os
import re
from argparse import ArgumentError
from tempfile import TemporaryDirectory
from urllib.parse import urldefrag
from zipfile import ZipFile

from classes.command import Command
from classes.cwl_workflow import CWLWorkflow
from utils.cwl_helper_utils import create_template_from_workflow_inputs, get_workflow_overrides_steps_dict, \
    get_type_from_cwl_io_object
from utils.cwl_workflow_helper_utils import zip_workflow, create_packed_workflow_from_zipped_workflow_path
from utils.gh_helpers import get_gh_release_output_path, get_github_url, get_releases_url

from utils.logging import get_logger

from pathlib import Path
from typing import Optional, List, Tuple
from mdutils import MdUtils
from utils.miscell import get_name_version_tuple_from_cwl_file_path, \
    get_items_dir_from_cwl_file_path, cwl_id_to_path
from utils.pydot_utils import get_step_path_from_step_obj
from utils.repo import get_workflows_dir
from utils.subprocess_handler import run_subprocess_proc

from cwl_utils.parser import load_document_by_uri

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
    GTIHUB_TAG:           The GitHub tag(s) that triggered this workflow
    """

    DEFAULT_OUTPUT_PATH = "cwl-ica-catalogue.md"
    DEFAULT_TITLE = "UMCCR CWL-ICA Catalogue"

    def __init__(self, command_argv):
        # Collect args from doc strings
        super().__init__(command_argv)

        # Initialise values
        self.cwl_file_path = None  # type: Optional[Path]
        self.cwl_obj = None  # type: Optional[CWLWorkflow]

        self.github_tag = None  # type: Optional[str]
        self.release_name = None  # type: Optional[str]
        self.release_url = None  # type: Optional[str]
        self.is_draft_release = None  # type: Optional[bool]

        # Release assets
        self.zipped_workflow_path = None  # type: Optional[Path]
        self.packed_workflow_path = None  # type: Optional[Path]
        self.zipped_cwl_obj = None  # type: Optional[CWLWorkflow]

        # Release artifacts
        self.release_artifacts_tmpdir = TemporaryDirectory()
        self.release_artifacts_path = None  # type: Optional[Path]
        self.release_artifacts_branch = None  # type: Optional[str]
        self.md_file_obj = None  # type: Optional[MdUtils]
        self.md_path_tmpdir = TemporaryDirectory()
        self.md_path = None  # type: Optional[Path]
        self.workflow_image_paths = None  # type: Optional[List[Tuple[str, Path, str]]]

        # Check args
        self.check_args()

        # Create the zipped workflow object
        self.create_zipped_workflow_obj()

        # Create release assets
        self.create_compressed_packed_workflow()

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
        self.cwl_file_path = Path(cwl_file_path_arg)

        if not self.cwl_file_path.is_file():
            logger.error(f"Could not find file {self.cwl_file_path}")
            raise FileNotFoundError

        # Get name, version from cwl file path
        name, version = get_name_version_tuple_from_cwl_file_path(
            self.cwl_file_path,
            items_dir=get_items_dir_from_cwl_file_path(self.cwl_file_path))

        self.cwl_obj = CWLWorkflow(
            cwl_file_path=self.cwl_file_path,
            name=name,
            version=version
        )
        # Validate object
        self.cwl_obj()

        # Check GITHUB_TAG env var exists
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
        full_github_tag_regex_obj = re.fullmatch("(\S+/\S+)__(\d+)", self.github_tag[1])
        if full_github_tag_regex_obj is None:
            logger.error(f"GITHUB_TAG env var '{','.join(self.github_tag)}' is not formatted as expected")
            raise ArgumentError
        print(full_github_tag_regex_obj.group(1))
        if not full_github_tag_regex_obj.group(1) == self.github_tag[0]:
            logger.error(f"GITHUB_TAG env var '{','.join(self.github_tag)}' is not as expected")
            raise ArgumentError

        # Release name is cwl_file_path.name + __ + YYMMDDHHMMSS
        self.release_name = self.github_tag[1].replace("/", "__")
        self.release_url = self.get_release_url()
        self.release_artifacts_branch = f"{self.github_tag[1]}--release-artifacts"

        # Get zipped workflow path
        self.release_artifacts_path = Path(self.release_artifacts_tmpdir.name) / "release-artifacts"
        self.release_artifacts_path.mkdir(exist_ok=True, parents=True)
        self.zipped_workflow_path = self.release_artifacts_path / (self.release_name + ".zip")
        # packed_workflow_path
        self.packed_workflow_path = self.release_artifacts_path / (self.release_name + ".packed.cwl.json.gz")

        # Get md path
        self.md_path = Path(self.md_path_tmpdir.name) / "Release.md"

    def __call__(self):
        """
        Create the markdown file object
        :return:
        """
        # Create images
        self.workflow_image_paths = self.create_workflow_images()

        # Create file object
        self.create_markdown_file_object()

        # Commit and Create release artifacts branch
        self.create_and_commit_to_release_artifacts_branch()

        # Fast forward tags
        self.fast_forward_tags()

        # Push commit
        self.push_branch_and_tags()

        # Upload release
        self.upload_release_assets_and_create_release()

        # Create release artifacts PR
        self.create_release_artifacts_pr()

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

    def add_description(self):
        """
        Add in the description text file with the following contents

        Please see <this url> for a detailed description of this workflow
        :return:
        """

    def get_release_url(self):
        return get_releases_url() + self.release_name

    def create_markdown_file_object(self):
        self.initialise_markdown_file()
        self.add_header_section()
        self.add_visual_section()
        self.add_inputs_template_section()
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

        self.md_file_obj.new_line("<details>")
        self.md_file_obj.new_line("<summary>Click to expand!</summary>\n")

        self.md_file_obj.insert_code(
            json.dumps(
                create_template_from_workflow_inputs(self.cwl_obj.cwl_obj.inputs),
                indent=4
            )
        )

        self.md_file_obj.new_line("</details>\n")

    def add_overrides_template_section(self):
        from utils.cwl_helper_utils import shortname

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
            workflow_obj = CWLWorkflow(cwl_file_path=get_workflows_dir() / name / version / (name + "__" + version + ".cwl"),
                                       name=name,
                                       version=version)
            workflow_obj()
            workflow_obj.generate_workflow_image(
                workflow_image_path
            )
            workflow_paths.append(
                (workflow.name, workflow_image_path, workflow_image_url)
            )

        return workflow_paths

    def create_and_commit_to_release_artifacts_branch(self):
        """
        Create the release artifacts branch
        :return:
        """
        # Create and checkout new branch
        # FIXME use gh api for these three commands
        git_checkout_command = [
            "git", "checkout",
            "-b", self.release_artifacts_branch
        ]

        git_checkout_proc = run_subprocess_proc(
            git_checkout_command,
            capture_output=True
        )

        # Commit files
        git_add_command = [
            "git", "add", self.get_release_artifact_output_path()
        ]

        git_add_proc = run_subprocess_proc(
            git_add_command,
            capture_output=True
        )

        git_commit_command = [
            "git", "commit",
            "-m", f"Uploading visual images for {self.release_name} release"
        ]

        git_commit_proc = run_subprocess_proc(
            git_commit_command,
            capture_output=True
        )

    def fast_forward_tags(self):
        """
        Fast forward tags after commit
        :return:
        """
        # FIXME use gh api for these commands
        for tag in self.github_tag:
            git_tag_command = [
                "git", "tag", "--force", tag
            ]
            git_tag_proc = run_subprocess_proc(
                git_tag_command,
                capture_output=True
            )

    def push_branch_and_tags(self):
        """
        Push branch and tags
        :return:
        """
        # FIXME could be redundant if we can use gh api in previous step
        git_push_command = [
            "git", "push",
            "--set-upstream", "origin",
            self.release_artifacts_branch
        ]
        git_push_proc = run_subprocess_proc(
            git_push_command,
            capture_output=True
        )

        git_push_tags_command = [
            "git", "push", "--tags", "--force"
        ]
        git_push_tags_proc = run_subprocess_proc(
            git_push_tags_command,
            capture_output=True
        )

    def upload_release_assets_and_create_release(self):
        """
        Create the release asset
        :return:
        """

        gh_create_release_command = [
            "gh", "release", "create", self.github_tag[1],
            "--notes-file",  self.md_path,
        ]

        if self.is_draft_release:
            gh_create_release_command.append("--prerelease")

        gh_create_release_command.extend(
            [
                self.packed_workflow_path,
                self.zipped_workflow_path
            ]
        )

        gh_returncode, gh_stdout, gh_stderr = run_subprocess_proc(
            gh_create_release_command,
            capture_output=True
        )

    def create_release_artifacts_pr(self):
        """
        Create release artifacts PR
        :return:
        """
        gh_pr_command = [
            "gh", "pr", "create",
            "--base", "main",  # FIXME - use dev if this is a pre-release
            "--head", self.release_artifacts_branch,
            "--title", f"Add in images for release {self.release_name}",
            "--body", f"See {self.release_url} for more information"
        ]

        gh_pr_proc = run_subprocess_proc(
            gh_pr_command,
            capture_output=True
        )
