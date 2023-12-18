#!/usr/bin/env python

"""cwl-ica ::: a functions suite for managing collections of cwl workflows on ica throughout multiple tenants and projects

Usage:
    cwl-ica [options] <command> [options] [<args>...]

Options:
    --debug                             Set the log level to debug

Command:

    help                                Print help and exit
    version                             Print version and exit

    ######################
    Configuration Commands
    ######################
    configure-repo                      One-time command to point to the cwl-ica git repository
    configure-tenant                    Create mapping of tenancy ids to tenancy names, convenience to save time typing out tenancy names
                                        Each project is linked to a tenancy id
    configure-user                      Add a user to user.yaml

    ##########################
    ICA Initialisers
    ##########################
    project-init                        Initialise a project in ${CWL_ICA_REPO_PATH}/config/project.yaml
    category-init                       Initialise a category in ${CWL_ICA_REPO_PATH}/config/category.yaml


    ########################
    Set Defaults Commands
    ########################
    set-default-tenant                  Set a tenant to the default tenant
    set-default-project                 Set a project to the default project
    set-default-user                    Set a user to the default user


    #########################
    # List Commands
    #########################
    list-categories                     List registered categories
    list-projects                       List registered projects
    list-tenants                        List registered tenants
    list-users                          List registered users


    #######################
    Creation Commands
    #######################
    create-expression-from-template     Initialise an CWL expression from the cwl expression template
    create-schema-from-template         Initialise a CWL schema from the cwl schema template
    create-tool-from-template           Initialise a CWL tool from the cwl tool template
    create-workflow-from-template       Initialise a CWL workflow from the cwl workflow template


    ###################
    Validation Commands
    ###################
    expression-validate                 Validate a CWL expression
    schema-validate                     Validate a CWL schema
    tool-validate                       Validate a CWL tool ready for initialising on ICA
    workflow-validate                   Validate a CWL workflow ready for initialising on ICA
    validate-config-yamls               Confirms configuration files are legit
    validate-api-key-script             Confirm an api-key-script works for a given project


    ###############
    Init Commands
    ###############
    expression-init                     Register an expression in ${CWL_ICA_REPO_PATH}/config/expression.yaml
    schema-init                         Register a schema in ${CWL_ICA_REPO_PATH}/config/schema.yaml
    tool-init                           Register a tool in ${CWL_ICA_REPO_PATH}/config/tool.yaml and with ICA projects
    workflow-init                       Register a workflow in ${CWL_ICA_REPO_PATH}/config/workflow.yaml and with ICA projects


    ########################
    Sync-to-project Commands
    ########################
    expression-sync                     Sync an expression in ${CWL_ICA_REPO_PATH}/config/expression.yaml
    tool-sync                           Sync a tool's md5sum in ${CWL_ICA_REPO_PATH}/config/tool.yaml
                                        and update definition on ICA
    schema-sync                         Sync a schema in ${CWL_ICA_REPO_PATH}/config/schema.yaml
    workflow-sync                       Sync a workflow's md5sum in ${CWL_ICA_REPO_PATH}/config/workflow.yaml
                                        and update definition on ICA


    #######################
    Add-to-project Commands
    #######################
    add-tool-to-project                 Add an existing tool to another project
    add-workflow-to-project             Add an existing workflow to another project
    add-linked-project                  Link an existing project-id to an initialised project in project.yaml


    ########################
    Add-category Commands
    ########################
    add-category-to-tool                Add an existing category to an existing tool
    add-category-to-workflow            Add an existing category to an existing workflow


    ############################
    Add-maintainer commands
    ############################
    add-maintainer-to-expression        Acknowledge a user as a maintainer of a cwl expression
    add-maintainer-to-tool              Acknowledge a user as a maintainer of a cwl tool
    add-maintainer-to-workflow          Acknowledge a user as a maintainer of a cwl workflow


    ###################################
    Submission Template Commands
    ###################################
    create-tool-submission-template         Create a input template and run script for a tool on ICA
    create-workflow-submission-template     Create a input template and run script for a workflow on ICA


    #############################
    Run-register Commands
    #############################
    register-tool-run-instance          Register an ICA workflow run instance of a tool for a given project
    register-workflow-run-instance      Register an ICA workflow run instance of a workflow for a given project


    #######################
    Query workflow Commands
    #######################
    get-workflow-step-ids               Get the step ids of a CWL workflow

    ##################
    Run-list Commands
    ##################
    list-tool-runs                      List registered tool runs for a CWL tool in a given project
    list-workflow-runs                  List registered workflows runs for a CWL workflow in a given project


    ################################
    Get Run-templates Commands
    ################################
    copy-tool-submission-template       Copy a tool submission template for an upcoming tool run
    copy-workflow-submission-template   Copy a workflow submission template for an upcoming workflow run


    #################################
    Typescript Extensions Commands
    #################################
    create-typescript-expression-from-template                 Initialise a new typescript expression in the typescript-expressions directory
    append-typescript-directory-to-cwl-expression-tool         Create a new typescript expression to complement a CWL expression
    append-typescript-directory-to-cwl-commandline-tool        Create a new typescript expression to complement a CWL tool
    append-typescript-directory-to-cwl-workflow                Create a new typescript expression to complement a CWL workflow
    create-typescript-interface-from-cwl-schema                Create a typescript interface to complement a CWL schema
    typescript-expression-validate                             Validate a typescript expression and generate a .cwljs file ready for importation by
    typescript-expression-update                               Update the dependencies in a typescript-expression directory


    #################################
    GitHub Actions Scripts
    #################################
    github-actions-sync-schemas                  Sync all schemas to schema.yaml
    github-actions-sync-expressions              Sync all expressions to expression.yaml
    github-actions-sync-tools                    Sync all tools to tool.yaml and to all projects with that tool version
    github-actions-sync-workflows                Sync workflows to workflow.yaml and to all projects with that workflow version
    github-actions-create-expression-markdown    Create a markdown help report file for a cwl expression
    github-actions-create-tool-markdown          Create a markdown help report file for a cwl tool
    github-actions-create-workflow-markdown      Create a markdown help report file for a cwl workflow
    github-actions-create-catalogue              Create the catalogue markdown file
    github-actions-build-workflow-release-asset  Create the release asset and push to release

    #################################
    # V2 Integrations
    #################################
    icav2-add-tenant                             Add tenant name to icav2 config
    icav2-add-project                            Add project name to icav2 config
    icav2-add-dataset                            Add icav2 dataset to icav2 config
    icav2-add-bunch                              Add bunch to icav2 config

    ##################################
    V2 Extensions
    ##################################
    icav2-zip-workflow                         Zip up a workflow ready to become a pipeline in icav2
"""

