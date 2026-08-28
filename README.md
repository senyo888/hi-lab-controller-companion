# HI Lab Controller Companion

The public Home Assistant companion for the separately operated **HI Lab Controller**.
It provides a narrow administrator-only action gateway and truthful diagnostic entities
for a dedicated HA Lab. It does not contain the external controller and does not install
or control Humidity Intelligence by itself.

The external controller remains private while its design characteristics, security
boundary, compatibility, and operational stability are completed. It is intended to
become a separately published maintainer tool only after those release gates pass.

## Install with custom HACS

1. In HACS, open **Custom repositories**.
2. Add `https://github.com/senyo888/hi-lab-controller-companion` as an
   **Integration** repository.
3. Download the selected published release.
4. Restart Home Assistant when separately approved so the new Python generation can
   become active.
5. Add **HI Lab Controller** from **Settings → Devices & services** and provide the
   private shared secret provisioned for the external controller.

Automatic HACS updates are supported. Only maintainer-published releases are exposed
as normal update candidates; the default branch is hidden. Downloading an update does
not prove restart completion, compatibility, runtime health, deployment acceptance, or
any Humidity Intelligence release state.

## Fixed actions

- `hi_lab_controller.prepare_version`
- `hi_lab_controller.activate_prepared_version`
- `hi_lab_controller.discard_prepared_version`
- `hi_lab_controller.deployment_status`
- `hi_lab_controller.controller_health`
- `hi_lab_controller.rollback_deployment`
- `hi_lab_controller.queue_prepare_version`
- `hi_lab_controller.cancel_queued_prepare`

Action registration does not grant authority to use an action. Source and target
selection remain fixed in the external controller, and queue capability remains
controller-owned and fail-closed when disabled.

## Status surface

The integration registers ten sensors and one binary sensor. It accepts signed status
schema majors 1 and 2 and makes controller truth unavailable when the local snapshot is
missing, stale, malformed, unsigned, permission-unsafe, or incompatible.

## Boundaries

- No Git, SSH, repository, provider, package, target, HACS, or release authority is
  present in the companion.
- No private addresses, entity IDs, credentials, target identities, or runtime evidence
  belong in this repository.
- This project is separate from the public Humidity Intelligence integration.
- The external controller's future-public direction is not a present availability,
  readiness, publication, or release claim.
- HACS owns normal companion installation and updates. The external controller's
  transactional bootstrap is a separately governed recovery route only.

See [ARCHITECTURE.md](ARCHITECTURE.md) and [SECURITY.md](SECURITY.md).
