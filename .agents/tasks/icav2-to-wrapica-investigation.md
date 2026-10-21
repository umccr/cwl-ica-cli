# Can `github-actions-build-workflow-release-asset` drop the `icav2` binary in favour of `wrapica`?

> Investigation only. No code was changed. All claims cite file paths and line numbers that were read directly.
> Content was rephrased for compliance with licensing restrictions where external/plugin source is summarised.

## Summary verdict

**Yes — the `icav2` binary dependency can be removed from this subcommand and replaced by direct `wrapica` calls, with one caveat that is already a non-issue.**

Every `icav2` invocation this subcommand makes is actually a call to `icav2-cli-plugins.py` (the `icav2-cli-plugins` Python entrypoint), not the Go `icav2` binary. Each of those plugin commands is a thin wrapper that, under the hood, calls a single public `wrapica` function. All seven required `wrapica` functions exist and are exported in the `wrapica` version already pinned by cwl-ica-cli.

The only plugin step that does non-trivial orchestration beyond a wrapica call is `projectpipelines create-cwl-pipeline-from-github-release`, which (a) downloads the release zip from GitHub via the `gh` binary and (b) then calls one wrapica function. But this subcommand **already builds the workflow zip locally** (`self.zipped_workflow_path`), so the download step is redundant here — the wrapica call can be fed the local zip directly. That removes the only orchestration concern.

cwl-ica-cli already depends on and imports `wrapica` in several modules, so this is an extension of an existing dependency, not a new one.

### What remains blocking: nothing hard
- The replacement needs a `pipeline_code` (the plugin derives it as `zip_stem.replace(".", "_")`) and an analysis-storage object (plugin default = `Small`). Both are trivial to supply.
- `gh`/`git`/`curl` subprocess calls remain in the subcommand, but those are **not** the `icav2` binary and are out of scope for this question.

---

## 1. Every `icav2` call made by the subcommand

The subcommand file is `src/cwl_ica/subcommands/github_actions/build_workflow_release_assets.py`. It never calls a bare `icav2` binary; it builds command lists that invoke the plugin's Python entrypoint:

```
f"{os.environ['ICAV2_CLI_PLUGINS_HOME']}/pyenv/bin/python",
f"{os.environ['ICAV2_CLI_PLUGINS_HOME']}/pyenv/bin/icav2-cli-plugins.py",
...
```

All are executed through `run_subprocess_proc` (imported at `build_workflow_release_assets.py:78` from `utils/subprocess_handler.py`), with per-tenant env (`ICAV2_BASE_URL`, `ICAV2_PROJECT_ID`, `ICAV2_ACCESS_TOKEN`) injected via `os.environ.copy()`.

### Direct in the subcommand — `create_and_commit_v2_bundles()` (`build_workflow_release_assets.py:1189`)
| # | Plugin command | Where built | Args | Output consumed |
|---|----------------|-------------|------|-----------------|
| 1 | `projectpipelines create-cwl-pipeline-from-github-release` | lines 1231–1238 | `self.release_url`, `--json` | stdout parsed as JSON; reads `pipeline_id` (lines 1297–1309) |
| 2 | `projectpipelines release <pipeline_id>` | lines 1240–1246 (+ `[pipeline_id]` at 1313) | `pipeline_id` | returncode only (lines 1315–1328) |

### Indirect — via `classes/icav2_bunch_classes.py` → `utils/icav2_gh_helpers.py`
The subcommand calls `latest_bunch_version.generate_bundle_from_bunch_version(...)` (`build_workflow_release_assets.py:1349`). That flows into `Bundle.create_bundle_from_bunch_version()` (`icav2_bunch_classes.py:1057`), which calls these `icav2_gh_helpers.py` functions, each of which shells out to the plugin:

| # | Helper (file:line) | Plugin command | Args |
|---|--------------------|----------------|------|
| 3 | `generate_empty_bundle` (`icav2_gh_helpers.py:522`) | `bundles init` | `<name> --short-description --bundle-version --bundle-version-description --json [--category ...]`; stdout JSON `id` consumed |
| 4 | `add_pipeline_to_bundle` (`icav2_gh_helpers.py:471`) | `bundles add-pipeline` | `<bundle_id> --pipeline <pipeline_id>` |
| 5 | `add_data_to_bundle` (`icav2_gh_helpers.py:561`) | `bundles add-data` | `<bundle_id> --data <data_id>` |
| 6 | `release_bundle` (`icav2_gh_helpers.py:607`) | `bundles release` | `<bundle_id>` |
| 7 | `add_bundle_to_project` (`icav2_gh_helpers.py:647`) | `bundles add-bundle-to-project` | `<bundle_id> --project <project_id>` |

**Non-`icav2` subprocess calls in the same code paths (out of scope, do not block removal):**
- `get_pipeline_code_from_pipeline_id` (`icav2_gh_helpers.py:681`) uses a `curl` call to the ICA REST API, not the plugin. (This is replaceable by wrapica `get_pipeline_obj_from_pipeline_id`, see note below, but it is not an `icav2` binary call.)
- `git` and `gh` calls throughout `__call__` — unrelated to the `icav2` binary.

