# Optional dashboard gallery

## HI Lab operations

![Illustrative public-safe preview of the HI Lab operations
dashboard](../docs/images/hi-lab-operations-dashboard.svg)

[`hi-lab-operations.yaml`](hi-lab-operations.yaml) is the canonical importable
template. It pairs a responsive, semantically colored **Operations** tab with a
separate exact-attribute **Evidence** tab. On tablet-sized content widths the official
header spans the view, **System pulse** pairs with **Contact and restart**, and
**Deployment lifecycle** pairs with **Baseline acceptance**. The wide validation,
outcome, queue, and evidence groups retain their deliberate full-width treatment;
narrower content widths collapse the outer pairs cleanly to one readable column. Both
views are read-only surfaces over the companion's eleven native entities and use only
built-in Home Assistant cards. The
full-size **Open Actions tool** control is navigation only; it cannot
execute an administrator action or service call, and it supplies no action data. The
native tool can retain its own prior editor state. The template exactly as shipped
requires Home Assistant 2026.4 or newer. Its Operations header displays the official
companion artwork and controller mark from the fixed local path
`/local/hi-lab-controller/companion-dashboard-header.png`; copy
`assets/hi-lab-controller-companion-dashboard-header.png` to the matching Home
Assistant `www/hi-lab-controller/` directory as part of import.

See [Using the companion](../docs/USING_THE_COMPANION.md#install-the-optional-read-only-dashboard)
for import, compatibility, responsive-layout checks, truth verification, and
presentation-only rollback.

For exact bundle metadata, artifact digests, compatibility, entity semantics, and
the preview/backup/confirmation/readback workflow, see the
[manual dashboard bundle contract](../docs/DASHBOARD_BUNDLE_CONTRACT.md). The
checked-in manifest is a contract example, not release, installation, or live-import
evidence.

## Missing and historical evidence

Evidence cards explain missing records instead of presenting empty attribute rows.
The signed deployment feed must be fresh before deployment records are shown.
`none` is kept distinct from `unknown` and `unavailable`: no pending deployment is
an explicit controller fact, while an unavailable active identity is not proof
that the integration is stopped. A `CLEAR` mutation lock has no owner or held-at
timestamp; it does not establish deployment readiness. A disabled queue remains
controller-owned and cannot be enabled here.

Accepted baseline and terminal deployment outcomes are labelled as historical
records and retain the controller's original acceptance/completion dates. They do
not identify the currently running package or accept a later version. Missing
Stage B/Stage 3 deployment validation and restart evidence remain unavailable;
a completed observation soak cannot fill those gaps. Per-field `not reported`
wording preserves reported zero counts and false flags. The independent observation
sections and their retained campaign results are unchanged.

These are presentation changes only. Import still requires the existing manual
preview, backup, explicit confirmation and readback workflow. The illustrative
preview above is a layout reference, not current runtime evidence.
