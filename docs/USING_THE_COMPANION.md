# Using the HI Lab Controller Companion

The companion is the Home Assistant surface for a separately operated HI Lab
Controller. It adds native entities, administrator actions, and operation
notifications to the HA Lab. It does not contain the controller, select arbitrary
sources or targets, use Git or SSH, or decide whether a deployment is allowed.

## What gets installed

HACS installs one Home Assistant custom integration:

- a configuration flow under **Settings → Devices & services**;
- ten sensors and one binary sensor attached to one **HI Lab Controller** service
  device;
- eight fixed actions in Home Assistant's **Actions tool**; and
- persistent notifications for important prepare, queue, activate, discard, and
  rollback results.

Home Assistant labels that destination **Tools → Actions** from 2026.8 and
**Developer Tools → Actions** through 2026.7.

The repository includes an optional read-only dashboard template. Its responsive
Operations view maps explicit controller states to green, amber, and red presentation,
while a separate Evidence view retains selected exact attributes. Raw entity state
remains authoritative; neutral cyan, teal, and blue-grey tiles do not assert health.
The template uses the eleven native entities and built-in Home Assistant cards only.
It is not installed automatically, contains no controller action call, and does not
duplicate controller logic. Its sole interaction is bounded navigation to Home
Assistant's native action tool.

## Authority boundary

The data path is deliberately narrow:

1. The external controller uploads a bounded, signed status snapshot through its
   controller-owned private SSH connection.
2. The companion validates its signature, schema, freshness, permissions, and
   identity before exposing controller truth as Home Assistant entities.
3. An authenticated Home Assistant administrator may invoke one of eight fixed
   actions.
4. The companion writes a signed request to the fixed local controller mailbox.
5. The controller's supervised watcher reads that mailbox through the fixed private
   SSH connection, validates the request, and writes a signed response.
6. The external controller accepts or rejects the request and remains authoritative
   for source selection, packaging, locks, deployment state, validation, rollback,
   and evidence.

If status cannot be trusted, controller-derived entities become unavailable. The
companion never guesses a healthy state or reconstructs controller truth from Home
Assistant history. The companion exposes no general network API and holds no SSH key;
SSH transport and credentials belong only to the external controller.

## Install and activate

### 1. Prove the prerequisites

Before installing the companion, the maintainer must have separately provisioned:

- the external HI Lab Controller on the dedicated HA Lab boundary;
- its fixed local signed mailbox and status snapshot paths;
- one private shared secret known to that controller and the HA Lab; and
- current rollback evidence for the companion generation already running, if any.

The public companion repository does not provision the controller or generate its
secret. Do not store the secret in Git, screenshots, issue reports, dashboard YAML,
or automation YAML.

### 2. Install through HACS

1. Open **HACS → Integrations**.
2. Open the HACS menu and choose **Custom repositories**.
3. Enter `https://github.com/senyo888/hi-lab-controller-companion`.
4. Select **Integration** as the category and add the repository.
5. Open **HI Lab Controller** and download a published release.
6. Restart Home Assistant when the maintainer has approved activation of the newly
   downloaded Python generation.

HACS automatic updates may remain enabled. The maintainer controls which versions
become eligible by publishing releases, and the default branch is not offered as an
update. A download alone does not prove that the new generation is active or healthy;
activation still requires a Home Assistant restart and post-restart verification.

### 3. Add the integration

1. Open **Settings → Devices & services**.
2. Select **Add integration** and search for **HI Lab Controller**.
3. Enter the private shared secret provisioned for the external controller.
4. Submit the form. The setup succeeds only if the companion can authenticate to the
   controller through the fixed local mailbox.

Only one companion instance is allowed. A failed connection should be treated as a
controller, mailbox, secret, permissions, or target-boundary problem—not bypassed by
editing Home Assistant storage.

### 4. Verify the installation

After the approved restart and configuration:

1. Open **Settings → Devices & services → HI Lab Controller**.
2. Confirm one service device and eleven registered entities.
3. Confirm **Feed** is `fresh`; do not use **Last contact** as a substitute for
   current freshness.
4. Confirm controller **Readiness**, **Mutation lock**, **Pending deployment**,
   **Prepare queue**, and **Restart required** agree with the external controller's
   evidence.
5. Open Home Assistant's **Actions tool** and confirm all eight
   `hi_lab_controller.*` actions are registered.
6. If a read-only operational check is authorized, run **HI Lab Controller: Controller
   health** and review its returned response. Merely seeing an action in the list does
   not authorize using it.

## The eleven entities

The entity IDs below are the defaults. Home Assistant may change an entity ID if an
operator renames it; the integration's unique IDs remain fixed.