---

## 2. What each plugin command does under the hood (wrapica usage)

Source read under `/home/alexiswl/GitHub/UMCCR/icav2-cli-plugins/src/icav2_cli_plugins/subcommands/`.

| Plugin command | Plugin file (`__call__` line) | Underlying `wrapica` call | wrapica import site |
|----------------|------------------------------|---------------------------|---------------------|
| `create-cwl-pipeline-from-github-release` | `projectpipelines/create_cwl_pipeline_from_github_release.py:113` | `create_cwl_workflow_from_zip(project_id, pipeline_code, zip_path, workflow_description)` at line 141 — **but first** downloads the zip via `gh release download` (`utils/gh_helpers.py:24`) | `from wrapica.project_pipelines import create_cwl_workflow_from_zip` (line 22–26) |
| `projectpipelines release` | `projectpipelines/release_pipeline.py:69` | `release_project_pipeline(project_id, pipeline_id)` (one line) | `from wrapica.project_pipelines import release_project_pipeline` (line 11–14) |
| `bundles init` | `bundles/bundles_init.py:170` | `generate_empty_bundle(name, version, short_description, version_comment, region_id, categories)` + optional `add_pipeline_to_bundle` / `add_data_to_bundle` loops | `from wrapica.bundle import generate_empty_bundle, add_pipeline_to_bundle, add_data_to_bundle, ...` (line 14–20) |
| `bundles add-pipeline` | `bundles/bundles_add_pipeline.py:84` | `add_pipeline_to_bundle(bundle_id, pipeline_id)` loop | `from wrapica.bundle import add_pipeline_to_bundle` (line 11–14) |
| `bundles add-data` | `bundles/bundles_add_data.py:95` | `add_data_to_bundle(bundle_id, data_id)` loop | `from wrapica.bundle import add_data_to_bundle` (line 14–17) |
| `bundles release` | `bundles/bundles_release.py:57` | `release_bundle(bundle_id)` (one line) | `from wrapica.bundle import release_bundle` (line 12) |
| `bundles add-bundle-to-project` | `bundles/bundles_add_to_project.py:96` | `link_bundle_to_project(project_id, bundle_id)` loop | `from wrapica.bundle import link_bundle_to_project` (line 10–13) |

The plugin commands' `check_args` methods do argument resolution (e.g. turning a bundle id string into a `Bundle` object, resolving project/pipeline objects), which is also backed by wrapica getters (e.g. `get_bundle_obj_from_bundle_id`, `get_pipeline_obj_from_pipeline_id`). cwl-ica-cli already holds raw IDs, so most of that resolution is unnecessary.

`icav2-cli-plugins` pins `wrapica >= 2.48.2, < 2.49.0` (`icav2-cli-plugins/pyproject.toml`), the same minor line cwl-ica-cli uses — so the two agree on the wrapica API surface.

---

## 3. Does cwl-ica-cli already use wrapica? Versions?

**Yes, extensively.** Confirmed imports (excluding `build/lib/` artifacts):
- `utils/icav2_gh_helpers.py:20-29` — `from wrapica.data import Data`; `from wrapica.project_data import ProjectData, find_project_data_bulk, convert_icav2_uri_to_data_obj, get_project_data_obj_by_id, is_data_id_format`; `from wrapica.enums import DataType`.
- `classes/icav2_bunch_classes.py:19-22` — `from wrapica.user import get_user_name_from_user_id`; `from wrapica.project_data import get_project_data_obj_by_id, find_project_data_bulk`; `from wrapica.region import get_region_obj_from_project_id`; `from wrapica.enums import DataType`.
- `subcommands/v2/icav2_add_dataset.py:22-23`, `subcommands/v2/icav2_add_bunch.py:17` — further `wrapica` imports.

**Version pins:**
- cwl-ica-cli `pyproject.toml`: `wrapica >= 2.48.2` (no upper bound).
- icav2-cli-plugins `pyproject.toml`: `wrapica >= 2.48.2, < 2.49.0`.
- Installed locally: `wrapica-2.48.1` at `/home/alexiswl/miniconda3/lib/python3.12/site-packages/wrapica` (one patch below the pin; all required functions present — see §4 verification).

---

## 4. Per-call verdicts

All target functions were confirmed exported in the installed wrapica:
- `wrapica/bundle/__init__.py` exports `generate_empty_bundle`, `add_pipeline_to_bundle`, `add_data_to_bundle`, `release_bundle`, `link_bundle_to_project` (lines 12–53).
- `wrapica/project_pipelines/__init__.py` exports `release_project_pipeline`, `create_cwl_workflow_from_zip` (lines 82–169).
- `create_cwl_workflow_from_zip` signature verified at `wrapica/project_pipelines/functions/project_pipelines_functions.py:2115` (params: `project_id`, `pipeline_code`, `zip_path`, optional `analysis_storage`, `workflow_description`, ...).

