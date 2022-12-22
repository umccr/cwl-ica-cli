#!/usr/bin/env python3

"""
Helpers for the gh command
"""

import json
from utils.subprocess_handler import run_subprocess_proc
from utils.logging import get_logger
from pathlib import Path
from base64 import b64encode
import os


logger = get_logger()


def get_user_id(user_name: str) -> int:
    gh_get_user_id_command = [
        "gh", "api", f"users/{user_name}"
    ]

    gh_get_user_id_proc, gh_get_user_id_stdout, gh_get_user_id_stderr = run_subprocess_proc(
        gh_get_user_id_command,
        capture_output=True
    )

    return json.loads(gh_get_user_id_stdout)["id"]


def create_release(release_name: str, release_notes: Path):
    """
    Create release from release path
    :param release_name:
    :param release_notes:
    :return:
    """

    gh_release_create_command = [
        "gh", "release", "create",
        release_name,
        "-F", release_notes
    ]

    gh_release_create_proc = run_subprocess_proc(
        gh_release_create_command,
        capture_output=True
    )


def get_github_url():
    github_server_url = os.environ["GITHUB_SERVER_URL"]
    github_repository = os.environ["GITHUB_REPOSITORY"]

    return "/".join([github_server_url, github_repository])


def get_repo_url_from_relative_repo_path(relative_path: Path) -> str:
    """
    Get repo url
    :param relative_path:
    :return:
    """
    blob = "blob/main"

    return "/".join(map(str, [get_github_url(), blob, relative_path]))


def get_releases_url() -> str:
    """
    Get the releases list url
    :return:
    """
    return get_github_url() + "/releases/tag/"


def get_gh_release_output_path() -> Path:
    """
    Get the output path for the release asset
    """
    return Path(".github") / "releases"