| Entity | What it shows | How to read it |
| --- | --- | --- |
| `sensor.hi_lab_controller_feed` | Companion-local feed health | `fresh` is the only state that exposes controller truth. `stale`, `missing`, `invalid_signature`, `schema_mismatch`, or `clock_invalid` fail closed. Attributes include supported and observed schema major, error code, snapshot revision, and expiry. |
| `sensor.hi_lab_controller_last_contact` | Last time a valid snapshot was accepted | Historical evidence only. A recent timestamp does not override a non-fresh **Feed** state. |
| `sensor.hi_lab_controller_readiness` | Controller readiness | `READY` or `BLOCKED`. Attributes expose bounded blocker codes, overflow count, and status revision. It is controller truth, not a Home Assistant decision. |
| `sensor.hi_lab_controller_active_deployment` | Exact active deployment identity | Shows a `HIL-…` deployment ID or `none`, with profile, manifest version, verification time, and baseline flag. It becomes unavailable if active identity is unproved. |
| `sensor.hi_lab_controller_pending_deployment` | Exact in-progress deployment | Shows a deployment ID or `none`, with lifecycle state, profile, manifest version, predecessor, and timestamps. It becomes unavailable on a lock-identity conflict. |
| `sensor.hi_lab_controller_mutation_lock` | Whether controller mutation is safely serialized | `CLEAR`, `HELD`, `CONFLICT`, or `UNVERIFIED`, with the owning deployment and lock evidence where available. Do not start mutation work unless the controller permits it. |
| `sensor.hi_lab_controller_accepted_baseline` | Last separately accepted deployment baseline | Shows a deployment ID or `none`, with target slot, profile, version, and acceptance time. Active deployment and accepted baseline are intentionally different facts. |
| `sensor.hi_lab_controller_last_validation` | Completion time of the latest controller validation | Attributes contain the deployment and installed identity plus **Integration health** (technical Stage B) and **Runtime truth** (technical Stage 3) counts and verdicts. It reports evidence; it does not accept a baseline. |
| `sensor.hi_lab_controller_last_outcome` | Latest terminal controller outcome | Examples include `ACTIVE`, `BLOCKED`, `FAILED_ACTIVATION`, `RESTORED_PRE_ACTIVATION`, and `ROLLED_BACK`. Attributes identify the deployment, profile, completion time, and bounded error codes. |
| `sensor.hi_lab_controller_prepare_queue` | Phase 4D prepare-queue state | `DISABLED`, `EMPTY`, `WAITING`, `FULL`, `BLOCKED`, `DEGRADED`, or `UNAVAILABLE`, with enabled state, depth, maximum depth, and bounded entries. The queue remains controller-owned and default-off unless separately enabled. |
| `binary_sensor.hi_lab_controller_restart_required` | Whether the exact pending lifecycle requires a restart | On or off only when durable controller restart truth is available. Attributes identify the deployment, reason, and approval. It is not permission to restart by itself. |

## The eight administrator actions

Every action requires an authenticated Home Assistant administrator and exactly one
configured controller gateway. Registration is discoverability, not authority.

| Action | Input | Effect and boundary |
| --- | --- | --- |
| `hi_lab_controller.controller_health` | None | Read-only controller gateway, target, lock, package-ownership, and readiness check. It does not prepare or deploy anything. |
| `hi_lab_controller.deployment_status` | `deployment_id` | Read-only ledger lookup for one exact deployment. |
| `hi_lab_controller.prepare_version` | `profile`: `public_patch_1` or `public_main` | Requests transactional staging of one controller-allowlisted source profile. It returns an exact deployment ID and never activates or restarts Home Assistant. |
| `hi_lab_controller.activate_prepared_version` | `deployment_id` | Requests activation of one exact verified deployment. The companion schedules a Home Assistant restart only when the controller response explicitly approves that exact restart. Controller post-restart verification remains authoritative. |
| `hi_lab_controller.discard_prepared_version` | `deployment_id` | Restores the verified pre-activation package for one prepared deployment without restarting Home Assistant. It is not a rollback of an already activated deployment. |
| `hi_lab_controller.rollback_deployment` | `deployment_id` | Requests restoration of the verified predecessor for an exact rollback-required deployment. It schedules a restart only after exact controller approval. |
| `hi_lab_controller.queue_prepare_version` | `profile`: `public_patch_1` or `public_main` | Queues one later prepare request when the controller capability is enabled and another mutation is active. It does not activate the result. The capability is controller-owned and default-off. |
| `hi_lab_controller.cancel_queued_prepare` | `queue_id` | Cancels one exact unclaimed queue entry. Claimed work cannot be cancelled or retried through this action. |

Read-only example for Home Assistant's **Actions tool**:

```yaml
action: hi_lab_controller.controller_health
data: {}
response_variable: controller_health
```

Bounded prepare example, for use only inside an approved maintenance gate:

