# Structure

## Repository Layout

```
cwl-ica-cli/
├── pyproject.toml              # Package metadata, deps, console-script entrypoint
├── install.sh                  # Conda-based installer (+ version/cwltool substitution)
├── cwl-ica-conda-env.yaml      # Main conda env spec (cwl-ica)
├── cwltool-icav1-conda-env.yaml# Secondary env pinned for ICAv1 cwltool
├── Dockerfile
├── autocompletion/             # bash/zsh completions + dynamic helper scripts
│   ├── bash/  zsh/  helpers/  templates/  run-autocompletion.sh
├── scripts/                    # Extra installed scripts (TypeScript expression tooling)
├── .github/                    # Actions: build-release, autocompletion, release assets
└── src/cwl_ica/                # The Python package
    ├── utils/                  # Cross-cutting helpers and the CLI dispatcher
    ├── classes/                # Domain object model
    └── subcommands/            # One module per CLI command, grouped by verb
```

## Package: `src/cwl_ica`

### `utils/` — cross-cutting helpers

- `cli.py` — **the entrypoint**. A single docopt docstring lists every command; `_dispatch()`
  is a large `if/elif` that lazily imports the matching subcommand class and calls it.
  `main()` is the console-script target.
- `globals.py` — constants, regexes, enums, ICA compute-size/container mappings, and the
  `__LATEST_CWLTOOL_VERSION__` placeholder.
- `__version__.py` — holds the `__VERSION__` placeholder replaced at install time.
- `logging.py` — `get_logger()` / `set_basic_logger()`; import a module-level `logger`.
- `repo.py` — resolve paths inside `CWL_ICA_REPO_PATH` (e.g. `get_tools_dir()`).
- `yaml.py`, `errors.py`, `miscell.py`, `project.py`, `conda.py`, `subprocess_handler.py`,
  `ica_utils.py`, `gh_helpers.py` — focused helpers by concern.
- `cwl_*_helper_utils.py`, `typescript_helpers.py`, `*_markdown_utils.py`, `pydot_utils.py`,
  `input_template_utils.py` — CWL parsing, TypeScript, markdown, graphing, templating.
- `icav2_*` — v2/ICAv2-specific helpers.

### `classes/` — domain model

- `command.py` — **`Command` base class** all subcommands inherit from. It parses argv with
  docopt against the subclass `__doc__`, exposes `_help()`, `check_length()`, and requires
  subclasses to implement `check_args()`.
- CWL artifacts: `cwl.py`, `cwl_expression.py`, `cwl_schema.py`, `cwl_tool.py`,
  `cwl_workflow.py`.
- Registry items: `item*.py`, `item_version*.py` (expression/schema/tool variants).
- ICA objects: `ica_workflow*.py`, `ica_task_run.py`, `project.py`-adjacent classes,
  `icav2_bunch_classes.py`, `dockstore.py`.

### `subcommands/` — one file per command, grouped by verb

Groupings mirror the command families in `cli.py`:

- `configure/` — configure-repo / -tenant / -user
- `initialisers/` — project/category init, expression/schema/tool/workflow init, run inits
- `creators/` — create-*-from-template, workflow-release, typescript creators
- `validators/` — *-validate, validate-config-yamls, validate-api-key-script
- `sync/` — *-sync and github-actions-sync-*
- `updaters/` — set-default-*, add-*-to-project, add-category/maintainer, typescript update
- `listers/` — list-*
- `query/` — get-workflow-step-ids, create/copy submission templates
- `appenders/` — append typescript directory to expression/tool/workflow
- `github_actions/` — markdown/catalogue/release-asset builders for CI
- `ica/` — ICA API interaction helpers
- `v2/` — ICAv2 integrations (add tenant/project/dataset/bunch, zip workflow)

Each group's `__init__.py` may define a shared intermediate base class (e.g.
`CreateFromTemplate`) that subcommands extend.

## Conventions

- **Files** start with `#!/usr/bin/env python3` and a module docstring.
- **Imports** are grouped and commented: `# External imports`, `# Utils`, `# Classes`,
  `# Locals`, followed by `logger = get_logger()`.
- **Every subcommand is a class** extending `Command` (often via a group base class). The
  class docstring **is** the CLI spec: `Usage:`, `Description:`, `Options:`,
  `EnvironmentVariables:`, `Example`. docopt parses it — keep the format exact.
- **`__init__`** calls `super().__init__()`, then `check_length()`, then `_help()` if
  `--help`, then `check_args()` inside a `try/except ArgumentError: self._help(fail=True)`.
- **`__call__`** performs the work (usually delegating to `super().__call__()` plus logging).
- **`check_args`** validates/normalizes args, raising `CheckArgumentError` (from
  `utils/errors.py`) on failure and setting instance attributes.
- **Adding a new command** requires two changes: create the subcommand module under the
  right `subcommands/<group>/` folder, and register it in both the docstring and the
  `if/elif` chain in `utils/cli.py`. Consider updating autocompletion helpers too.
- **Naming**: command names are kebab-case (`create-tool-from-template`); classes are
  PascalCase (`CreateToolFromTemplate`); options are `--kebab-case`.
- **CLI args** are validated for shell-safety and version format via base-class helpers
  (`check_shlex_arg`, `check_conformance`, `check_shlex_version_arg`).
