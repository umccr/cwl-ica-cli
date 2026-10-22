# Implementation Plan — adapt cwl-ica-cli to cwl-utils 0.45 (schema-salad 8.10.x)

## Goal

The user bumped `cwl-utils` (now 0.45, pulling schema-salad 8.10.x) and chose NOT to pin/downgrade.
Several symbols the codebase imports from `cwl_utils.parser.*` were renamed/removed, so the CLI
crashes on import for any command that touches CWL parsing (original repro:
`cwl-ica github-actions-build-workflow-release-asset --help` ->
`ImportError: cannot import name 'shortname' from 'cwl_utils.parser.latest'`).

Scope: edit ONLY files under `src/cwl_ica/`. Do NOT touch site-packages. Do NOT pin/downgrade
cwl-utils. Do NOT add a test framework (repo convention: validation is via import smoke tests and
the `--help` repro). Change only what the API bump actually breaks.

## Install / verification note (critical)

The package is installed NON-editable into the conda env `cwl-ica`
(`/home/alexiswl/miniconda3/envs/cwl-ica/lib/python3.14/site-packages/cwl_ica/`). Editing `src/`
does NOT change the installed runtime. To verify EDITED source without reinstalling, run from
`src/` via PYTHONPATH under the conda env. All verify commands below use this pattern.

## Confirmed API changes in cwl-utils 0.45 (from live introspection against the installed env)

Symbol existence across parser modules (`hasattr`, verified):

| old symbol      | v1_0 / v1_1 / v1_2 / latest | new name                         |
|-----------------|-----------------------------|----------------------------------|
| `RecordSchema`  | GONE                        | `CWLRecordSchema`                |
| `ArraySchema`   | GONE                        | `CWLArraySchema`                 |
| `EnumSchema`    | GONE (no `CWLEnumSchema`)   | base moved to `schema_salad.metaschema.EnumSchema`; concrete `InputEnumSchema`/`OutputEnumSchema` remain |
| `shortname`     | GONE from `parser.latest`   | `schema_salad.runtime.shortname` (already fixed in a prior session) |

All other symbols the codebase imports were verified to STILL EXIST and MUST NOT be changed:
`WorkflowInputParameter` (v1_1/v1_2/latest — correctly absent from v1_0 and not imported from there),
`WorkflowOutputParameter`, `Workflow`, `WorkflowStep`, `CommandLineTool`, `load_document_by_uri`,
`Input/OutputEnumSchema`, `Input/OutputArraySchema`, `Input/OutputRecordSchema`, and all the
`*Requirement` names in `cwl_utils_typing_helpers.py`.

### Runtime-behavior finding for `CWLRecordSchema` (settled by construction, not by reading)

`CWLRecordSchema.__init__` signature is now
`(self, type_, fields=None, extension_fields=None, loadingOptions=None)` — `type_` is a required
positional first arg. Concern was whether the old pattern `RecordSchema(yaml_obj).type_` (pass the
whole yaml dict as the only positional, then read `.type_` back) still yields the plain-dict-like
structure the downstream code relies on (`.get("type")`, `.get("name")`, `.get("fields")`,
`json.dumps(self.cwl_obj)`, `deepcopy`, `new_cwl_obj["fields"] = ...`).

Verified by constructing against a real schema
(`.../schemas/dragen-tmb-options/4.4.0/dragen-tmb-options__4.4.0.yaml`):
- `CWLRecordSchema(yaml_obj)` accepts the single positional arg (the yaml `CommentedMap` becomes `type_`).
- `.type_` returns the SAME `ruamel.yaml.comments.CommentedMap` unchanged: `.get("type")=="record"`,
  `.get("name")=="dragen-tmb-options"`, `.get("fields")` is a `CommentedMap`.
- `CWLRecordSchema(type_="record", fields=[])` (the `create_object` pattern) works: `.type_=="record"`, `.fields==[]`.
- `CWLSchema(...).import_cwl_yaml()` followed by `validate_object()` (which does `.get(...)` and
  `json.dumps(self.cwl_obj)`) PASSES end to end.

