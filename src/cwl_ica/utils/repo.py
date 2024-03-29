#!/usr/bin/env python3

"""
Few repo requests
"""

# External imports
import os
from pathlib import Path
from ruamel.yaml import YAML

# Local utils
from .globals import CWL_ICA_REPO_PATH_ENV_VAR, GITHUB_DEFAULT_BRANCH
from .errors import CWLICARepoAssetNotFoundError, CWLICARepoNotFoundError
from .logging import get_logger

logger = get_logger()


def get_cwl_ica_repo_path():
    """
    Return CWL_ICA_REPO_PATH_ENV_VAR from environment
    :return:
    """

    # Get env var
    cwl_ica_repo_path = os.environ.get(CWL_ICA_REPO_PATH_ENV_VAR, None)

    # Check env var exists
    if cwl_ica_repo_path is None:
        logger.error(f"Error, could not get environment variable {CWL_ICA_REPO_PATH_ENV_VAR}. "
                     f"Please make sure you've run cwl-ica configure-repo and are in the cwl-ica conda environment."
                     f"If you have just run cwl-ica configure-repo, please deactivate then reactivate the environment")
        raise CWLICARepoNotFoundError

    # Convert to Path object
    cwl_ica_repo_path = Path(cwl_ica_repo_path)

    # Check repo path is a directory
    if not cwl_ica_repo_path.is_dir():
        logger.error(
            f"Found env var \"{CWL_ICA_REPO_PATH_ENV_VAR}\" but the directory \"{cwl_ica_repo_path}\" does not exist."
        )
        raise CWLICARepoNotFoundError

    return cwl_ica_repo_path


def get_configuration_path():

    config_path = get_cwl_ica_repo_path() / Path("config")

    if not config_path.is_dir():
        logger.error("Couldn't find \"config\" folder under {ica_repo_path_folder}.".format(
            ica_repo_path_folder=get_cwl_ica_repo_path()
        ))
        raise CWLICARepoNotFoundError

    return config_path


def get_tenant_yaml_path(non_existent_ok=False):

    config_path = get_configuration_path()

    tenant_yaml_path = config_path / Path("tenant.yaml")

    if not tenant_yaml_path.is_file() and not non_existent_ok:
        logger.error(f"Couldn't find \"tenant.yaml\" file in {config_path}")
        raise CWLICARepoAssetNotFoundError

    return tenant_yaml_path


def get_project_yaml_path(non_existent_ok=False):

    config_path = get_configuration_path()

    project_yaml_path = config_path / Path("project.yaml")

    if not project_yaml_path.is_file() and not non_existent_ok:
        logger.error(f"Couldn't find \"project.yaml\" file in {config_path}")
        raise CWLICARepoAssetNotFoundError

    return project_yaml_path


def get_category_yaml_path(non_existent_ok=False):

    config_path = get_configuration_path()

    category_yaml_path = config_path / Path("category.yaml")

    if not category_yaml_path.is_file() and not non_existent_ok:
        logger.error(f"Couldn't find \"category.yaml\" file in {config_path}")
        raise CWLICARepoAssetNotFoundError

    return category_yaml_path


def get_user_yaml_path(non_existent_ok=False):

    config_path = get_configuration_path()

    user_yaml_path = config_path / Path("user.yaml")

    if not user_yaml_path.is_file() and not non_existent_ok:
        logger.error(f"Couldn't find \"user.yaml\" file in {config_path}")
        raise CWLICARepoAssetNotFoundError

    return user_yaml_path


def get_tool_yaml_path(non_existent_ok=False):
    """
    Get the path to /config / tool.yaml
    :param non_existent_ok:
    :return:
    """

    config_path = get_configuration_path()

    tool_yaml_path = config_path / Path("tool.yaml")

    if not tool_yaml_path.is_file() and not non_existent_ok:
        logger.error(f"Couldn't find \"tool.yaml\" file in {config_path}")
        raise CWLICARepoAssetNotFoundError

    return tool_yaml_path


def get_tools_dir(create_dir=False):
    """
    returns <CWL_ICA_REPO_PATH>/tools
    :return:
    """
    tool_path = Path(get_cwl_ica_repo_path()) / "tools"

    if not tool_path.is_dir() and not create_dir:
        logger.error(f"Couldn't find tools directory at {tool_path}")
        raise CWLICARepoAssetNotFoundError
    else:
        tool_path.mkdir(parents=True, exist_ok=True)

    return tool_path


def get_workflow_yaml_path(non_existent_ok=False):
    """
    Get the path to /config / workflow.yaml
    :param non_existent_ok:
    :return:
    """

    config_path = get_configuration_path()

    workflow_yaml_path = config_path / Path("workflow.yaml")

    if not workflow_yaml_path.is_file() and not non_existent_ok:
        logger.error(f"Couldn't find \"workflow.yaml\" file in {config_path}")
        raise CWLICARepoAssetNotFoundError

    return workflow_yaml_path


def get_workflows_dir(create_dir=False):
    """
    returns <CWL_ICA_REPO_PATH>/workflows
    :param create_dir: 
    :return: 
    """
    workflow_path = Path(get_cwl_ica_repo_path()) / "workflows"

    if not workflow_path.is_dir() and not create_dir:
        logger.error(f"Couldn't find workflows directory at {workflow_path}")
        raise CWLICARepoAssetNotFoundError
    else:
        workflow_path.mkdir(parents=True, exist_ok=True)

    return workflow_path


