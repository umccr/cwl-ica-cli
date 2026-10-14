#!/usr/bin/env python

"""
One great goal of mine is to never have a file called miscell.py
Yet every project of mine has always had one, and probably always will.

A refined goal is to actively reduce the number of functions in this file.
"""

# External imports
from urllib.parse import urlparse, ParseResult, urldefrag
from pathlib import Path
import os
from base64 import b64encode, b64decode
import zlib
from deepdiff import DeepDiff
import json
from typing import Dict, Any
from datetime import datetime
from string import ascii_letters, digits
import re

# Local imports
from .repo import read_yaml, get_blob_url, get_raw_url
from .yaml import dump_yaml
from .logging import get_logger
from .errors import CWLFileNameError
from .repo import get_cwl_ica_repo_path
from .errors import InvalidNameError

# Set logger
logger = get_logger()


def get_items_dir_from_cwl_file_path(cwl_file_path: Path) -> Path:
    """
    Get the absolute path of the items directory from the cwl file path
    :param cwl_file_path:
    :return:
    """
    return \
        get_cwl_ica_repo_path().joinpath(
            Path(
                cwl_file_path.absolute().resolve().relative_to(
                    get_cwl_ica_repo_path()
                ).parts[0]
            )
        )


def write_item_yaml(items, item_type_key, item_yaml):
    """
    Mostly static method
    :return:
    """

    # Check if we have any tools registered
    if not Path(item_yaml).is_file():
        all_items_list = []
    else:
        all_items_list = read_yaml(item_yaml)[item_type_key]

    new_all_items_list = [item.copy() for item in all_items_list]

    for item_obj in items:
        for i, item_dict in enumerate(all_items_list):
            if item_dict.get("name") == item_obj.name:
                new_all_items_list[i] = item_obj.to_dict()
                break
        else:
            new_all_items_list.append(item_obj.to_dict())

    with open(item_yaml, "w") as item_yaml_h:
        dump_yaml({item_type_key: new_all_items_list}, item_yaml_h)


def get_name_version_tuple_from_cwl_file_path(cwl_file_path, items_dir):
    """
    We confirm that the cwl_file_path is in a subfolder of the item_dir
    :param cwl_file_path: Path to the cwl file
    :param items_dir: Either tools/ workflowls/ etc
    :return:
    """

    name_version_path = Path(cwl_file_path).absolute().resolve().relative_to(items_dir)

    name_version_file_split = name_version_path.name.split("__", 1)

    if len(name_version_file_split) < 2:
        logger.error(f"Could not split name and version from {name_version_path.name}. "
                     f"Please name under {items_dir} as "
                     f"<name>/<version>/<name>__<version>.cwl.")
        raise CWLFileNameError

    name_file = name_version_file_split[0]
    version_file = name_version_file_split[1]
    version_file = Path(version_file).resolve().stem

    name_dir = name_version_path.parent.parent.name
    version_dir = name_version_path.parent.name

    if not name_file == name_dir:
        logger.error(f"CWL file has incorrect naming convention, please name under {items_dir} as"
                     f"<name>/<version>/<name>__<version>.cwl. "
                     f"But got first <name> as {name_dir} and second <name> as {name_file}")
        raise CWLFileNameError

    if not version_file == version_dir:
        logger.error(f"CWL file has incorrect naming convention, please name under {items_dir} as"
                     f"<name>/<version>/<name>__<version>.cwl.  "
                     f"But got first <version> as {version_dir} and second <version> as {version_file}")
        raise CWLFileNameError

    return name_file, version_file


def encode_compressed_base64(uncompressed_string):
    """
    Compress string then base64 string

    1. Encode to ascii
    2. Convert to bytes for zlib compression
    3. Encode as base64
    4. Decode as ascii

    :param uncompressed_string:
    :return:
    """

    return b64encode(
            zlib.compress(bytes(uncompressed_string.encode('ascii')))
           ).decode('ascii')


def decode_compressed_base64(compressed_string):
    """
    Might thing we do the opposite? Ah no
    1. Decode base64
    2. Decompress
    3. Decode as ascii
    :param compressed_string:
    :return:
    """

    return zlib.decompress(
             b64decode(compressed_string)
           ).decode('ascii')


