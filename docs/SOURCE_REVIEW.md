# Reporting source review — 30 October 2026

This branch preserves the unpublished manual-dashboard contract commit
`c93f8ea3d48de3d576752e585d9689980e3330f5` and prepares the separately reviewed
0.5.0-beta.1 observation reporting candidate. It is not a HACS release, installed
package receipt or live feed repair.

Legacy eleven entities, eight actions and signed deployment semantics stay unchanged.
The four optional observation sensors consume explicitly paired controller-authored
v2 reports. Backend integration and frontend-resource campaigns share the existing
`reported_health` projection. The Companion does not fetch or execute frontend
resources, infer installed identity, start/stop campaigns, or own provider credentials.
Missing, stale or unpaired reporting stays unavailable; running native observation
is not proof that a Companion publisher is working.

The controller keeps its historical v0.4.1 Git link during this review. Interoperability
checks can select the separate controller source with `HILC_CONTROLLER_SOURCE`; they
do not change either repository's authority or imply adoption of an uncommitted tree.
Public source excludes private profiles, enrollment, replay stores, keys and receipts.
Existing development worktrees and duplicate local files remain untouched.

## Validation

Run the repository suite from `AGENTS.md` and `ruby scripts/validate_dashboard.rb`.
Run observation
adapter tests with the pinned Home Assistant 2026.9.0/Python 3.14 environment from CI;
without it those tests skip and must not be reported as complete. Real disposable
filesystem and loopback transport tests are distinct from pure protocol/schema
fixtures and from live Home Assistant evidence. No live target is contacted.

Fresh branch validation: **61 tests passed**, including pinned HA adapter,
disposable storage/permissions/reload/HTTP and explicit backend/frontend selected-profile
interoperability with the controller review source. The new frontend case has no
campaign and makes no live campaign or browser-execution claim. Both schemas, Python
compilation, workflow YAML, Ruby dashboard contract, whitespace and public repository
privacy checks passed. Gitleaks source and history scans found zero matches.

An earlier extended test run had two assertion-key errors; the corrected 61-test run
passed and the failed log is retained privately. Bella, Aetherwing and Aetherbite
reviewed the bounded source changes; initial documentation findings were resolved.
The admitted candidate implementation and protocol/schema bytes were copied unchanged;
this preparation adds documentation and interoperability coverage.
HACS Action and Hassfest on the proposed revision remain required before release.

## Next decision

Accept the source review and authorize its separate commit/PR. Publication, release,
installation/restart, pairing repair and dashboard import remain separate decisions.
Only an accepted immutable Companion commit can support a proposed controller Git-link
update. Preserve replay sequence custody during any later authorized maintenance.
