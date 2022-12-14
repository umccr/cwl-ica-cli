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

    ##################################
    V2 Extensions
    ##################################
    icav2-zip-workflow                         Zip up a workflow ready to become a pipeline in icav2
    icav2-deploy-pipeline                      Deploy a zipped workflow to icav2
    icav2-launch-pipeline-analysis             Launch a workflow in v2
    icav2-list-analysis-steps                  List steps of an icav2 analysis
    icav2-get-analysis-step-logs               Get logs (stdout or stderr) of an analysis step
"""

from docopt import docopt
from utils.__version__ import version
import sys
from utils.logging import set_basic_logger

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
    elif cmd == "version":
        print(version)

    # Configuration commands
    elif cmd == "configure-repo":
        from subcommands.configure.configure_repo import ConfigureRepo
        # Initialise command
        configure_repo_obj = ConfigureRepo(command_argv)
        # Call command
        configure_repo_obj()
    elif cmd == "configure-tenant":
        from subcommands.configure.configure_tenant import ConfigureTenant
        # Initialise command
        configure_tenant_obj = ConfigureTenant(command_argv)
        # Call command
        configure_tenant_obj()
    elif cmd == "configure-user":
        from subcommands.configure.configure_user import ConfigureUser
        # Initialise command
        configure_project_obj = ConfigureUser(command_argv)
        # Call command
        configure_project_obj()

    # Config initialiser commands
    elif cmd == "category-init":
        from subcommands.initialisers.category_init import CategoryInit
        # Initialise command
        category_init_obj = CategoryInit(command_argv)
        # Call command
        category_init_obj()
    elif cmd == "project-init":
        from subcommands.initialisers.project_init import ProjectInit
        # Initialise command
        project_init_obj = ProjectInit(command_argv)
        # Call command
        project_init_obj()

    # Set default commands
    elif cmd == "set-default-tenant":
        from subcommands.updaters.set_default_tenant import SetDefaultTenant
        # Initialise command
        set_default_tenant_obj = SetDefaultTenant(command_argv)
        # Call command
        set_default_tenant_obj()
    elif cmd == "set-default-project":
        from subcommands.updaters.set_default_project import SetDefaultProject
        # Initialise command
        set_default_project_obj = SetDefaultProject(command_argv)
        # Call command
        set_default_project_obj()
    elif cmd == "set-default-user":
        from subcommands.updaters.set_default_user import SetDefaultUser
        # Initialise command
        set_default_user_obj = SetDefaultUser(command_argv)
        # Call command
        set_default_user_obj()

    # List commands
    elif cmd == "list-categories":
        from subcommands.listers.list_categories import ListCategories
        # Initialise command
        list_categories_obj = ListCategories(command_argv)
        # Call command
        list_categories_obj()
    elif cmd == "list-projects":
        from subcommands.listers.list_projects import ListProjects
        # Initialise command
        list_projects_obj = ListProjects(command_argv)
        # Call command
        list_projects_obj()
    elif cmd == "list-tenants":
        from subcommands.listers.list_tenants import ListTenants
        # Initialise Command
        list_tenants_obj = ListTenants(command_argv)
        # Call command
        list_tenants_obj()
    elif cmd == "list-users":
        from subcommands.listers.list_users import ListUsers
        # Initialise Command
        list_users_obj = ListUsers(command_argv)
        # Call command
        list_users_obj()

    # Creation commands
    elif cmd == "create-expression-from-template":
        from subcommands.creators.create_expression_from_template import CreateExpressionFromTemplate
        # Initialise command
        create_expression_obj = CreateExpressionFromTemplate(command_argv)
        # Call command
        create_expression_obj()
    elif cmd == "create-schema-from-template":
        from subcommands.creators.create_schema_from_template import CreateSchemaFromTemplate
        # Initialise command
        create_schema_obj = CreateSchemaFromTemplate(command_argv)
        # Call command
        create_schema_obj()
    elif cmd == "create-tool-from-template":
        from subcommands.creators.create_tool_from_template import CreateToolFromTemplate
        # Initialise command
        create_tool_obj = CreateToolFromTemplate(command_argv)
        # Call command
        create_tool_obj()
    elif cmd == "create-workflow-from-template":
        from subcommands.creators.create_workflow_from_template import CreateWorkflowFromTemplate
        # Initialise command
        create_workflow_obj = CreateWorkflowFromTemplate(command_argv)
        # Call command
        create_workflow_obj()

    # Validation commands
    elif cmd == "expression-validate":
        from subcommands.validators.expression_validate import ExpressionValidate
        # Initialise command
        expression_validate_obj = ExpressionValidate(command_argv)
        # Call command
        expression_validate_obj()
    elif cmd == "schema-validate":
        from subcommands.validators.schema_validate import SchemaValidate
        # Initialise command
        schema_validate_obj = SchemaValidate(command_argv)
        # Call command
        schema_validate_obj()
    elif cmd == "tool-validate":
        from subcommands.validators.tool_validate import ToolValidate
        # Initialise command
        tool_validate_obj = ToolValidate(command_argv)
        # Call command
        tool_validate_obj()
    elif cmd == "workflow-validate":
        from subcommands.validators.workflow_validate import WorkflowValidate
        # Initialise command
        workflow_validate_obj = WorkflowValidate(command_argv)
        # Call command
        workflow_validate_obj()
    elif cmd == "validate-config-yamls":
        from subcommands.validators.validate_config_yamls import ValidateConfigYamls
        # Init command
        validate_config_obj = ValidateConfigYamls(command_argv)
        # Call command
        validate_config_obj()
    elif cmd == "validate-api-key-script":
        from subcommands.validators.validate_api_key_script import ValidateApiKeyScript
        # Init command
        validate_api_key_script_obj = ValidateApiKeyScript(command_argv)
        # Call command
        validate_api_key_script_obj()

    # Initialisation commands
    elif cmd == "expression-init":
        from subcommands.initialisers.expression_init import ExpressionInitialiser
        # Initialise command
        expression_init_obj = ExpressionInitialiser(command_argv)
        # Call command
        expression_init_obj()
    elif cmd == "schema-init":
        from subcommands.initialisers.schema_init import SchemaInitialiser
        # Initialise command
        schema_init_obj = SchemaInitialiser(command_argv)
        # Call command
        schema_init_obj()
    elif cmd == "tool-init":
        from subcommands.initialisers.tool_init import ToolInitialiser
        # Initialise command
        tool_init_obj = ToolInitialiser(command_argv)
        # Call command
        tool_init_obj()
    elif cmd == "workflow-init":
        from subcommands.initialisers.workflow_init import WorkflowInitialiser
        # Initialise command
        workflow_init_obj = WorkflowInitialiser(command_argv)
        # Call command
        workflow_init_obj()

    # Sync to project commands
    elif cmd == "expression-sync":
        from subcommands.sync.sync_expression import ExpressionSync
        # Initialise Command
        expression_sync_obj = ExpressionSync(command_argv)
        # Call command
        expression_sync_obj()
    elif cmd == "schema-sync":
        from subcommands.sync.sync_schema import SchemaSync
        # Initialise Command
        schema_sync_obj = SchemaSync(command_argv)
        # Call command
        schema_sync_obj()
    elif cmd == "tool-sync":
        from subcommands.sync.sync_tool import ToolSync
        # Initialise Command
        tool_sync_obj = ToolSync(command_argv)
        # Call command
        tool_sync_obj()
    elif cmd == "workflow-sync":
        from subcommands.sync.sync_workflow import WorkflowSync
        # Initialise Command
        workflow_sync_obj = WorkflowSync(command_argv)
        # Call command
        workflow_sync_obj()

    # Add to project commands --
    elif cmd == "add-tool-to-project":
        from subcommands.updaters.add_tool_to_project import AddToolToProject
        # Initialise command
        tool_add_obj = AddToolToProject(command_argv)
        # Call command
        tool_add_obj()
    elif cmd == "add-workflow-to-project":
        from subcommands.updaters.add_workflow_to_project import AddWorkflowToProject
        # Initialise command
        workflow_add_obj = AddWorkflowToProject(command_argv)
        # Call command
        workflow_add_obj()

    # Add category to 'x' commands
    elif cmd == "add-category-to-tool":
        from subcommands.updaters.add_category_to_tool import AddCategoryToTool
        # Initialise command
        category_add_obj = AddCategoryToTool(command_argv)
        # Call command
        category_add_obj()
    elif cmd == "add-category-to-workflow":
        from subcommands.updaters.add_category_to_workflow import AddCategoryToWorkflow
        # Initialise command
        category_add_obj = AddCategoryToWorkflow(command_argv)
        # Call command
        category_add_obj()

    # Add maintainer commands
    elif cmd == "add-maintainer-to-expression":
        from subcommands.updaters.add_maintainer_to_expression import AddMaintainerToExpression
        # Initialise command
        add_maintainer_obj = AddMaintainerToExpression(command_argv)
        # Call command
        add_maintainer_obj()
    elif cmd == "add-maintainer-to-tool":
        from subcommands.updaters.add_maintainer_to_tool import AddMaintainerToTool
        # Initialise command
        add_maintainer_obj = AddMaintainerToTool(command_argv)
        # Call command
        add_maintainer_obj()
    elif cmd == "add-maintainer-to-workflow":
        from subcommands.updaters.add_maintainer_to_workflow import AddMaintainerToWorkflow
        # Initialise command
        add_maintainer_obj = AddMaintainerToWorkflow(command_argv)
        # Call command
        add_maintainer_obj()

    # Project update command
    elif cmd == "add-linked-project":
        from subcommands.updaters.add_linked_project import LinkProject
        # Initialise command
        link_project_obj = LinkProject(command_argv)
        # Call command
        link_project_obj()

    # Register run instance commands
    elif cmd == "register-tool-run-instance":
        from subcommands.initialisers.run_tool_init import RegisterToolRunInstance
        # Initialise command
        register_tool_run_instance_obj = RegisterToolRunInstance(command_argv)
        # Call command
        register_tool_run_instance_obj()
    elif cmd == "register-workflow-run-instance":
        from subcommands.initialisers.run_workflow_init import RegisterWorkflowRunInstance
        register_workflow_run_instance_obj = RegisterWorkflowRunInstance(command_argv)
        # Call command
        register_workflow_run_instance_obj()
    elif cmd == "get-workflow-step-ids":
        from subcommands.query.get_workflow_step_ids import GetWorkflowStepIDs
        get_workflow_step_ids_obj = GetWorkflowStepIDs(command_argv)
        # Call command
        get_workflow_step_ids_obj()
    # Get run templates
    elif cmd == "copy-tool-submission-template":
        from subcommands.query.copy_tool_submission_template import CopyToolSubmissionTemplate
        copy_tool_submission_template_obj = CopyToolSubmissionTemplate(command_argv)
        # Call command
        copy_tool_submission_template_obj()
    elif cmd == "copy-workflow-submission-template":
        from subcommands.query.copy_workflow_submission_template import CopyWorkflowSubmissionTemplate
        copy_workflow_submission_template_obj = CopyWorkflowSubmissionTemplate(command_argv)
        # Call command
        copy_workflow_submission_template_obj()

    elif cmd == "list-tool-runs":
        from subcommands.listers.list_tool_runs import ListToolRuns
        tool_runs_obj = ListToolRuns(command_argv)
        # Call command
        tool_runs_obj()
    elif cmd == "list-workflow-runs":
        # FIXME
        from subcommands.listers.list_workflow_runs import ListWorkflowRuns
        workflow_runs_obj = ListWorkflowRuns(command_argv)
        # Call command
        workflow_runs_obj()

    elif cmd == "create-tool-submission-template":
        from subcommands.query.create_tool_submission_template import CreateToolSubmissionTemplate
        create_tool_template_obj = CreateToolSubmissionTemplate(command_argv)
        # Call command
        create_tool_template_obj()
    elif cmd == "create-workflow-submission-template":
        from subcommands.query.create_workflow_submission_template import CreateWorkflowSubmissionTemplate
        create_workflow_template_obj = CreateWorkflowSubmissionTemplate(command_argv)
        # Call command
        create_workflow_template_obj()


    # Github actions
    elif cmd == "github-actions-sync-schemas":
        from subcommands.sync.sync_github_actions_schema import SyncGitHubActionsSchema
        # Initialise command
        sync_schemas_obj = SyncGitHubActionsSchema(command_argv)
        # Call command
        sync_schemas_obj()
    elif cmd == "github-actions-sync-expressions":
        from subcommands.sync.sync_github_actions_expression import SyncGitHubActionsExpression
        # Initialise command
        sync_expressions_obj = SyncGitHubActionsExpression(command_argv)
        # Call command
        sync_expressions_obj()
    elif cmd == "github-actions-sync-tools":
        from subcommands.sync.sync_github_actions_tool import SyncGitHubActionsTool
        # Initialise command
        sync_tools_obj = SyncGitHubActionsTool(command_argv)
        # Call command
        sync_tools_obj()
    elif cmd == "github-actions-sync-workflows":
        from subcommands.sync.sync_github_actions_workflow import SyncGitHubActionsWorkflow
        # Initialise command
        sync_workflows_obj = SyncGitHubActionsWorkflow(command_argv)
        # Call command
        sync_workflows_obj()
    elif cmd == "github-actions-create-expression-markdown":
        from subcommands.github_actions.create_expression_markdown_file import CreateExpressionMarkdownFile
        # Initialise command
        create_expression_markdown_obj = CreateExpressionMarkdownFile(command_argv)
        # Call command
        create_expression_markdown_obj()
    elif cmd == "github-actions-create-tool-markdown":
        from subcommands.github_actions.create_tool_markdown_file import CreateToolMarkdownFile
        # Initialise command
        create_tool_markdown_obj = CreateToolMarkdownFile(command_argv)
        # Call command
        create_tool_markdown_obj()
    elif cmd == "github-actions-create-workflow-markdown":
        from subcommands.github_actions.create_workflow_markdown_file import CreateWorkflowMarkdownFile
        # Initialise command
        create_workflow_markdown_obj = CreateWorkflowMarkdownFile(command_argv)
        # Call command
        create_workflow_markdown_obj()
    elif cmd == "github-actions-create-catalogue":
        from subcommands.github_actions.create_catalogue import CreateCatalogue
        # Initialise command
        create_catalogue_obj = CreateCatalogue(command_argv)
        # Call command
        create_catalogue_obj()
    elif cmd == "github-actions-build-workflow-release-asset":
        from subcommands.github_actions.build_workflow_release_assets import BuildWorkflowReleaseAsset
        # Initialise command
        build_release_asset_obj = BuildWorkflowReleaseAsset(command_argv)
        # Call command
        build_release_asset_obj()
    elif cmd == "create-typescript-expression-from-template":
        from subcommands.creators.create_typescript_expression_from_template import CreateTypeScriptExpressionFromTemplate
        # Initialise command
        create_typescript_expression_from_template = CreateTypeScriptExpressionFromTemplate(command_argv)
        # Call Command
        create_typescript_expression_from_template()
    elif cmd == "append-typescript-directory-to-cwl-expression-tool":
        from subcommands.appenders.append_typescript_dir_to_cwl_expression import AppendTypeScriptExpressionDir
        # Initialise command
        append_typescript_expression_dir = AppendTypeScriptExpressionDir(command_argv)
        # Call Command
        append_typescript_expression_dir()
    elif cmd == "append-typescript-directory-to-cwl-commandline-tool":
        from subcommands.appenders.append_typescript_to_tool import AppendTypeScriptToolDir
        # Initialise command
        append_typescript_tool_dir = AppendTypeScriptToolDir(command_argv)
        # Call Command
        append_typescript_tool_dir()
    elif cmd == "append-typescript-directory-to-cwl-workflow":
        from subcommands.appenders.append_typescript_to_workflow import AppendTypeScriptWorkflowDir
        # Initialise command
        append_typescript_workflow_dir = AppendTypeScriptWorkflowDir(command_argv)
        # Call Command
        append_typescript_workflow_dir()
    elif cmd == "create-typescript-interface-from-cwl-schema":
        from subcommands.creators.create_typescript_from_schema import CreateTypeScriptInterfaceFromCWLSchema
        # Initialise command
        create_typescript_interface_from_cwl_schema = CreateTypeScriptInterfaceFromCWLSchema(command_argv)
        # Call Command
        create_typescript_interface_from_cwl_schema()
    elif cmd == "typescript-expression-validate":
        from subcommands.validators.typescript_validate import TypeScriptExpressionDirValidate
        # Initialise command
        typescript_expression_dir_validate = TypeScriptExpressionDirValidate(command_argv)
        # Call Command
        typescript_expression_dir_validate()

    # V2 add-ons
    elif cmd == "icav2-zip-workflow":
        from subcommands.v2.zip_v2_workflow import ZipV2Workflow
        # Initialise command
        zip_v2_workflow = ZipV2Workflow(command_argv)
        # Call Command
        zip_v2_workflow()
    elif cmd == "icav2-deploy-pipeline":
        from subcommands.v2.deploy_to_v2 import DeployV2Workflow
        # Initialise command
        deploy_v2_workflow = DeployV2Workflow(command_argv)
        # Call Command
        deploy_v2_workflow()
    elif cmd == "icav2-launch-pipeline-analysis":
        from subcommands.v2.launch_v2_workflow import LaunchV2Workflow
        # Initialise command
        launch_v2_workflow = LaunchV2Workflow(command_argv)
        # Call Command
        launch_v2_workflow()
    elif cmd == "icav2-list-analysis-steps":
        from subcommands.v2.list_v2_analysis_steps import ICAv2ListAnalysisSteps
        # Initialise command
        list_icav2_analysis_steps = ICAv2ListAnalysisSteps(command_argv)
        # Call Command
        list_icav2_analysis_steps()
    elif cmd == "icav2-get-analysis-step-logs":
        from subcommands.v2.get_v2_step_logs import GetICAv2AnalysisStepLogs
        # Initialise command
        get_icav2_analysis_step_logs = GetICAv2AnalysisStepLogs(command_argv)
        # Call Command
        get_icav2_analysis_step_logs()
    # NotImplemented Error
    else:
        print(__doc__)
        print(f"Could not find cmd \"{cmd}\". Please refer to usage above")
        sys.exit(1)


def main():
    # If only cwl-ica is written, append help s.t help documentation shows
    if len(sys.argv) == 1:
        sys.argv.append('help')
    try:
        _dispatch()
    except KeyboardInterrupt:
        pass
