# Verification evidence — adapt cwl-ica-cli to cwl-utils 0.45

Addresses review finding "No coder verification evidence recorded" (review.json verdict
CHANGES_REQUESTED). The four `src/cwl_ica/` edits were already reviewed as correct; this file
records the actual verification runs against the EDITED source so the evidence is auditable.

## Environment

- Conda env: `cwl-ica`, Python 3.14
- `cwl-utils 0.45`, `schema-salad 8.10.20260825112551`
  (`conda run -n cwl-ica python -c "from importlib.metadata import version; print(version('cwl-utils'), version('schema-salad'))"`)
- All commands run the EDITED source via `PYTHONPATH=/home/alexiswl/GitHub/UMCCR/cwl-ica-cli/src`
  (package is installed non-editable, so src must be on PYTHONPATH to exercise the edits — not the
  stale installed copy).

## Files changed (all under src/cwl_ica/)

- `src/cwl_ica/classes/cwl_schema.py` — `RecordSchema` -> `CWLRecordSchema` (import + 2 call sites).
- `src/cwl_ica/utils/cwl_schema_helper_utils.py` — `RecordSchema` -> `CWLRecordSchema` (import,
  annotation, constructor).
- `src/cwl_ica/utils/cwl_utils_typing_helpers.py` — per-version `RecordSchema`->`CWLRecordSchema`,
  `ArraySchema`->`CWLArraySchema`; removed non-existent `EnumSchema` imports; redefined
  `EnumSchemaType = Union[InputEnumSchemaType, OutputEnumSchemaType]`.
- `src/cwl_ica/utils/cwl_helper_utils.py` — `shortname` imported from `schema_salad.runtime`
  (kept from prior session).

## Symbol-rename confirmation

```
conda run -n cwl-ica python -c "import cwl_utils.parser.latest as m; print('CWLRecordSchema', hasattr(m,'CWLRecordSchema')); print('CWLArraySchema', hasattr(m,'CWLArraySchema')); print('RecordSchema', hasattr(m,'RecordSchema')); print('CWLEnumSchema', hasattr(m,'CWLEnumSchema')); print('InputEnumSchema', hasattr(m,'InputEnumSchema'))"
```
Result: `CWLRecordSchema` and `CWLArraySchema` present; old `RecordSchema`/`ArraySchema` gone; no
`CWLEnumSchema` (only `Input/Output/CommandInput/CommandOutputEnumSchema`) — confirms the chosen
`EnumSchemaType` union of the concrete Input/Output enum schema types.

## Item 5 — full submodule import walk (expect 0 cwl-utils ImportErrors)

```
conda run -n cwl-ica env PYTHONPATH=/home/alexiswl/GitHub/UMCCR/cwl-ica-cli/src python -c "
import importlib, pkgutil, cwl_ica
errs = []
for m in pkgutil.walk_packages(cwl_ica.__path__, 'cwl_ica.'):
    try:
        importlib.import_module(m.name)
    except Exception as e:
        errs.append((m.name, type(e).__name__, str(e)))
print('TOTAL ERRORS:', len(errs))
for name, etype, msg in errs:
    print(f'{name} :: {etype}: {msg}')
"
```
Output:
```
TOTAL ERRORS: 1
cwl_ica.subcommands.updaters.add_maintainer :: NameError: name 'get_logger' is not defined
```
Zero cwl-utils ImportErrors. The single remaining failure is the pre-existing, out-of-scope
`add_maintainer` stub `NameError` (never imported cwl-utils; broken before the bump) — explicitly
left unfixed per the plan.

## Item 6 — original reproducer

```
conda run -n cwl-ica env PYTHONPATH=/home/alexiswl/GitHub/UMCCR/cwl-ica-cli/src python -c "import cwl_ica.subcommands.github_actions.build_workflow_release_assets; print('ok')"
```
Output: `ok` (exit 0).

Original CLI command (the one the user reported crashing):
```
conda run -n cwl-ica env PYTHONPATH=/home/alexiswl/GitHub/UMCCR/cwl-ica-cli/src python -m cwl_ica.utils.cli github-actions-build-workflow-release-asset --help
```
Exit 0, no ImportError, no traceback. (The `--help` text itself prints empty; this is a
pre-existing CLI help-rendering quirk — the top-level no-arg invocation also prints nothing — and
is unrelated to the cwl-utils adaptation. The class docopt docstring is intact at 1175 chars. The
original failure was an `ImportError: cannot import name 'shortname'` traceback, which is now gone.)

## Additional CWL-touching subcommand smoke tests

```
python -m cwl_ica.utils.cli tool-validate --help      # exit 0, no ImportError
python -m cwl_ica.utils.cli schema-validate --help    # exit 0, no ImportError
```
Both exit 0 with no ImportError/traceback.

## Item 7 — record-schema round-trip (behavior-preserving, not just import-clean)

```
conda run -n cwl-ica env PYTHONPATH=/home/alexiswl/GitHub/UMCCR/cwl-ica-cli/src CWL_ICA_REPO_PATH=/home/alexiswl/GitHub/UMCCR/cwl-ica python -c "
from pathlib import Path
from cwl_ica.classes.cwl_schema import CWLSchema
s = CWLSchema(Path('/home/alexiswl/GitHub/UMCCR/cwl-ica/schemas/dragen-tmb-options/4.4.0/dragen-tmb-options__4.4.0.yaml'), 'dragen-tmb-options', '4.4.0')
assert s.cwl_obj.get('type') == 'record'
s.validate_object()
print('validate ok')
"
```
Output: `validate ok`. Confirms `CWLRecordSchema(yaml_obj).type_` returns the same dict-like object
the downstream `.get('type')/.get('name')/.get('fields')` and `json.dumps(self.cwl_obj)` logic in
`validate_object()` relies on — the rename is behavior-preserving.

## Conclusion

Submodule import walk clean of cwl-utils ImportErrors; original reproducer and additional
CWL-touching subcommands import and run `--help` with no traceback; record-schema round-trip
validates. All edits confined to `src/cwl_ica/`; no site-packages change, no cwl-utils/schema-salad
pin or downgrade, no test framework added.