| icav2 call | Verdict | wrapica replacement (rough shape) | Notes |
|------------|---------|-----------------------------------|-------|
| `create-cwl-pipeline-from-github-release` | **CAN** | `create_cwl_workflow_from_zip(project_id=<pipeline_project_id>, pipeline_code=<zip_stem.replace('.','_')>, zip_path=self.zipped_workflow_path, workflow_description=f"GitHub Release URL: {self.release_url}")` → use returned `pipeline.id` | The plugin's extra work (download zip from GitHub via `gh`) is redundant here because the subcommand already produced the zip locally. Supply `project_id` from `get_project_id_from_project_name(...)` as is done today; default analysis storage = `Small`. |
| `projectpipelines release` | **CAN** | `release_project_pipeline(project_id, pipeline_id)` | Direct one-to-one. |
| `bundles init` | **CAN** | `generate_empty_bundle(bundle_name, bundle_version, short_description=..., version_comment=..., region_id=..., categories=[...])` → `.id` | Needs a `region_id`; cwl-ica-cli already resolves regions via `wrapica.region.get_region_obj_from_project_id` (`icav2_bunch_classes.py:21`). |
| `bundles add-pipeline` | **CAN** | `add_pipeline_to_bundle(bundle_id, pipeline_id)` | Direct one-to-one. |
| `bundles add-data` | **CAN** | `add_data_to_bundle(bundle_id, data_id)` | Direct one-to-one; loop over data ids as today. |
| `bundles release` | **CAN** | `release_bundle(bundle_id)` | Direct one-to-one. |
| `bundles add-bundle-to-project` | **CAN** | `link_bundle_to_project(project_id, bundle_id)` | Direct one-to-one. |
| (`get_pipeline_code_from_pipeline_id`, curl — not icav2) | CAN (optional) | `get_pipeline_obj_from_pipeline_id(pipeline_id).code` (`wrapica.pipelines`) | Not an `icav2` binary call; replacing it just removes a `curl` call. |

---

## 5. Overall conclusion & recommendation

**The `icav2` binary (i.e. `icav2-cli-plugins.py`) dependency can be fully removed from `build_workflow_release_assets.py` and its two helper modules, replaced entirely by `wrapica` calls that cwl-ica-cli is already set up to make.**

Concretely, replace:
1. The two subprocess blocks in `create_and_commit_v2_bundles()` (`build_workflow_release_assets.py:1231–1328`) with direct `create_cwl_workflow_from_zip(...)` and `release_project_pipeline(...)` calls. Because the zip is already local, drop the GitHub re-download entirely.
2. The five plugin-shelling helpers in `icav2_gh_helpers.py` (`generate_empty_bundle` :522, `add_pipeline_to_bundle` :471, `add_data_to_bundle` :561, `release_bundle` :607, `add_bundle_to_project` :647) with their `wrapica.bundle` equivalents. Keep the same function names/signatures so `Bundle.create_bundle_from_bunch_version()` (`icav2_bunch_classes.py:1057`) needs no change.

Supporting points to carry into implementation:
- Set `ICAV2_BASE_URL` / `ICAV2_ACCESS_TOKEN` for wrapica the way wrapica expects (env or its config) instead of per-subprocess env injection; today the subcommand already computes these per tenant (`get_tenant_access_token`, `ICAV2_DEFAULT_BASE_URL`).
- Supply `pipeline_code` and the `Small` analysis-storage default that the plugin currently fills in implicitly.
- Optionally also drop the `curl` call in `get_pipeline_code_from_pipeline_id` in favour of `wrapica.pipelines.get_pipeline_obj_from_pipeline_id(...).code` — not required for removing the `icav2` dependency, but it tidies another external process call.

**Nothing in these flows requires logic that lives only inside `icav2-cli-plugins`.** The plugins add argument parsing, object resolution from strings, and (for one command) a GitHub download that this caller does not need. Removing the dependency reduces install surface (`ICAV2_CLI_PLUGINS_HOME`, the `cwltool-icav1`-style separate env) and removes coupling to a plugin repo that the user describes as being in flux.

### Authentication mechanism (resolved)
wrapica in cwl-ica-cli authenticates via environment variables: existing v2 subcommands document `ICAV2_ACCESS_TOKEN` (required) and `ICAV2_BASE_URL` (optional) — see `subcommands/v2/icav2_add_dataset.py:127-128` and `subcommands/v2/icav2_add_bunch.py:148-149`. These are exactly the values the subcommand already computes per tenant today (`get_tenant_access_token`, `ICAV2_DEFAULT_BASE_URL`). So the migration can set those env vars (or wrapica's config) per tenant before the wrapica calls, mirroring the current per-subprocess env injection — no new auth plumbing required. `project_id` is passed directly as a function argument.

### NEEDS-MORE-INFO
- Installed wrapica is 2.48.1 locally while the pin is `>= 2.48.2`; confirm the CI/runtime environment resolves to a `>= 2.48.2` build. The required function names are present in 2.48.1, so this is a pin-hygiene check, not a blocker.
