# Drop ICAv2 bundle generation from workflow release, keep pipeline create/release

Removes ICAv2 bundle generation from the `github-actions-build-workflow-release-asset` step while leaving pipeline creation and release intact. The bundle generation path was failing at runtime now that all production reference data is external (`NotFoundException` on `add_data_to_bundle`). The former `create_and_commit_v2_bundles` method is renamed to `create_and_release_v2_pipelines`, its bundle-generation / config-YAML-write / commit portion excised, and the markdown report now surfaces a per-tenant/per-project Pipelines section with a standard shareable pipeline link instead of the old Bundles section. The change is confined to a single file.

Watch for: nothing blocking. The pipeline create/release loop is preserved byte-for-byte (confirmed), the markdown link format matches the task exactly (confirmed), and all dead attributes/imports are removed without touching out-of-scope modules (confirmed).

**Verdict**: APPROVED

## High-level view

The bundle removal is surgical. The renamed method keeps the entire tenant/project pipeline loop — bunch discovery, project-name derivation, existence check, create-from-zip, release, and population of `self.pipeline_ids_by_project_by_tenant` — and simply drops everything after it: the `for bunch in bunches_filtered` bundle-generation loop, the `bundles:` write into the icav2 config YAML, and the git add/diff/commit sequence for that config. The bunch read at the top of the method is retained because it still drives which tenants/projects the pipeline is registered into, which the updated docstring now explains accurately.

The markdown report swaps the per-tenant "Bundles Generated" section for a "Pipelines Generated" section driven by `self.pipeline_ids_by_project_by_tenant` (tenant → project_id → pipeline_id). Each pipeline renders id, name+version (resolved via `get_pipeline_name_version_from_pipeline_id`), project id and name (via `get_project_name_from_project_id`), and a markdown pipeline link. The link uses the literal UI host `https://ica.illumina.com/ica/projects/{project_id}/pipelines/{pipeline_id}`, matching the task's required format exactly.

Dead code cleanup is tight and verified. The three bundle attributes, the `Bundle`/`BunchVersion` imports, `CommentedSeq`, and the three icav2-config-YAML write helpers (`write_config_yaml`, `get_icav2_config_yaml_path`) are all removed, while `Bunch`, `read_config_yaml`, `YAML`, and `sleep` are retained because they still have genuine uses. The docstring, the `__call__` step comment, the `update_release_description` comment, and the `ICAV2_ACCESS_TOKEN_<TENANT_NAME>` env-var help all have their bundle wording dropped. No other files are touched; `classes/icav2_bunch_classes.py` and `subcommands/v2/` are untouched, and committed `bundles:` config entries are left alone.

<details>
<summary>Issues (0)</summary>

No blocking or non-blocking action items. One informational note is captured in the details below regarding the pipeline link host overlapping the REST base-URL constant; the literal host is the correct choice here and requires no change.

</details>

<details>
<summary>Details</summary>

### Pipeline loop preserved, bundle tail excised

The kept loop is identical to the original pipeline path (confirmed by reading HEAD lines 1171–1300): it reads bunches from the icav2 config, filters to those whose `pipeline_path` matches the current workflow, derives tenants and per-tenant pipeline project names, and for each project checks existence via `get_project_pipeline_obj_from_pipeline_name`, falls back to `create_cwl_workflow_from_zip`, releases via `release_project_pipeline` when not already `RELEASED`, and records the id in `pipeline_ids_by_project_by_tenant[tenant_name][pipeline_project_id]`. The method ends at `self.pipeline_ids_by_project_by_tenant = pipeline_ids_by_project_by_tenant` — everything that followed (the `bundle_objs` loop calling `generate_bundle_from_bunch_version`, the `icav2_bundles_by_tenant_by_project` population, the `config_yaml_obj["bundles"]` write via `CommentedSeq`, and the git add/diff/commit block) is gone. Grep confirms zero remaining references to `generate_bundle_from_bunch_version`, `add_data_to_bundle`, `self.bundle_objs`, `self.icav2_bundles_by_tenant`, or a `"bundles"` write (confirmed).

The `__call__` call site was updated to `self.create_and_release_v2_pipelines()` with the step comment changed from "Generate bundles for icav2" to "Create and release icav2 pipeline(s)" (confirmed at line 277).

### Markdown Pipelines section and link format