def get_expression_yaml_path(non_existent_ok=False):
    """
    Get the path to /config / expression.yaml
    :param non_existent_ok:
    :return:
    """

    config_path = get_configuration_path()

    expression_yaml_path = config_path / Path("expression.yaml")

    if not expression_yaml_path.is_file() and not non_existent_ok:
        logger.error(f"Couldn't find \"expression.yaml\" file in {config_path}")
        raise CWLICARepoAssetNotFoundError

    return expression_yaml_path


def get_expressions_dir(create_dir=False):
    """
    returns <CWL_ICA_REPO_PATH>/expressions
    :param create_dir:
    :return:
    """
    expression_path = Path(get_cwl_ica_repo_path()) / "expressions"

    if not expression_path.is_dir() and not create_dir:
        logger.error(f"Couldn't find expressions directory at {expression_path}")
        raise CWLICARepoAssetNotFoundError
    else:
        expression_path.mkdir(parents=True, exist_ok=True)

    return expression_path


def get_schema_yaml_path(non_existent_ok=False):
    """
    Get the path to /config / schema.yaml
    :param non_existent_ok:
    :return:
    """

    config_path = get_configuration_path()

    schema_yaml_path = config_path / Path("schema.yaml")

    if not schema_yaml_path.is_file() and not non_existent_ok:
        logger.error(f"Couldn't find \"schema.yaml\" file in {config_path}")
        raise CWLICARepoAssetNotFoundError

    return schema_yaml_path


def get_schemas_dir(create_dir=False):
    """
    returns <CWL_ICA_REPO_PATH>/schemas
    :param create_dir:
    :return:
    """
    schema_path = Path(get_cwl_ica_repo_path()) / "schemas"

    if not schema_path.is_dir() and not create_dir:
        logger.error(f"Couldn't find schemas directory at {schema_path}")
        raise CWLICARepoAssetNotFoundError
    else:
        schema_path.mkdir(parents=True, exist_ok=True)

    return schema_path


def get_typescript_expressions_dir(create_dir=False):
    """
    returns <CWL_ICA_REPO_PATH>/typescript_expressions
    :param create_dir:
    :return:
    """
    typescript_expressions_path = Path(get_cwl_ica_repo_path()) / "typescript-expressions"

    if not typescript_expressions_path.is_dir() and not create_dir:
        logger.error(f"Couldn't find schemas directory at {typescript_expressions_path}")
        raise CWLICARepoAssetNotFoundError
    else:
        typescript_expressions_path.mkdir(parents=True, exist_ok=True)

    return typescript_expressions_path


def get_run_yaml_path(non_existent_ok=False):
    config_path = get_configuration_path()

    run_yaml_path = config_path / Path("run.yaml")

    if not run_yaml_path.is_file() and not non_existent_ok:
        logger.error(f"Couldn't find \"run.yaml\" file in {config_path}")
        raise CWLICARepoAssetNotFoundError

    return run_yaml_path


def get_gh_dir() -> Path:
    """
    :return:
    """

    return get_cwl_ica_repo_path() / ".github/"


def get_gh_catalogue_dir() -> Path:
    """
    Get the github actions catalogue directory - handy when running GH as will point to full url paths
    :return:
    """
    return get_gh_dir() / "catalogue"


def get_gh_run_graphs_dir() -> Path:
    return get_gh_catalogue_dir() / "images/runs"


def read_yaml(yaml_file):
    # Read in the cwl file from a yaml
    yaml = YAML()

    with open(yaml_file, "r") as yaml_h:
        yaml_obj = yaml.load(yaml_h)

    return yaml_obj


def get_branch_name() -> str:
    """
    Get the GitHub branch name, useful when creating plots locally
    :return:
    """
    return os.environ.get("GITHUB_BRANCH", GITHUB_DEFAULT_BRANCH)


def get_blob_url() -> str:
    return get_cwl_ica_repo_url() + f"/blob/{get_branch_name()}"


def get_raw_url() -> str:
    return get_cwl_ica_repo_url() + f"/raw/{get_branch_name()}"


def get_cwl_ica_repo_url() -> str:
    """
    Returns the repo url
    :return:
    """

    return os.environ["GITHUB_SERVER_URL"] + "/" + os.environ["GITHUB_REPOSITORY"]


def join_run_path_from_caller_path(caller_path: Path, run_path: Path) -> Path:
    """
    Join run path from the caller path
    Say I have a workflow at $PWD/workflow/bclconvert-with-qc-pipeline/4.0.3/bclconvert-with-qc-pipeline__4.0.3.cwl
    And this workflow calls ../../../expressions/get-file-from-directory/1.0.1/get-file-from-directory__1.0.1.cwl
    Return the value $PWD/expressions/get-file-from-directory/1.0.1/get-file-from-directory__1.0.1.cwl
    Another example may be a subworkflow which uses ../../ over ../../../
    So if $PWD/workflow/bclconvert-with-qc-pipeline/4.0.3/bclconvert-with-qc-pipeline__4.0.3.cwl calls
    ../../bclconvert-scatter/4.0.3/bclconvert-scatter__4.0.3.cwl, return
    $PWD/workflows/bclconvert-scatter/4.0.3/bclconvert-scatter__4.0.3.cwl
    :return:
    """
    return caller_path.parent.absolute().resolve().joinpath(
        run_path
    ).resolve()


def get_dockstore_dir() -> Path:
    """
    Get the abs path to the dockstore directory
    :return:
    """
    return get_cwl_ica_repo_path() / ".dockstore"
