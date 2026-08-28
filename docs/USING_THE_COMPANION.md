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
- eight fixed actions under **Developer Tools → Actions**; and
- persistent notifications for important prepare, queue, activate, discard, and
  rollback results.

There is no custom panel or dashboard in the current release. A future optional
dashboard template may present the native entities, but it must remain read-only and
must not duplicate controller logic.

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
5. Open **Developer Tools → Actions** and confirm all eight
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
| `sensor.hi_lab_controller_last_validation` | Completion time of the latest controller validation | Attributes contain the deployment and installed identity plus Stage B and Stage 3 pass counts and verdicts. It reports evidence; it does not accept a baseline. |
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

Read-only example for **Developer Tools → Actions**:

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

## Optional dashboard direction

The intended dashboard is a presentation layer over the eleven native entities. It
may group feed integrity, readiness, deployment state, queue state, validation,
baseline, and restart truth into an operator-friendly view. It must:

- remain optional and read-only by default;
- use entity states and attributes rather than reproducing controller logic;
- make stale, missing, invalid, blocked, and unaccepted states visually explicit;
- avoid embedding private target identities, credentials, or machine-specific paths;
- keep mutation actions out of casual controls; and
- never imply that a download, restart, active deployment, observation, accepted
  baseline, publication, or release has occurred without controller-owned evidence.

Until that template is separately designed and validated, use the native device page,
entity details, Developer Tools actions, and controller evidence as the supported
surface.
