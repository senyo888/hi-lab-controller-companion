# Changelog

## Unreleased

- Added the official HI Lab Controller Companion artwork as the README header while
  preserving the repository's public-safe controller/companion authority boundary.
- Added an optional, importable `dashboards/hi-lab-operations.yaml` dashboard with a
  responsive Operations view and a separate detailed Evidence view, built only from
  native Home Assistant cards and the companion's eleven entities.
- Refined the optional dashboard into a balanced tablet-first two-column surface with
  a full-width official header. System pulse now pairs with Contact and restart,
  Deployment lifecycle pairs with Baseline acceptance, and both pairs collapse in a
  logical order on mobile. The proven horizontal validation, outcome, queue, and
  navigation-only Actions treatment remains intact.
- Added a darker dashboard-specific treatment of the official companion header and
  representative native icons across the Evidence groups while preserving the
  original README artwork and avoiding custom frontend dependencies.
- Added direct degraded-state callouts for feed integrity, readiness, mutation lock,
  restart truth, and queue truth while preserving active, pending, accepted-baseline,
  validation, and outcome facts as separate controller-owned evidence.
- Added a direct green/amber/red semantic state language, an illustrative public-safe
  preview, import guidance, an exact Home Assistant 2026.4 presentation floor,
  mobile/desktop verification steps, presentation-only rollback, and gallery placement.
- Added the official bundled controller mark to the self-contained public preview and
  renamed technical Stage B/Stage 3 dashboard rows to the public-facing **Integration
  health** and **Runtime truth** labels without changing their source attributes.
- Made the native **Operations** and **Evidence** navigation model explicit and added
  one prominent **Open Actions tool** navigation-only card. It supplies no action data
  and cannot execute a Home Assistant action.
- Added the official companion artwork and controller mark to the Operations header
  through a fixed Home Assistant-local asset path, with import and presentation-only
  rollback guidance and no remote image or optional-card dependency.
- Added repository contract checks that reject extra entity IDs, custom cards,
  action/service calls, unbounded interactions, and missing degraded-state coverage,
  and that bind the dashboard to its official local header artwork.
- Added a public operator guide for HACS installation, activation, verification,
  updates, rollback, all eleven native entities, and all eight administrator actions.
- Added a README architecture diagram that distinguishes Home Assistant presentation
  from external-controller authority, identifies the controller-owned private SSH
  mailbox bridge, and keeps the optional dashboard inside the read-only presentation
  boundary.
- Clarified that automatic HACS updates may remain enabled while restart, runtime
  verification, controller deployment, and release authority stay separate.
- No runtime, entity, action, protocol, or authority behavior changed. The dashboard is
  optional, read-only, and is not installed automatically.

## 0.4.1 - 2026-08-28

- Established the companion as an independently versioned custom-HACS integration.
- Added public-safe repository, architecture, security, validation, and branding
  surfaces.
- Adopted the MIT License for the public companion repository.
- Corrected documentation and issue routes to the companion repository.
- Declared the integration as config-entry-only and removed invalid legacy uppercase
  enum translation maps without changing the underlying entity state values.
- Preserved the existing eight actions, eleven entities, status-schema-major 1 and 2
  support, local signed-mailbox protocol, and fail-closed behavior.
- Enabled the release-only HACS update channel, including operator-selected automatic
  updates. A HACS download still requires separate restart and runtime verification.
- Added no Git, SSH, provider, source-selection, package, target, deployment, baseline,
  Humidity Intelligence release, or Stable authority to Home Assistant.