Conclusion: these are PURE RENAMES. No constructor-call or dict-access adaptation is needed for
either `CWLRecordSchema(yaml_obj).type_` or `CWLRecordSchema(type_=..., fields=...)`.

### `ArraySchemaType` / `EnumSchemaType` replacement rationale (settled by MRO)

`ArraySchemaType` and `EnumSchemaType` are used only as `isinstance(...)` targets in
`cwl_helper_utils.get_workflow_type` (array branch) around lines 476/489 and the enum branch around
line 500, where the operand is a workflow input/output parameter's `.type_`.

MRO verified: `InputArraySchema`, `OutputArraySchema`, `CommandInputArraySchema` all subclass
`CWLArraySchema`; `InputEnumSchema`, `OutputEnumSchema`, `CommandInputEnumSchema` all subclass
`schema_salad.metaschema.EnumSchema`. So:
- `ArraySchema_v1_x` -> import `CWLArraySchema as ArraySchema_v1_x` from each per-version module. The
  `isinstance(i_o_type, ArraySchemaType)` checks keep working (concrete array schemas are subclasses).
- There is NO `CWLEnumSchema`. Rather than add a new `schema_salad.metaschema` import into the typing
  helpers, redefine `EnumSchemaType` as the union of the existing `InputEnumSchemaType` and
  `OutputEnumSchemaType` (both already defined in the file from the still-valid concrete
  `Input/OutputEnumSchema` imports). A parameter's `.type_` for an enum is always an
  `Input/OutputEnumSchema`, so this covers every runtime case the old base `EnumSchema` covered here.

`RecordSchemaType` is defined but never referenced outside its own module; still fix its members so
the union stays valid (do not delete it — minimise churn, preserve style).

### Full list of distinct ImportErrors the import walk surfaced (before fix)

Running the submodule walk from the current `src/` (shortname fix already applied) surfaced 21
cwl-utils ImportErrors plus 1 pre-existing unrelated error. All 21 reduce to exactly TWO distinct
root causes, both the `RecordSchema` rename, propagating directly or transitively:

1. `cannot import name 'RecordSchema' from 'cwl_utils.parser.latest'` — direct in
   `classes/cwl_schema.py` and `utils/cwl_schema_helper_utils.py`; transitive importers:
   `classes/item_schema`, `classes/item_version_schema`, `subcommands/creators/create_schema_from_template`,
   `subcommands/initialisers/schema_init`, `subcommands/validators/schema_validate`.
2. `cannot import name 'RecordSchema' from 'cwl_utils.parser.cwl_v1_0'` — direct in
   `utils/cwl_utils_typing_helpers.py`; transitive importers (via that module or `cwl_helper_utils`):
   `utils/cwl_helper_utils`, `utils/cwl_workflow_helper_utils`, `utils/pydot_utils`,
   `classes/cwl_tool`, `classes/item_tool`, `classes/item_version_tool`,
   `subcommands/creators/create_tool_from_template`, `subcommands/initialisers/tool_init`,
   `subcommands/validators/tool_validate`, `subcommands/query/get_workflow_step_ids`,
   `subcommands/updaters/add_category_to_tool`, `subcommands/v2/zip_v2_workflow`,
   `subcommands/github_actions/build_workflow_release_assets` (the original repro command).

The `ArraySchema`/`EnumSchema` renames do NOT appear as separate walk errors only because
`cwl_utils_typing_helpers.py` hits the `RecordSchema` line first; they are confirmed broken by direct
import test and MUST be fixed in the same edit, or the file will fail on the next line after the
RecordSchema fix.

Pre-existing, OUT OF SCOPE (NOT caused by the cwl-utils bump):
- `cwl_ica.subcommands.updaters.add_maintainer :: NameError: name 'get_logger' is not defined` —
  `src/cwl_ica/subcommands/updaters/add_maintainer.py` is an unfinished stub (no imports, just
  `logger = get_logger()`). It never imported cwl-utils and failed before the bump too. Do NOT fix it
  as part of this task.

## Items

