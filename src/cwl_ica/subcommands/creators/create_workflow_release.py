#!/usr/bin/env python3

"""
Given an input to a workflow path,

Generate a tag locally and push the tag to GitHub.

This command will ensure that

1. CWL_ICA_REPO_PATH is on the 'main' GitHub branch
2. Is in sync with remote.

This command will also create a release on GitHub.
"""


# External imports
from argparse import ArgumentError
from pathlib import Path
from typing import Optional

# Utils
from ...utils.logging import get_logger
from ...utils.errors import CheckArgumentError

# Classes
from ...classes.command import Command
from ...utils.miscell import get_name_version_tuple_from_cwl_file_path
from ...utils.repo import get_workflows_dir
from ...utils.subprocess_handler import run_subprocess_proc

# Set logger
logger = get_logger()


class CreateWorkflowRelease(Command):
    """Usage:
    cwl-ica [options] workflow-release help
    cwl-ica [options] workflow-release (--workflow-path=<workflow_path>)
                                       [--draft]

Description:
    Release a workflow, this will push a github tag to the repository.
    This will trigger the GitHub Action command to build the workflow and workflow release assets.

Options:
    --workflow-path=<workflow_path>  Required, Path to the workflow to be released
    --draft                          Optional, Will create a draft release
Environment:

Example:
    cwl-ica workflow-release --workflow-path /path/to/workflow.cwl
    """

    def __init__(self, command_argv):

        # Collect args from doc strings
        super(CreateWorkflowRelease, self).__init__(command_argv)

        # Initialise parameters
        self.workflow_path: Optional[str] = None
        self.name: Optional[str] = None
        self.version: Optional[str] = None
        self.draft: bool = False
        self.tag = None

        # Check if help has been called
        if self.args["help"]:
            self._help()

        # Confirm 'required' arguments are present and valid
        try:
            logger.debug("Checking args")
            self.check_args()
        except ArgumentError:
            self._help(fail=True)

        self.set_tag()

    def check_args(self):
        # Get workflow path
        self.workflow_path = self.args.get("--workflow-path", None)
        if self.workflow_path is None:
            logger.error(f"Please use --workflow-path parameter")
            raise CheckArgumentError
        self.workflow_path = Path(self.workflow_path).absolute().resolve()
        self.name, self.version = get_name_version_tuple_from_cwl_file_path(
            self.workflow_path,
            items_dir=get_workflows_dir()
        )

        # Check if draft
        self.draft = self.args.get("--draft", False)

        # Set tag and check remote
        self.set_tag()

        self.git_checks()



    def set_tag(self):
        self.tag = self.name + "/" + self.version

        if self.draft:
            self.tag += "-rc"

    def git_checks(self):

        # Check all changes have been committed
        diff_returncode, diff_stdout, diff_stderr = run_subprocess_proc(
            [
                "git", "diff-index", "--quiet", "HEAD"
            ],
            capture_output=True
        )
        if diff_returncode != 0:
            logger.error("Please either stash or commit+push all your changes before continuing")
            raise CheckArgumentError

        # Get the name of the current branch
        get_branch_name_returncode, get_branch_name_stdout, get_branch_name_stderr = run_subprocess_proc(
            [
                "git", "rev-parse", "--abbrev-ref", "HEAD"
            ],
            capture_output=True
        )
        if get_branch_name_returncode != 0:
            logger.error("Please ensure you are on the main branch before continuing")
            raise CheckArgumentError
        branch_name = get_branch_name_stdout.strip()

        if not self.draft:
            # Check we're on the main branch
            if branch_name != "main":
                logger.error("Please ensure you are on the main branch before continuing")
                raise CheckArgumentError

        # Check we're in sync with the remote branch
        get_remote_branch_returncode, get_remote_branch_stdout, get_remote_branch_stderr = run_subprocess_proc(
            [
                "git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"
            ],
            capture_output=True
        )
        if get_remote_branch_returncode != 0:
            logger.error("Could not get the upstream branch for this ")
            raise CheckArgumentError
        remote_branch = get_remote_branch_stdout.strip()

        # Check diffs between remote and local
        diff_returncode, diff_stdout, diff_stderr = run_subprocess_proc(
            [
                "git", "diff", "--exit-code", branch_name, remote_branch
            ],
            capture_output=True
        )
        if diff_returncode != 0:
            logger.error("Please ensure you are in sync with the remote branch before continuing")
            raise CheckArgumentError

        # Check if tag is on the remote
        # "git ls-remote --exit-code --tags origin v1.2.3"
        og_log_level = logger.level
        logger.setLevel("CRITICAL")
        tag_remote_returncode, tag_remote_stdout, tag_remote_stderr = run_subprocess_proc(
            [
                "git", "ls-remote", "--exit-code", "--tags", "origin", self.tag
            ],
            capture_output=True
        )
        # Set back log level
        logger.setLevel(og_log_level)

        # Delete tag from origin
        if tag_remote_returncode == 0:
            logger.info(f"Tag {self.tag} exists on the remote, will need to delete first")

            # Delete tag
            delete_tag_returncode, delete_tag_stdout, delete_tag_stderr = run_subprocess_proc(
                [
                    "git", "push", "--delete", "origin", self.tag
                ],
                capture_output=True
            )


    def generate_tag(self):
        logger.info("Generating tag")
        tag_returncode, tag_stdout, tag_stderr = run_subprocess_proc(
            [
                "git", "tag", "--force", self.tag
            ],
            capture_output=True
        )

        if tag_returncode != 0:
            logger.error("Could not generate tag")
            logger.error(tag_stderr)
            raise CheckArgumentError

    def __call__(self):

        self.generate_tag()

        logger.info(f"Pushing tag {self.tag}")
        push_tag_returncode, push_tag_stdout, push_tag_stderr = run_subprocess_proc(
            [
                "git", "push", "origin", "--force", self.tag
            ],
            capture_output=True
        )

        if push_tag_returncode != 0:
            logger.error("Could not push tag")
            logger.error(push_tag_stderr)
            raise CheckArgumentError