# External imports
from docopt import docopt
import sys

# Local Utils
from .__version__ import version
from .logging import set_basic_logger

# Set logger
logger = set_basic_logger()


def _dispatch():

    # This variable comprises both the subcommand AND the args
    global_args: dict = docopt(__doc__, sys.argv[1:], version=version, options_first=True)

    # Handle all global args we've set
    if global_args["--debug"]:
        logger.info("Setting logging level to 'DEBUG'")
        logger.setLevel(level="DEBUG")
    else:
        logger.setLevel(level="INFO")

    command_argv = [global_args["<command>"]] + global_args["<args>"]

    cmd = global_args['<command>']

    # Yes, this is just a massive if-else statement
    if cmd == "help":
        # We have a separate help function for each subcommand
        print(__doc__)
        sys.exit(0)
    elif cmd == "version":
        print(version)
        sys.exit(0)

    # Configuration commands
    elif cmd == "configure-repo":
        from ..subcommands.configure.configure_repo import ConfigureRepo as command_to_call
    elif cmd == "configure-tenant":
        from ..subcommands.configure.configure_tenant import ConfigureTenant as command_to_call
    elif cmd == "configure-user":
        from ..subcommands.configure.configure_user import ConfigureUser as command_to_call

    # Config initialiser commands
    elif cmd == "category-init":
        from ..subcommands.initialisers.category_init import CategoryInit as command_to_call
    elif cmd == "project-init":
        from ..subcommands.initialisers.project_init import ProjectInit as command_to_call

    # Set default commands
    elif cmd == "set-default-tenant":
        from ..subcommands.updaters.set_default_tenant import SetDefaultTenant as command_to_call
    elif cmd == "set-default-project":
        from ..subcommands.updaters.set_default_project import SetDefaultProject as command_to_call
    elif cmd == "set-default-user":
        from ..subcommands.updaters.set_default_user import SetDefaultUser as command_to_call

    # List commands
    elif cmd == "list-categories":
        from ..subcommands.listers.list_categories import ListCategories as command_to_call
    elif cmd == "list-projects":
        from ..subcommands.listers.list_projects import ListProjects as command_to_call
    elif cmd == "list-tenants":
        from ..subcommands.listers.list_tenants import ListTenants as command_to_call
    elif cmd == "list-users":
        from ..subcommands.listers.list_users import ListUsers as command_to_call

    # Creation commands
    elif cmd == "create-expression-from-template":
        from ..subcommands.creators.create_expression_from_template import CreateExpressionFromTemplate as command_to_call
    elif cmd == "create-schema-from-template":
        from ..subcommands.creators.create_schema_from_template import CreateSchemaFromTemplate as command_to_call
    elif cmd == "create-tool-from-template":
        from ..subcommands.creators.create_tool_from_template import CreateToolFromTemplate as command_to_call
    elif cmd == "create-workflow-from-template":
        from ..subcommands.creators.create_workflow_from_template import CreateWorkflowFromTemplate as command_to_call

    # Validation commands
    elif cmd == "expression-validate":
        from ..subcommands.validators.expression_validate import ExpressionValidate as command_to_call
    elif cmd == "schema-validate":
        from ..subcommands.validators.schema_validate import SchemaValidate as command_to_call
    elif cmd == "tool-validate":
        from ..subcommands.validators.tool_validate import ToolValidate as command_to_call
    elif cmd == "workflow-validate":
        from ..subcommands.validators.workflow_validate import WorkflowValidate as command_to_call
    elif cmd == "validate-config-yamls":
        from ..subcommands.validators.validate_config_yamls import ValidateConfigYamls as command_to_call
    elif cmd == "validate-api-key-script":
        from ..subcommands.validators.validate_api_key_script import ValidateApiKeyScript as command_to_call

    # Initialisation commands
    elif cmd == "expression-init":
        from ..subcommands.initialisers.expression_init import ExpressionInitialiser as command_to_call
    elif cmd == "schema-init":
        from ..subcommands.initialisers.schema_init import SchemaInitialiser as command_to_call
    elif cmd == "tool-init":
        from ..subcommands.initialisers.tool_init import ToolInitialiser as command_to_call
    elif cmd == "workflow-init":
        from ..subcommands.initialisers.workflow_init import WorkflowInitialiser as command_to_call

    # Sync to project commands
    elif cmd == "expression-sync":
        from ..subcommands.sync.sync_expression import ExpressionSync as command_to_call
    elif cmd == "schema-sync":
        from ..subcommands.sync.sync_schema import SchemaSync as command_to_call
    elif cmd == "tool-sync":
        from ..subcommands.sync.sync_tool import ToolSync as command_to_call
    elif cmd == "workflow-sync":
        from ..subcommands.sync.sync_workflow import WorkflowSync as command_to_call

    # Add to project commands --
    elif cmd == "add-tool-to-project":
        from ..subcommands.updaters.add_tool_to_project import AddToolToProject as command_to_call
    elif cmd == "add-workflow-to-project":
        from ..subcommands.updaters.add_workflow_to_project import AddWorkflowToProject as command_to_call

    # Add category to 'x' commands
    elif cmd == "add-category-to-tool":
        from ..subcommands.updaters.add_category_to_tool import AddCategoryToTool as command_to_call
    elif cmd == "add-category-to-workflow":
        from ..subcommands.updaters.add_category_to_workflow import AddCategoryToWorkflow as command_to_call

    # Add maintainer commands
    elif cmd == "add-maintainer-to-expression":
        from ..subcommands.updaters.add_maintainer_to_expression import AddMaintainerToExpression as command_to_call
    elif cmd == "add-maintainer-to-tool":
        from ..subcommands.updaters.add_maintainer_to_tool import AddMaintainerToTool as command_to_call
    elif cmd == "add-maintainer-to-workflow":
        from ..subcommands.updaters.add_maintainer_to_workflow import AddMaintainerToWorkflow as command_to_call

    # Project update command
    elif cmd == "add-linked-project":
        from ..subcommands.updaters.add_linked_project import LinkProject as command_to_call

    # Register run instance commands
    elif cmd == "register-tool-run-instance":
        from ..subcommands.initialisers.run_tool_init import RegisterToolRunInstance as command_to_call
    elif cmd == "register-workflow-run-instance":
        from ..subcommands.initialisers.run_workflow_init import RegisterWorkflowRunInstance as command_to_call
    elif cmd == "get-workflow-step-ids":
        from ..subcommands.query.get_workflow_step_ids import GetWorkflowStepIDs as command_to_call
    # Get run templates
    elif cmd == "copy-tool-submission-template":
        from ..subcommands.query.copy_tool_submission_template import CopyToolSubmissionTemplate as command_to_call
    elif cmd == "copy-workflow-submission-template":
        from ..subcommands.query.copy_workflow_submission_template import CopyWorkflowSubmissionTemplate as command_to_call
    elif cmd == "list-tool-runs":
        from ..subcommands.listers.list_tool_runs import ListToolRuns as command_to_call
    elif cmd == "list-workflow-runs":
        from ..subcommands.listers.list_workflow_runs import ListWorkflowRuns as command_to_call
    elif cmd == "create-tool-submission-template":
        from ..subcommands.query.create_tool_submission_template import CreateToolSubmissionTemplate as command_to_call
    elif cmd == "create-workflow-submission-template":
        from ..subcommands.query.create_workflow_submission_template import CreateWorkflowSubmissionTemplate as command_to_call

    # Github actions
    elif cmd == "github-actions-sync-schemas":
        from ..subcommands.sync.sync_github_actions_schema import SyncGitHubActionsSchema as command_to_call
    elif cmd == "github-actions-sync-expressions":
        from ..subcommands.sync.sync_github_actions_expression import SyncGitHubActionsExpression as command_to_call
    elif cmd == "github-actions-sync-tools":
        from ..subcommands.sync.sync_github_actions_tool import SyncGitHubActionsTool as command_to_call
    elif cmd == "github-actions-sync-workflows":
        from ..subcommands.sync.sync_github_actions_workflow import SyncGitHubActionsWorkflow as command_to_call
    elif cmd == "github-actions-create-expression-markdown":
        from ..subcommands.github_actions.create_expression_markdown_file import CreateExpressionMarkdownFile as command_to_call
    elif cmd == "github-actions-create-tool-markdown":
        from ..subcommands.github_actions.create_tool_markdown_file import CreateToolMarkdownFile as command_to_call
    elif cmd == "github-actions-create-workflow-markdown":
        from ..subcommands.github_actions.create_workflow_markdown_file import CreateWorkflowMarkdownFile as command_to_call
    elif cmd == "github-actions-create-catalogue":
        from ..subcommands.github_actions.create_catalogue import CreateCatalogue as command_to_call
    elif cmd == "github-actions-build-workflow-release-asset":
        from ..subcommands.github_actions.build_workflow_release_assets import BuildWorkflowReleaseAsset as command_to_call
    elif cmd == "create-typescript-expression-from-template":
        from ..subcommands.creators.create_typescript_expression_from_template import CreateTypeScriptExpressionFromTemplate as command_to_call
    elif cmd == "append-typescript-directory-to-cwl-expression-tool":
        from ..subcommands.appenders.append_typescript_dir_to_cwl_expression import AppendTypeScriptExpressionDir as command_to_call
    elif cmd == "append-typescript-directory-to-cwl-commandline-tool":
        from ..subcommands.appenders.append_typescript_to_tool import AppendTypeScriptToolDir as command_to_call
    elif cmd == "append-typescript-directory-to-cwl-workflow":
        from ..subcommands.appenders.append_typescript_to_workflow import AppendTypeScriptWorkflowDir as command_to_call
    elif cmd == "create-typescript-interface-from-cwl-schema":
        from ..subcommands.creators.create_typescript_from_schema import CreateTypeScriptInterfaceFromCWLSchema as command_to_call
    elif cmd == "typescript-expression-validate":
        from ..subcommands.validators.typescript_validate import TypeScriptExpressionDirValidate as command_to_call
    elif cmd == "typescript-expression-update":
        from ..subcommands.updaters.update_typescript_expressions_dir import TypeScriptExpressionDirUpdate as command_to_call

    # V2 Integrations
    elif cmd == "icav2-add-tenant":
        from ..subcommands.v2.icav2_config_add_tenant import ICAv2AddTenant as command_to_call
    elif cmd == "icav2-add-project":
        from ..subcommands.v2.icav2_config_add_project import ICAv2AddProject as command_to_call
    elif cmd == "icav2-add-dataset":
        from ..subcommands.v2.icav2_add_dataset import ICAv2AddDataset as command_to_call
    elif cmd == "icav2-add-bunch":
        from ..subcommands.v2.icav2_add_bunch import ICAv2AddBunch as command_to_call

    # V2 Extensions
    elif cmd == "icav2-zip-workflow":
        from ..subcommands.v2.zip_v2_workflow import ZipV2Workflow as command_to_call

    # NotImplemented Error
    else:
        print(__doc__)
        print(f"Could not find cmd \"{cmd}\". Please refer to usage above")
        sys.exit(1)

    # Initialise command
    command_obj = command_to_call(command_argv)

    # Call back command
    command_obj()


def main():
    # If only cwl-ica is written, append help s.t help documentation shows
    if len(sys.argv) == 1:
        sys.argv.append('help')
    try:
        _dispatch()
    except KeyboardInterrupt:
        pass