```yaml
action: hi_lab_controller.prepare_version
data:
  profile: public_patch_1
response_variable: prepared
```

Use the deployment ID returned by the controller for subsequent status, activation,
discard, or rollback actions. Never substitute a display label, branch name, version,
or older deployment ID.

## Safe operating sequences

### Prepare, inspect, then activate

1. Prove **Feed** is `fresh`, **Readiness** is `READY`, **Mutation lock** is `CLEAR`,
   and **Pending deployment** is `none`.
2. Run `controller_health` within its separately approved read-only gate.
3. Run `prepare_version` for one fixed profile within an approved mutation gate.
4. Record the returned deployment ID and inspect `deployment_status`, **Pending
   deployment**, **Last validation**, and **Restart required**.
5. Stop if identity, signature, validation, lock, source, package, target, or rollback
   evidence differs from the approved packet.
6. Invoke `activate_prepared_version` only under a separate activation-and-restart
   authority for that exact deployment ID.
7. After Home Assistant returns, re-prove the companion version, all eleven entities,
   all eight actions, fresh signed status, active deployment, validation, last outcome,
   lock state, and rollback readiness.

### Discard before activation

Use `discard_prepared_version` when a verified staged package must be removed before
activation. Confirm the exact deployment ID and controller state first. The controller
restores the verified pre-activation package without a Home Assistant restart.

### Roll back after activation

Use `rollback_deployment` only when the controller marks the exact deployment as
rollback-required and the rollback restart has separate authority. The controller
chooses and verifies the predecessor; the companion does not accept an arbitrary
package or target.

### Queue a later prepare

Use `queue_prepare_version` only when the controller reports the queue capability as
enabled. Record its returned queue ID. `cancel_queued_prepare` applies only before the
controller claims that entry. Queue admission is not preparation, activation,
deployment, observation acceptance, baseline acceptance, publication, or release.

## Update and rollback the companion

### Update

1. Select a maintainer-published release in HACS, or allow the maintainer-selected
   automatic update policy to download it.
2. Record the previous and downloaded companion versions.
3. Restart Home Assistant under the applicable maintenance authority.
4. Verify the active version, eleven entities, eight actions, supported status schema,
   fresh signed feed, and controller readiness.

### Roll back

1. In HACS, choose the previously proved companion release and download it.
2. Restart Home Assistant under a separately approved rollback gate.
3. Re-prove the active companion version and the complete entity/action/status
   contract.

HACS rollback changes the companion package only. It does not roll back an external
controller deployment. The controller's separate recovery bootstrap remains a
maintainer-governed recovery route, not the normal HACS update path.

## Install the optional read-only dashboard

The template at [`dashboards/hi-lab-operations.yaml`](../dashboards/hi-lab-operations.yaml)
is an optional presentation surface. It uses only core **Sections**, **Heading**,
**Markdown**, **Conditional**, **Tile**, **Entities**, and **Button** cards and native
attribute rows. Its Markdown header displays the repository's official companion
artwork and controller mark from a Home Assistant-local asset. It has no custom-card,
theme, JavaScript, external-network, or controller dependency beyond the companion's
eleven native entities.

### Import as a new dashboard

1. Complete companion installation and confirm all eleven entities exist.
2. Copy
   [`assets/hi-lab-controller-companion-dashboard-header.png`](../assets/hi-lab-controller-companion-dashboard-header.png)
   to `/config/www/hi-lab-controller/companion-dashboard-header.png` on the target Home
   Assistant. Keep the file local to Home Assistant; do not replace it with a remote
   image URL. The header is intentionally public artwork because files under `/local`
   are not an authenticated evidence surface. If `/config/www` does not already
   exist, Home Assistant can require a restart before serving it; omit the artwork or
   obtain separate restart authority rather than restarting as part of dashboard
   import.
3. In Home Assistant, open **Settings → Dashboards** and create a new dashboard in
   storage mode. On the dedicated private HA Lab, make the dashboard **Admin only**;
   its Evidence view contains live operational identities and diagnostics.
4. Open the new dashboard, choose **Edit dashboard → three-dot menu → Raw
   configuration editor**.
5. Copy the complete contents of
   [`dashboards/hi-lab-operations.yaml`](../dashboards/hi-lab-operations.yaml), replace
   the editor contents, save, and reload the dashboard once.
6. If Home Assistant changed an entity ID after an operator rename, replace each
   documented default ID with the matching registered entity. Do not substitute a
   helper, template sensor, or controller-private identity.

