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
- Companion release line: `0.4.x`
- Supported status schema majors: `1` and `2`
- Registered actions: eight fixed services declared in `services.yaml`
- Registered entities: ten sensors and one binary sensor
- Configuration schema: one local shared secret, stored by Home Assistant

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
dashboard template. Its responsive Operations view uses a semantic green/amber/red
status language and its separate Evidence view retains selected exact controller
attributes.
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

## Security and privacy

Tracked files are public-safe. Shared secrets, target identities, mailbox contents,
signed snapshots, controller configuration, credentials, and operational evidence must
never enter this repository. All unsafe or incomplete status evidence fails closed.