def get_markdown_file_from_cwl_path(cwl_path: Path) -> Path:
    """
    From the cwl file path, get the path to the markdown file path
    :param cwl_path:
    :return:
    """
    # Get the relative path
    relative_cwl_path = cwl_path.absolute().resolve().relative_to(get_cwl_ica_repo_path())

    return (
        get_cwl_ica_repo_path() /
        ".github/catalogue/docs" /
        relative_cwl_path.parent /
        (relative_cwl_path.stem + ".md")
    )


def get_blob_url_to_markdown_file_from_cwl_path(cwl_path: Path) -> str:
    """
    From the step id, get the url to the markdown file
    :param cwl_path:
    :return:
    """
    # Get the relative path to CWL_ICA_REPO_PATH and then prefix with catalogue docs path
    markdown_path = get_markdown_file_from_cwl_path(cwl_path).absolute().resolve().relative_to(get_cwl_ica_repo_path())

    return get_blob_url() + "/" + str(markdown_path)


def get_blob_url_from_path(cwl_path: Path) -> str:
    """
    From the cwl path get the cwl url
    :param cwl_path:
    :return:
    """

    relative_cwl_path = cwl_path.absolute().resolve().relative_to(get_cwl_ica_repo_path())

    return get_blob_url() + "/" + str(relative_cwl_path)


def get_raw_url_from_path(cwl_path: Path) -> str:
    """
    From the path get the raw url
    :param cwl_path:
    :return:
    """
    relative_cwl_path = cwl_path.absolute().resolve().relative_to(get_cwl_ica_repo_path())

    return get_raw_url() + "/" + str(relative_cwl_path)


def get_graph_path_from_cwl_path(cwl_path: Path) -> Path:
    """
    From the cwl path get the path to the svg graph
    :param cwl_path:
    :return:
    """
    # Get the relative path
    relative_cwl_path = cwl_path.absolute().resolve().relative_to(get_cwl_ica_repo_path())

    return (
        get_cwl_ica_repo_path() /
        ".github/catalogue/images" /
        relative_cwl_path.parent /
        (relative_cwl_path.stem + ".svg")
    )


def cwl_id_to_path(cwl_id: str) -> Path:
    """
    Returns the bit after '#' and converts to a path object
    :param cwl_id:
    :return:
    """
    return Path(urldefrag(cwl_id).fragment)


def summarise_differences_of_two_dicts(dict_1: Dict, dict_2: Dict) -> str:
    """
    Summarise the difference of two dicts with deepdiff
    Credit: https://stackoverflow.com/a/50912266/6946787
    :param dict_1:
    :param dict_2:
    :return:
    """

    diff = DeepDiff(dict_1, dict_2)

    return json.dumps(json.loads(diff.to_json()), indent=4)


def check_shlex_arg(arg_name, arg_val):
    """
    If argument contains characters outside of A-Z, 0-9, -, _, then fail
    :return:
    """

    # Removed hyphens from name convention, can be used for the versioning only
    illegal_chars = set(arg_val).difference(ascii_letters + digits + "-_")

    if not len(illegal_chars) == 0:
        logger.error("The following illegal characters were found in arg {arg_name}"
                     "{arg_chars}".format(
                        arg_name=arg_name,
                        arg_chars=", ".join(["\"%s\"" % char for char in illegal_chars])
                     ))
        raise InvalidNameError


def camel_to_snake_case(camel_case: str) -> str:
    return re.sub(r'(?<!^)(?=[A-Z])', '_', camel_case).lower()


def sanitise_dict_keys(input_dict: Dict) -> Dict:
    output_dict = {}
    key: str
    value: Any
    for key, value in input_dict.items():
        output_dict[camel_to_snake_case(key)] = value
    return output_dict


def strip_trailing_slash_from_url(url: str) -> str:
    url_obj = urlparse(url)
    new_url_obj = ParseResult(
        scheme=url_obj.scheme,
        netloc=url_obj.netloc,
        path=url_obj.path.rstrip("/"),
        params="",
        query="",
        fragment=""
    )
    return new_url_obj.geturl()


def get_current_time_in_release_format() -> str:
    return datetime.utcnow().strftime("%y%m%d%H%M%S")