- [ ] 1. Rename `RecordSchema` -> `CWLRecordSchema` in `src/cwl_ica/classes/cwl_schema.py`.
      Under the `# CWL Utils` header change `from cwl_utils.parser.latest import \ RecordSchema` to
      `... import \ CWLRecordSchema`. Update the two call sites: `import_cwl_yaml` line
      `self.cwl_obj = RecordSchema(yaml_obj).type_` -> `CWLRecordSchema(yaml_obj).type_`; `create_object`
      `self.cwl_obj = RecordSchema(type_="record", fields=[])` -> `CWLRecordSchema(type_="record", fields=[])`.
      No other logic changes — `.type_`/`.fields` access and `validate_object`'s dict access stay as-is
      (verified behavior-preserving). Keep the existing `# CWL Utils` comment header.
      Files: src/cwl_ica/classes/cwl_schema.py
      Verify: `conda run -n cwl-ica env PYTHONPATH=/home/alexiswl/GitHub/UMCCR/cwl-ica-cli/src python -c "import cwl_ica.classes.cwl_schema"` exits 0 with no ImportError.

- [ ] 2. Rename `RecordSchema` -> `CWLRecordSchema` in `src/cwl_ica/utils/cwl_schema_helper_utils.py`.
      Under `# CWL Utils` change `from cwl_utils.parser.latest import RecordSchema` to
      `from cwl_utils.parser.latest import CWLRecordSchema`. Update the type annotation
      `self.cwl_obj: RecordSchema = cwl_obj` -> `self.cwl_obj: CWLRecordSchema = cwl_obj` and the
      constructor in `load_schema_from_uri`: `return cls(RecordSchema(schema_obj), file_path)` ->
      `return cls(CWLRecordSchema(schema_obj), file_path)`. Leave `from cwl_utils.parser import Workflow` and
      all `.type_.get(...)` access unchanged.
      Files: src/cwl_ica/utils/cwl_schema_helper_utils.py
      Verify: `conda run -n cwl-ica env PYTHONPATH=/home/alexiswl/GitHub/UMCCR/cwl-ica-cli/src python -c "import cwl_ica.utils.cwl_schema_helper_utils"` exits 0.

- [ ] 3. Fix the renamed schema imports in `src/cwl_ica/utils/cwl_utils_typing_helpers.py` (three per-version
      blocks). In each of the `cwl_v1_0`, `cwl_v1_1`, `cwl_v1_2` import groups:
      change `RecordSchema as RecordSchema_v1_X` -> `CWLRecordSchema as RecordSchema_v1_X`;
      change `ArraySchema as ArraySchema_v1_X` -> `CWLArraySchema as ArraySchema_v1_X`;
      remove the `EnumSchema as EnumSchema_v1_X` line (there is no `CWLEnumSchema`), and remove the now-
      dangling trailing comma on the preceding `CWLArraySchema as ArraySchema_v1_X` line so each group
      ends cleanly. Keep the alias names (`RecordSchema_v1_X`, `ArraySchema_v1_X`) so the downstream
      `Union` definitions and all other modules referencing the `*Type` aliases are untouched.
      Then redefine the `EnumSchemaType` union (currently `Union[EnumSchema_v1_0, EnumSchema_v1_1,
      EnumSchema_v1_2]`) as:
      `EnumSchemaType = Union[InputEnumSchemaType, OutputEnumSchemaType]`
      (both are already defined above in this same file). Leave `RecordSchemaType` and `ArraySchemaType`
      union bodies as-is — their members now resolve to the renamed classes via the updated aliases.
      Files: src/cwl_ica/utils/cwl_utils_typing_helpers.py
      Verify: `conda run -n cwl-ica env PYTHONPATH=/home/alexiswl/GitHub/UMCCR/cwl-ica-cli/src python -c "import cwl_ica.utils.cwl_utils_typing_helpers, cwl_ica.utils.cwl_helper_utils"` exits 0.