The template uses responsive Sections headers, two-column section spans, section
backgrounds, native Tile colors, and card grid sizing. At widths where two section
columns fit, cards expand into available cells and the validation/outcome, queue, and
evidence groups use the full view width. Narrower content widths collapse cleanly to
one readable column. **Use
Home Assistant 2026.4 or newer for the template exactly as
shipped; 2026.4 introduced section backgrounds.** Earlier frontends are outside this
template's validated presentation contract. It follows the installed Home Assistant
theme; the navy, teal, and amber
[public preview](images/hi-lab-operations-dashboard.svg) is an illustrative identity
concept, not an imported Home Assistant screenshot or a promise of pixel-identical
rendering under every theme and viewport.

The integration bundles its official controller mark under `brand/`, so Home Assistant
2026.3 and newer can use it on integration and device surfaces. The dashboard header
uses the official wide companion artwork in a darker dashboard-tuned treatment from
the explicit local `www` copy because
Lovelace YAML cannot portably request the authenticated brand image endpoint. That
artwork incorporates the controller mark without the small icon's package-background
treatment. State tiles retain native MDI icons so condition meaning remains clear at
small sizes. Evidence attribute rows use representative MDI icons rather than a
repeated generic marker. The original README header remains unchanged; the public
preview uses the same official identity.

Home Assistant view visibility is presentation, not an access-control boundary: a
hidden view can still be reached by direct URL. Keep dashboard access Admin only and
do not publish or share screenshots, exports, or raw YAML captured from the live
**Evidence** view. The repository preview uses synthetic public-safe identities only.

The imported **Operations** and **Evidence** views appear as native Home Assistant
tabs. Operations is deliberately calm and scannable, with full-width historical
contact and accepted-baseline truth plus a wide validation, outcome, and queue area.
Evidence carries the selected exact controller attributes in navy, teal, and amber
groups that would make the operational glance too dense. The
repository illustration previews that navigation model, but is a static public-safe
image rather than a second dashboard implementation.

The version-neutral **Open Actions tool** label works across that naming change. The
template keeps the 2026.4-compatible internal path, which current frontends redirect
to **Tools → Actions**.

### Verify truth and responsive layout

After import:

1. Compare every tile with **Settings → Devices & services → HI Lab Controller**.
   Exactly the same eleven entities should appear; no helper or derived entity is
   required.
2. Confirm the **Operations** view uses green only for an expected or clear state on
   that tile, amber for attention or incomplete lifecycle acceptance, and red for
   stale, invalid, blocked, degraded, or unavailable truth. Cyan, teal, and blue-grey
   are neutral evidence colours. No tile colour declares overall health. Colour is a
   second signal; text, state, and icon must remain understandable without colour.
3. Confirm a non-`fresh` **Feed** shows the feed-attention card and its exact raw state.
   `stale`, `missing`, `invalid_signature`, `schema_mismatch`, `clock_invalid`,
   `unknown`, and `unavailable` must not look healthy.
4. Confirm `BLOCKED` readiness, a non-`CLEAR` mutation lock, an unavailable restart
   fact, and `BLOCKED`, `DEGRADED`, `UNAVAILABLE`, and `DISABLED` queue states remain
   visibly distinct. `DISABLED` is the blue-grey safe default rather than a fault.
5. Confirm **Active deployment**, **Pending deployment**, and **Accepted baseline** are
   displayed separately. The dashboard must not infer baseline acceptance by comparing
   identities.
6. Check both **Operations** and **Evidence** at tablet and mobile widths. Operations
   should use two balanced columns where the available content width permits, collapse
   to one column at narrower widths, and show no orphaned half-width card beside an
   empty cell. Historical contact, accepted baseline,
   validation coverage, terminal outcome, queue explanation, and the Actions card
   must remain readable without horizontal scrolling. Evidence attribute rows may wrap
   but must remain readable. This check remains release evidence until the exact YAML
   is imported and rendered in Home Assistant.
7. Open the raw configuration again and confirm there is no `custom:` card, service
   call, hold action, or double-tap action. The sole `tap_action` must be `navigate`
   with the exact path `/config/developer-tools/action`.

The Markdown and conditional cards only present direct entity states and documented
attributes. They do not decide readiness, validate a deployment, resolve a lock,
approve a restart, dispatch queue work, or accept a baseline. Administrator actions
remain separately documented under [The eight administrator actions](#the-eight-administrator-actions)
and are intentionally absent from the dashboard. **Open Actions tool**
only opens Home Assistant's native administrator tool; it does not prefill, select, or
execute an action or pass action data. The native tool can retain its own prior editor
state, so always inspect the selected action and fields before use. Admin access and
deliberate action selection remain required.

### Remove or roll back the dashboard

Removing the dashboard or replacing its raw configuration affects presentation only.
It does not unload the integration, change HACS ownership, call the controller, mutate
Home Assistant runtime state, cancel work, restart Home Assistant, or change any
deployment or baseline. Before editing an established view, save its current raw YAML
so the presentation change can be reversed exactly. The optional local dashboard
header can be removed separately after the previous dashboard configuration has been
restored.
