# Migrate `github-actions-build-workflow-release-asset` off icav2-cli-plugins onto direct wrapica calls

The workflow release-asset flow previously shelled out to `icav2-cli-plugins.py` (via `ICAV2_CLI_PLUGINS_HOME`) for pipeline creation, pipeline release, and all five bundle operations. This change replaces every one of those subprocess invocations with direct `wrapica` Python calls, removing the coupling to the plugin binary. Pipeline creation now feeds the already-built local zip (`self.zipped_workflow_path`) straight into `create_cwl_workflow_from_zip`, dropping the redundant GitHub re-download the plugin performed. The five `icav2_gh_helpers.py` bundle helpers keep their names and signatures, so the `icav2_bunch_classes.py` callers are untouched. The wrapica pin stays at `>= 2.48.2` (already present) and the local env was bumped 2.48.1 → 2.48.2.

Watch for: the per-tenant auth now mutates the real `os.environ` instead of a per-subprocess copy, so a token set for one tenant persists in-process after the loop (likely, benign in the single-shot CLI flow). Pipeline creation now sends `workflow_description` and bundle creation now forwards `pipeline_release_url` into wrapica — new behavior the plugin did not expose, worth a sanity check but non-blocking (possible/informational).

**Verdict**: APPROVED

## High-level view

The replacement is one-to-one against real wrapica signatures. `create_cwl_workflow_from_zip`, `release_project_pipeline`, `generate_empty_bundle`, `add_pipeline_to_bundle`, `add_data_to_bundle`, `release_bundle`, and `link_bundle_to_project` all exist in the installed wrapica 2.48.2 with signatures that match the call sites exactly. The follow-up commit fixes a real break: `get_analysis_storage_from_analysis_storage_size` filters on a plain-string `Literal`, so the enum member had to become its `.value` ("Small") or the call would have raised `ValueError` on first run.

Auth is handled the way wrapica expects — `ICAV2_BASE_URL` and `ICAV2_ACCESS_TOKEN` are set in-process per tenant before each wrapica call, mirroring the prior per-subprocess env injection. The one behavioral shift is that these now land in the process-wide `os.environ` rather than a throwaway copy, so values leak across loop iterations. In this single-shot CLI the last-writer-wins behavior is harmless because every call site rewrites the token immediately before use.

The migration respects the task boundaries: only the two in-scope files changed, the curl-based `get_pipeline_code_from_pipeline_id` and the unrelated git/gh subprocess calls are left alone, no `icav2-cli-plugins` strings survive in the migrated paths, and the five bundle helper signatures are preserved so no caller needed to change.

<details>
<summary>Issues (2)</summary>

1. **Process-wide env mutation across tenants** — the auth env vars are written to the real `os.environ` (not a copied dict) inside the per-tenant loop, so a tenant's token persists in-process after its iteration. Non-blocking in the current single-shot flow since each call rewrites the token immediately before use; worth a comment if these helpers are ever reused in a long-lived or concurrent context.
2. **New fields forwarded to wrapica** — `workflow_description` (pipeline) and `pipeline_release_url` (bundle) are now sent to ICA where the plugin path did not expose them. Confirm ICA accepts these on create; both are optional wrapica params so this is informational, not blocking.

</details>

<details>
<summary>Details</summary>

### wrapica signatures match the call sites

A narrow signature spot-check against the installed wrapica confirmed version 2.48.2 and the exact shapes used:

```
create_cwl_workflow_from_zip(project_id, pipeline_code: str, zip_path: Path,
    analysis_storage=None, workflow_description=None, ...)
release_project_pipeline(project_id, pipeline_id)
get_analysis_storage_from_analysis_storage_size(project_id,
    analysis_storage_size: Literal['Small','Medium','Large','XLarge','2XLarge','3XLarge'])
generate_empty_bundle(bundle_name, bundle_version, short_description, version_comment,
    region_id=None, categories=None, pipeline_release_url=None) -> Bundle
add_pipeline_to_bundle(bundle_id, pipeline_id) -> bool
add_data_to_bundle(bundle_id, data_id) -> bool
release_bundle(bundle_id)
link_bundle_to_project(project_id, bundle_id)
```

Each wrapica call in the diff lines up: `create_cwl_workflow_from_zip(project_id=pipeline_project_id, pipeline_code=pipeline_code, zip_path=self.zipped_workflow_path, analysis_storage=..., workflow_description=...)`, `release_project_pipeline(pipeline_project_id, pipeline_id)`, and the five bundle helpers forwarding positional ids plus `generate_empty_bundle(...)` by keyword. `pipeline_obj.id` and `bundle_obj.id` are read off the returned objects, matching the `ProjectPipelineV4` / `Bundle` return types.

### The analysis-storage fix is a genuine bug catch

The first commit passed the bare enum member `AnalysisStorageSize.SMALL` into `get_analysis_storage_from_analysis_storage_size`. That resolver's parameter is typed `Literal['Small', ...]` and it filters storage options by `name == analysis_storage_size`, where `name` is a plain string. Since `AnalysisStorageSize` is not a `str` subclass, `'Small' == AnalysisStorageSize.SMALL` is `False`, the filter matches nothing, and the call raises before any pipeline is created. The follow-up commit passes `AnalysisStorageSize.SMALL.value` ("Small"), which the `Literal` and the function docstring expect. Behavior is unchanged (Small storage, the plugin's implicit default) and the fix was verified directly against the installed wrapica.