- [ ] 4. Confirm no other source file imports a removed symbol. The `shortname` fix in
      `src/cwl_ica/utils/cwl_helper_utils.py` (import from `schema_salad.runtime`) is already present and
      must be KEPT; that file imports no `RecordSchema`/`ArraySchema`/`EnumSchema` directly (its earlier
      walk error was transitive via `cwl_utils_typing_helpers`). No edit expected here — this item is a
      guard: grep `src/cwl_ica` for any remaining `import ... RecordSchema`/`ArraySchema`/`EnumSchema`
      (bare, without the `CWL`/`Input`/`Output`/`Command` prefix) or `shortname` imported from
      `cwl_utils`, and fix any that are found following the same rename rules.
      Files: (none expected; fix in place if the grep finds a stray import)
      Verify: no stray bare `RecordSchema`/`ArraySchema`/`EnumSchema` cwl_utils imports remain, confirmed by the full walk in item 5.

- [ ] 5. Full-package import smoke test from edited src. Run the submodule import walk and confirm the only
      remaining error is the pre-existing, out-of-scope `add_maintainer` `NameError` (zero cwl-utils
      ImportErrors).
      Files: (verification only)
      Verify:
      `conda run -n cwl-ica env PYTHONPATH=/home/alexiswl/GitHub/UMCCR/cwl-ica-cli/src python -c "import importlib, pkgutil, cwl_ica; errs=[]`
      `[errs.append((m.name, type(e).__name__, str(e))) for m in pkgutil.walk_packages(cwl_ica.__path__, 'cwl_ica.') for e in [None]]"` —
      practically: walk all modules, collect exceptions; EXPECT exactly one failure,
      `cwl_ica.subcommands.updaters.add_maintainer :: NameError`, and NO `ImportError` mentioning
      `cwl_utils`/`RecordSchema`/`ArraySchema`/`EnumSchema`/`shortname`.

- [ ] 6. Reproduce the original user command against edited src and confirm it no longer raises ImportError.
      Files: (verification only)
      Verify:
      `conda run -n cwl-ica env PYTHONPATH=/home/alexiswl/GitHub/UMCCR/cwl-ica-cli/src python -c "import cwl_ica.subcommands.github_actions.build_workflow_release_assets; print('ok')"`
      prints `ok` and exits 0 (the module that backs
      `cwl-ica github-actions-build-workflow-release-asset --help`, which previously raised the reported
      ImportError, now imports cleanly).

- [ ] 7. Functional sanity check of the record-schema round trip (confirms the rename is behavior-
      preserving, not merely import-clean). Load a real schema through `CWLSchema`, read back the dict, and
      run `validate_object()`.
      Files: (verification only)
      Verify (requires `CWL_ICA_REPO_PATH` and at least one schema present; adjust the schema path if the
      sample differs):
      `conda run -n cwl-ica env PYTHONPATH=/home/alexiswl/GitHub/UMCCR/cwl-ica-cli/src CWL_ICA_REPO_PATH=/home/alexiswl/GitHub/UMCCR/cwl-ica python -c "from pathlib import Path; from cwl_ica.classes.cwl_schema import CWLSchema; s=CWLSchema(Path('/home/alexiswl/GitHub/UMCCR/cwl-ica/schemas/dragen-tmb-options/4.4.0/dragen-tmb-options__4.4.0.yaml'),'dragen-tmb-options','4.4.0'); assert s.cwl_obj.get('type')=='record'; s.validate_object(); print('validate ok')"`
      prints `validate ok`. (This exact sequence was already run successfully against a scratch copy during
      planning.)

## Notes / assumptions carried into the plan

- All edits preserve the repo's grouped-import comment headers (`# External imports` / `# CWL Utils` /
  `# Classes` / `# Locals`).
- `add_maintainer.py`'s `NameError` is explicitly left unfixed (pre-existing, unrelated). If the
  implement/review loop flags it, note it as out of scope for this cwl-utils adaptation.
- No `pyproject.toml`/env edits: the task is source adaptation only; cwl-utils stays unpinned.
- The entire fix was validated end-to-end on a throwaway copy of `src/` during planning: the walk went
  from 21 cwl-utils ImportErrors to 0 (only the unrelated `add_maintainer` NameError remained), the repro
  module imported cleanly, and `CWLSchema.validate_object()` passed.
