# Review: fix-zip-workflow-schemas

## Verdict: APPROVED

## Scope reviewed
- Diff: `git diff main...HEAD` on worktree `fix-zip-workflow-schemas` (1 file, +24/-2).
- Only changed file: `src/cwl_ica/utils/cwl_workflow_helper_utils.py` (`zip_workflow`).
- Cross-checked helpers: `cwl_schema_helper_utils.get_schemas`,
  `add_additional_schemas_to_schema_list_recursively`, `check_dict_field_type_for_imports`,
  `repo.join_run_path_from_caller_path`, `cwl_helper_utils.get_path_from_cwl_id`,
  `collect_objects_by_print_deps` and its recursive location collector.

## Approach conformance
The chosen fix approach is implemented exactly:
- Schemas are resolved directly from the parsed CWL object via `get_schemas(cwl_obj)`,
  each relative path joined with `join_run_path_from_caller_path(cwl_obj.cwl_file_path, ...)`,
  then expanded transitively with `add_additional_schemas_to_schema_list_recursively(...)`.
  This matches the established pattern already used by `get_schema_mappings`.
- `collect_objects_by_print_deps(...)` is unchanged; its result is only augmented with
  schema paths not already present.
- The relative-path temp-dir layout is preserved
  (`output_tempdir / path.relative_to(get_cwl_ica_repo_path())`).

## Correctness checks
- Double-copy of the same file is prevented: a dedup set of `.absolute().resolve()` paths
  is built from the print-deps collection, and each schema is appended only if its resolved
  path is not already present. Print-deps paths are produced `.absolute()` (not `.resolve()`d,
  may contain `../`), while schema paths are already resolved; normalising both sides with
  `.absolute().resolve()` makes the comparison sound.
- Fragment handling is consistent on both sides: print-deps locations pass through
  `get_path_from_cwl_id` (strips `#frag` via `urldefrag`) and `get_schemas` uses
  `urlparse(...).path` (fragment-free). So a schema referenced with a fragment by print-deps
  still matches its fragment-free resolved schema path and is not re-appended.
- `new_path.parent.mkdir(exist_ok=False)` is relaxed to `exist_ok=True`. This is required and
  correct: two schema files sharing a version directory (or a schema dir already created by a
  print-deps file) would otherwise raise `FileExistsError`. File-level de-duplication still
  prevents copying the same file twice; only directory re-creation is now tolerated.
- Appended entries are `.yaml` schema files, so the downstream `.cwljs` `include_mappings`
  filter is unaffected.

## Constraints
- Code style / import grouping: reuses existing imports from `cwl_schema_helper_utils` and
  `repo`; no new import groups introduced. Consistent with file conventions.
- No test framework added.
- cwl_utils / wrapica version pins untouched (only one source file changed; `--stat` confirms).

## Recorded verification (from commit 99a904b)
- Reproduction script run from cwd `/home/alexiswl/GitHub/UMCCR/cwl-ica` with
  `PYTHONPATH=<worktree>/src` and the conda `cwl-ica` python3.14 interpreter (cwl_utils 0.45);
  commit states the edited code was loaded from the worktree and the shared install untouched.
- Output shows `OK -> /tmp/dragen-wgts-dna-pipeline__4.4.6.zip` (previously failed with
  `Expected a <class 'NoneType'> but got list`).
- All three previously-missing schemas reported present in the zip:
  - `schemas/bam-output/1.0.0/bam-output__1.0.0.yaml`
  - `schemas/cram-output/1.0.0/cram-output__1.0.0.yaml`
  - `schemas/dragen-wgts-options-alignment-stage/4.4.0/dragen-wgts-options-alignment-stage__4.4.0.yaml`
- Interpreter / PYTHONPATH stated as required; pins confirmed unchanged.

All required acceptance evidence is present and the implementation matches the approved
approach. No blockers.
