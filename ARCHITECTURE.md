# HI Lab Controller Companion architecture

## Purpose

This repository is the public, HACS-installable Home Assistant companion for the
separately operated HI Lab Controller. It exposes a small administrator-only action
surface and fail-closed status entities. It is not Humidity Intelligence, does not
contain the external controller, and cannot select repositories, source refs, targets,
packages, credentials, deployments, baselines, or releases.

The external controller is private during design stabilization. Its accepted direction
is a future separate public release after its architecture, security, compatibility,
operational evidence, documentation, and release criteria are complete. This direction
does not make the controller currently public or release-ready.

## Responsibility split

| Boundary | Owner |
| --- | --- |
| Home Assistant integration source and HACS releases | This repository |
| Git/source resolution, target policy, package mutation, evidence, and rollback decisions | External HI Lab Controller |
| Humidity Intelligence runtime and product policy | Humidity Intelligence |

The companion writes signed requests to a fixed local mailbox and reads a bounded,
permission-checked, signed local status snapshot. The external controller remains the
only authority for source resolution and package operations.

## Compatibility contract

- Domain: `hi_lab_controller`
- Companion release line: `0.4.x`; optional reporting source candidate `0.5.0-beta.1`
- Supported status schema majors: `1` and `2`
- Registered actions: eight fixed services declared in `services.yaml`
- Legacy entities: ten sensors and one binary sensor, unchanged
- Additive observation entities: four sensors with independent availability
- Configuration schema: one legacy shared secret; optional explicit observation instance/epoch/key pairing

The [observation v2 compatibility contract](docs/OBSERVATION_REPORTING.md) adds a
fixed administrator-authenticated signed telemetry endpoint and separate durable
replay custody. The external controller remains the only campaign owner/scheduler.
No new action or Start/Stop surface is provided. Selection, campaign identity,
checkpoint time, current feed expiry and historical results remain distinct.
Receiver unload drains a physical persistence operation before a replacement loads
its sequence floor. Reporting storage is separate from the legacy mailbox/status.

Changes to an action name, entity identity, signature domain, status schema support,
mailbox location, or restart behavior require a versioned compatibility decision and
coordinated controller validation.

## HACS lifecycle

The repository is intended to be added as a custom HACS integration. Published GitHub
releases are the only normal update channel; the default branch is hidden from HACS.
Automatic HACS updates are supported. Maintainer control is exercised by publishing
only reviewed, controller-compatible releases.

HACS may download and replace the integration files. It does not authorize a Home
Assistant restart, prove that updated Python is active, validate the external
controller, or accept a runtime baseline. Those remain separate evidence-backed steps.

## Optional dashboard surface

`dashboards/hi-lab-operations.yaml` is a manually imported, read-only Home Assistant
dashboard template. Its responsive Operations view uses a full-width header and two
paired tablet rows: System pulse beside Contact and restart, then Deployment lifecycle
beside Baseline acceptance. Those pairs collapse to an ordered single column at
narrower widths. A semantic green/amber/red status language remains direct
controller-authored presentation, while the separate Evidence view retains selected
exact controller attributes.
Both use core Home Assistant cards and only the eleven entities and documented
attributes owned by this integration. Conditional presentation maps direct entity
states to explicit expected/clear, attention, and degraded wording; it does not
recompute readiness, deployment, lock, validation, baseline, queue, outcome, or
restart truth.

The dashboard contains no administrator action call or service call and is not
installed or mutated automatically. Its single **Open Actions tool**
button is a bounded Home Assistant navigation action only: it cannot prefill or
execute a companion action. Its presence in this repository does not change the signed
status `dashboard` capability, which remains controller-provided protocol truth, and
does not add runtime, deployment, baseline, HACS, publication, or release authority.
Removing the dashboard changes presentation only.

The manual bundle design in `docs/DASHBOARD_BUNDLE_CONTRACT.md` is accepted as
design only by controller decision `HILC-ADR-20260830-006`; this companion repository
continues to own its source contract. It binds this canonical YAML, public assets,
compatibility metadata, and the eleven current entity semantics to a versioned
manifest. Its checked-in example remains contract evidence only, not a companion
release or live dashboard installation. Manual preview, private backup, explicit
administrator confirmation, supported-editor import, readback, and manual restore
remain the first delivery path. The contract does not change
`capabilities.dashboard: false`, and it grants no browser automation, direct
Home Assistant save, direct `.storage` write, runtime action, restart, or release
authority.

## Security and privacy

Tracked files are public-safe. Shared secrets, target identities, mailbox contents,
signed snapshots, controller configuration, credentials, and operational evidence must
never enter this repository. All unsafe or incomplete status evidence fails closed.
