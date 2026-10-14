# Tech

## Language & Runtime

- **Python** `>= 3.10` (uses `tomllib`, so 3.11+ preferred for the installer).
- Packaged with **setuptools** via `pyproject.toml` (`build-backend = setuptools.build_meta`).
- Distributed as a console script: `cwl-ica = cwl_ica.utils.cli:main`.

## Key Dependencies

- `docopt` — every subcommand's CLI interface is defined by its docstring.
- `cwl_utils` + `cwltool` — parse, validate, and pack CWL. `cwltool` is always pinned to
  the latest version at install time.
- `wrapica` — Illumina ICA API wrapper (v2 integrations).
- `ruamel.*` / `PyYAML`-style handling via `utils/yaml.py` — reads/writes config YAMLs
  with controlled indentation (`YAML_INDENTATION_LEVEL = 4`).
- `PyJWT` — decodes/validates ICA API key tokens.
- `pandas`, `numpy`, `matplotlib`, `pydot` — reporting, catalogue, and graph rendering.
- `mdutils` — markdown help/catalogue generation.
- `deepdiff`, `semantic_version`, `python_dateutil`, `beautifulsoup4`, `in_place`,
  `requests`, `websocket_client`, `verboselogs`.

## Environment / Installation

- Installed into a **conda** environment named `cwl-ica` (plus a second env
  `cwltool-icav1` pinned to `cwltool 3.0.20201203173111` for ICAv1 compatibility).
- Use `./install.sh` (requires `conda >= 4.9.0`, `jq`, and one of `node`/`nodejs`/`docker`,
  plus `rsync`, bash 4+, and `greadlink` on macOS).
  - `-y/--yes` create/update the conda env without prompting.
  - `-s/--skip-yarn-installation` skip the npm/corepack/yarn setup (needed for TypeScript
    expression support).
- The installer performs source substitutions after install:
  - `__VERSION__` in `utils/__version__.py` <- version from `pyproject.toml`.
  - `__LATEST_CWLTOOL_VERSION__` in `utils/globals.py` <- installed `cwltool --version`.

## Important Environment Variables

- `CWL_ICA_REPO_PATH` — path to the cwl-ica git repo the CLI operates on.
- `ICA_BASE_URL` — ICA API base URL (netloc matches `*.platform.illumina.com`).
- `CWL_ICA_DEFAULT_TENANT`, `CWL_ICA_DEFAULT_PROJECT`, `CWL_ICA_DEFAULT_USER` — defaults
  so users can omit `--tenant`, `--project`, `--username`.

## Common Commands

```bash
# Install / update
./install.sh --yes

# Discover commands
cwl-ica help
cwl-ica <command> help          # per-subcommand help via docopt docstring

# Enable debug logging (global flag, must come before the subcommand)
cwl-ica --debug <command> [args]

# Version
cwl-ica version
```

There is no dedicated unit-test runner configured in this repo. Validation of CWL
artifacts is done through the `*-validate` subcommands rather than a pytest suite. Do not
add a test framework unless explicitly requested.

## Autocompletion

- Bash and zsh completions live under `autocompletion/` and are installed into the conda
  prefix's `etc/autocompletions/`. Helper scripts under `autocompletion/helpers/` back
  the dynamic completions. The `.github/workflows/update_auto_completion.yml` workflow
  regenerates them.