### Local zip used, GitHub re-download dropped

The plugin's `create-cwl-pipeline-from-github-release` downloaded the release zip via `gh` before calling wrapica. This caller already produced the zip at `self.zipped_workflow_path`, so the migration feeds that path directly to `create_cwl_workflow_from_zip` and the download disappears. `pipeline_code` is derived as `self.zipped_workflow_path.stem.replace(".", "_")`, matching the plugin's `zip_stem.replace(".", "_")` convention and respecting ICA's no-dots rule for pipeline codes.

### Auth env handling and the process-wide mutation

Previously each subprocess got `ICAV2_BASE_URL` / `ICAV2_PROJECT_ID` / `ICAV2_ACCESS_TOKEN` through a copied `proc_environ` dict passed to `run_subprocess_proc`. The migration sets `ICAV2_BASE_URL` and `ICAV2_ACCESS_TOKEN` directly on `os.environ` before each wrapica call, since that is how wrapica authenticates in-process (consistent with the v2 subcommands documented in the investigation). `ICAV2_PROJECT_ID` is correctly dropped — wrapica takes `project_id` as a function argument.

The behavioral difference is scope: the old copy was discarded when the subprocess exited, whereas these writes persist in the parent process. A token set for tenant A survives into tenant B's iteration until overwritten. Because every call site rewrites `ICAV2_ACCESS_TOKEN` immediately before the wrapica call, the effective value is always correct at the point of use. It would become a hazard only if these helpers were called concurrently or interleaved with code that reads the env without first setting it.

### Bundle helper signatures preserved

The five helpers in `icav2_gh_helpers.py` keep their exact parameter lists, including the `icav2_access_token` argument (now consumed to set the env var rather than injected into a subprocess) and `generate_empty_bundle`'s pre-existing `pipeline_release_url`. `icav2_bunch_classes.py` is not in the diff; its call at line 1060 still passes `region_id=self.bundle_region_id` and `pipeline_release_url=self.pipeline_release_url`, which the unchanged signature accepts. One behavioral change: `generate_empty_bundle` now forwards `pipeline_release_url` into wrapica, where the old plugin `bundles init` invocation had no such flag and silently ignored it. wrapica accepts it as an optional param, so this sends release-url metadata to ICA that the plugin path never did — confirm ICA accepts it on create.

### Scope discipline

Only `build_workflow_release_assets.py` and `icav2_gh_helpers.py` changed. The curl-based `get_pipeline_code_from_pipeline_id` is untouched (and the investigation explicitly left it out of scope), with `json` and `run_subprocess_proc` imports retained because that path and the git/gh calls still use them. The dropped `JSONDecodeError` import was the only casualty, correct since its sole use was the deleted stdout-parsing block. A grep over the migrated files found no remaining `ICAV2_CLI_PLUGINS_HOME`, `icav2-cli-plugins`, `create-cwl-pipeline-from-github-release`, or `bundles init` strings.

### Verification evidence

The implementer recorded in the commit messages: wrapica 2.48.2 installed; `'Small' == AnalysisStorageSize.SMALL` is False while `== .value` is True; `ast.parse` clean on both files; all eight wrapica functions resolve with matching signatures; grep confirms no plugin strings remain. The only gap they noted is that a full package import could not run because the import chain pulls in the unrelated ICAv1 `libica.openapi.libwes` module (present on main, not installed in this environment) — not introduced by this change and not exercising any live ICA call. This review independently re-ran the signature spot-check and confirmed 2.48.2 and all eight signatures.

### Test coverage

This repo has no unit-test suite by design; validation is import-level plus signature checks. No live ICA API round-trip was exercised, so the actual create/release/bundle calls against ICA are unverified at runtime. Not tested: end-to-end pipeline creation and bundle assembly against a real tenant, and whether ICA accepts the newly forwarded `workflow_description` / `pipeline_release_url` values. These require a live ICA environment and are out of reach here.

</details>

<details>
<summary>File map</summary>

- `src/cwl_ica/subcommands/github_actions/build_workflow_release_assets.py` — swapped the two plugin subprocess blocks in `create_and_commit_v2_bundles()` for `create_cwl_workflow_from_zip` + `release_project_pipeline`; added the `# Wrapica` import block; set auth env in-process per tenant; derived `pipeline_code` from the local zip stem; removed the unused `JSONDecodeError` import.
- `src/cwl_ica/utils/icav2_gh_helpers.py` — rewrote `add_pipeline_to_bundle`, `generate_empty_bundle`, `add_data_to_bundle`, `release_bundle`, `add_bundle_to_project` to call the `wrapica.bundle` equivalents (imported under `wrapica_*` aliases); names/signatures unchanged; curl-based `get_pipeline_code_from_pipeline_id` untouched.
- `pyproject.toml` — unchanged; wrapica pin already `>= 2.48.2`.

Full diff: `git -C /home/alexiswl/GitHub/UMCCR/cwl-ica-cli/.worktrees/icav2-to-wrapica diff main...icav2-to-wrapica`

</details>