The report section iterates `self.pipeline_ids_by_project_by_tenant.items()` (tenant → dict) and then `pipeline_ids_by_project.items()` (project_id → pipeline_id), resolving name/version through `get_pipeline_name_version_from_pipeline_id(pipeline_id, get_tenant_access_token(tenant_name))` and project name through `get_project_name_from_project_id(tenant_name, pipeline_project_id)`. The rendered order — pipeline id, name, version, project id, project name, then the link — matches the task's stated fields. The link is built as:

```python
pipeline_url = (
    f"https://ica.illumina.com/ica/projects/{pipeline_project_id}/pipelines/{pipeline_id}"
)
```

which is exactly the required `https://ica.illumina.com/ica/projects/{project_id}/pipelines/{pipeline_id}` (confirmed). The `if self.pipeline_ids_by_project_by_tenant is None` guard is preserved, so a workflow with no configured bunches still produces a report without the ICAv2 section.

On the base-URL constant: `ICAV2_DEFAULT_BASE_URL` is `https://ica.illumina.com/ica/rest` (confirmed in `utils/globals.py:221`), i.e. the REST API base, not the UI host. The pipeline link needs `https://ica.illumina.com/ica/projects/...`, whose path diverges after the shared host, so composing from the constant would be awkward and the literal host is the appropriate choice — consistent with the task's "literal host is fine" fallback and the existing pattern in `classes/icav2_bunch_classes.py`. The coder flagged this correctly in the commit message. Informational only, no action needed.

### Dead code and import cleanup

Removed attributes `self.bundle_tenants`, `self.bundle_objs`, and `self.icav2_bundles_by_tenant` and their `# ICAv2 assets` comment block; grep confirms no remaining references (confirmed). Removed imports `CommentedSeq`, `Bundle`, `BunchVersion`, `write_config_yaml`, and `get_icav2_config_yaml_path`, all of which had no remaining use after the bundle tail was cut (confirmed zero occurrences). Retained imports verified as still used: `read_config_yaml` (bunch read in the kept method), `Bunch` (`Bunch.from_dict`), `YAML` (three `YAML()` constructions in unrelated methods), and `sleep` (two `sleep(3)` calls in other methods, distinct from the one removed with the bundle commit block). `get_project_id_from_project_name` stays because the kept loop still calls it (confirmed at line 1263).

### Docstring and comment accuracy

All "bundle" wording is gone from the file (grep returns none). The method docstring now describes creating/releasing one pipeline per project-name per tenant and explains that bunches are read only to determine registration targets. The `ICAV2_ACCESS_TOKEN_<TENANT_NAME>` env-var help changed from "generate pipelines / bundles" to "generate pipelines", the `__call__` summary bullet from "generates pipelines and bundles (separate PR)" to "Create and release the v2 pipeline(s)...", and the `update_release_description` comment from "bundle objects" to "pipeline objects".

### Scope containment

Only `src/cwl_ica/subcommands/github_actions/build_workflow_release_assets.py` is in the diff (confirmed via `--name-only`). `classes/icav2_bunch_classes.py` and `subcommands/v2/` are not touched (confirmed). Committed `bundles:` entries in config YAMLs are left in place — the change only stops appending.

### Verification (from commit messages, not re-run)

The coder recorded, under the conda env python 3.14 with the worktree src on `PYTHONPATH`: `ast.parse` OK, `py_compile` OK, module import OK (no `ImportError`/`NameError`), grep confirming removed symbols absent and `pipeline_ids_by_project_by_tenant` still populated and consumed, and `__pycache__` cleanup. The live end-to-end release run was not performed (needs prod ICA tokens), consistent with the task. The static/grep facts above were independently re-confirmed in this review via `git show` of HEAD.

</details>

<details>
<summary>File map</summary>

- `src/cwl_ica/subcommands/github_actions/build_workflow_release_assets.py` — renamed `create_and_commit_v2_bundles` → `create_and_release_v2_pipelines` and removed the bundle-generation / config-YAML-write / commit tail; replaced the markdown Bundles section with a Pipelines section using the standard pipeline link; removed dead bundle attributes and unused imports; updated docstring, `__call__` comment, release-description comment, and env-var help to drop bundle wording.

Full diff: `git -C .worktrees/remove-icav2-bundles diff main...HEAD`

</details>
