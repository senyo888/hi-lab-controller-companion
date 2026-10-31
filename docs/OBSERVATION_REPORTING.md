# Integration observation reporting

The **0.5.0-beta.1 source candidate** adds an optional observation feed from the native
controller. It is not published or installed by these source changes. Existing
deployment status, actions and baseline entities retain their original meanings.

| New sensor | Meaning |
| --- | --- |
| Observation feed | Fresh, stale or unavailable reporting; not integration health |
| Observation integration | Selected integration and expected reference, including while idle |
| Observation campaign | Controller-authored IDLE or campaign state, counts, checkpoint times, results and report ID |
| Observation last result | One retained terminal result, explicitly historical, with its original integration/reference and finish time |

An expired legacy Feed can coexist with fresh observation reporting. Neither revives
the other. RUNNING means the campaign is running; IDLE means no current campaign, not
healthy. Partial, failed, interrupted and unavailable outcomes remain visible. A PASS
means all required reported-health checkpoints passed, not continuous health, loaded
source attestation, deployment ownership or baseline acceptance.

## Pairing after separately approved installation

Use the integration's Options to enable reporting and supply the controller owner's
instance UUID, stream epoch UUID and separate 64-character lowercase hexadecimal key.
These are private configuration; never paste a key into issue reports or dashboards.
The controller owner separately provisions its matching publisher and verifies the
dedicated Lab route plus an HA administrator credential. Options do not start a soak,
enable the controller publisher, or authorize a deployment/restart.

The fixed authenticated endpoint is `/api/hi_lab_controller/observation/v2`. It accepts
only the closed signed observation envelope. No command, service invocation, target,
Git ref or native confirmation token is accepted. The signature domain is distinct
from legacy status and actions. Instance and epoch must match explicit pairing;
unknown streams never auto-enroll. The payload schema is supplied in
[`integration-observation-companion-v2.schema.json`](../schemas/integration-observation-companion-v2.schema.json).
Schema validation alone is not authentication or replay protection.

The publisher reserves each sequence durably. The companion admits private filesystem
custody and commits the accepted sequence/body digest before acknowledgment or entity
publication. It retains replay state under the dedicated `.hi_lab_controller/observation-v2`
directory, with owner-only directories/files and descriptor-relative atomic updates.
Unsafe links, changed ancestry, corruption, missing initialized state and write failure
refuse. Partial stages are retained. Physical writes drain before reload can replace
the receiver, including after request cancellation.

Each projection expires at its original deadline, no more than sixty seconds after
generation. Replays and polling cannot renew it. Future-clock allowance is at most
five seconds, and clock discontinuity clears availability. After reload/restart a
higher authenticated sequence is required before current values return. A retained
terminal result is history only. Receiver state holds a replay floor and one terminal
projection per epoch; old epochs are retained until explicit owner maintenance.

Missing custody or restoration of backups requires a deliberate new epoch/key on
both sides. Do not delete replay records to re-enable an old epoch. A shared key
authenticates its holder, not a physical server; HTTP does not encrypt bearer tokens.
This feature does not alter the owner's network security configuration.

## Dashboard and verification

The optional [`integration-observation.yaml`](../dashboards/integration-observation.yaml)
is one native-card section for the existing Operations view. Preview it, preserve a
private dashboard backup, and import through the supported editor only when separately
authorized. It preserves current dashboard sections and actions. The controller app
remains the only Start/Stop surface for this feature.

After authorized delivery, verify pairing, a new signed sequence, exact expiry,
selected profile/reference, actual campaign/checkpoint state and rendered unavailable
states. Check legacy deployment entities independently. A downloaded HACS update,
successful HTTP response or passing offline test is not this live verification.

To roll back presentation, restore the saved dashboard section. Disable observation
reporting before an authorized companion downgrade, preserving replay files. Replacing
the native controller while a campaign runs interrupts it; wait for completion or
obtain its explicit disposition. No automatic restart/resume/catch-up is provided.

## Validation

Pure protocol tests run without Home Assistant. The HA adapter tests require the
pinned validation environment and otherwise report a skip. They use real HA classes,
disposable local files and loopback HTTP with a synthetic authenticated principal,
never an installed Lab or real credential. Cross-repository interoperability additionally
sets `HILC_CONTROLLER_SOURCE` to an explicitly selected controller checkout.
Schema/presentation fixtures require `jsonschema`, `PyYAML` and `Jinja2`. The retained
manual dashboard bundle remains the versioned 0.4.1 eleven-entity contract; the new
four-sensor section is a separate manual artifact, not a rewritten bundle contract.

Implementation uses the supported [HA options flow](https://developers.home-assistant.io/docs/core/integration/options_flow/)
and [authenticated HTTP view](https://github.com/home-assistant/core/blob/2026.9.3/homeassistant/helpers/http.py)
interfaces. Publication still requires the repository's GitHub HACS/Hassfest and
maintainer release gates. Installation, restart and rendered live verification remain
separate from source validation.

Checkpoint UTC bounds allow 2.001 seconds for the engine's existing two-second
wall/monotonic tolerance and millisecond timestamp projection. Original timestamps
are preserved; the source still enforces its strict 900-second monotonic window.
Wire validation does not independently prove that monotonic evidence.

The publisher applies one five-second network deadline across connect, TLS and
response phases, with a retained-socket watchdog for trickling responses. It does
not promise hard real-time interruption of kernel, scheduler or CA-file stalls.
Late dispatch/return refuses, and physical request custody is retained until drainage.
