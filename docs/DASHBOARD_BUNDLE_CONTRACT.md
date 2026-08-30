# Manual dashboard bundle contract

Status: `ACCEPTED_DESIGN_ONLY_NOT_RELEASED`

The HI Lab operations dashboard is distributed as a versioned, inspectable bundle
contract. The bundle binds the canonical dashboard YAML, its public assets,
compatibility limits, and the eleven companion entity semantics to exact repository
bytes. It does not add a Home Assistant control path.

The checked-in example manifest is
[`examples/dashboard-bundles/hi-lab-operations.manual.v1.json`](../examples/dashboard-bundles/hi-lab-operations.manual.v1.json).
Its schema is
[`schemas/dashboard-bundle.schema.json`](../schemas/dashboard-bundle.schema.json).
The example has `contract_example` lifecycle status: it demonstrates and validates
the contract, but is not proof of a GitHub release, HACS delivery, a Home Assistant
installation, or a live dashboard import.

Controller decision `HILC-ADR-20260830-006` accepts the cross-product delivery
boundary as design only and closes `HILC-PROP-20260830-001`. This companion
repository remains the sole editable source for the bundle contract and canonical
dashboard. The decision does not change the example's `contract_example` lifecycle
or authorize implementation, import, installation, publication, or release.

## Contract boundaries

- The companion repository owns this manifest contract and the dashboard files it
  names. Controller and companion releases remain separate.
- HACS owns companion integration installation and update. Dashboard import is a
  separate, manual administrator action; the bundle does not claim HACS installs or
  updates dashboards.
- `dashboards/hi-lab-operations.yaml` remains the canonical importable dashboard.
  The manifest describes that file; it is not a second generated dashboard.
- `capabilities.dashboard` remains `false`. The bundle is presentation metadata and
  does not change signed status truth, entities, actions, polling, or runtime
  behavior.
- The contract forbids automatic installation, browser automation, direct Home
  Assistant saves, and direct `.storage` writes. It carries no credentials, target
  URL, dashboard identifier, or machine-specific path.
- Only Home Assistant's supported dashboard editor may be used for a manual import.
  The bundle never calls an action or service, reloads Home Assistant, or restarts
  it.

## Manifest contents

Contract major 1 records:

- bundle identity, version, and lifecycle;
- canonical companion repository plus exact source commit and tag for released
  bundles; contract examples keep both identities null rather than invent release
  evidence;
- SHA-256 digest, byte size, path, and media type for the canonical YAML and each
  public asset;
- minimum and maximum-tested companion versions, Home Assistant,
  signed-status-schema, and core-card compatibility;
- the fixed entity-semantic set, including default entity IDs and registry unique
  IDs; and
- mandatory manual-delivery safeguards.

Repository paths are relative and resolve from the repository root. The header
asset's `/local/...` value is a Home Assistant public URL target, not a filesystem
write instruction. The SVG is an illustrative public-safe preview; the YAML remains
the import authority.

Any change to a bound file requires a new bundle version and updated digest and byte
size. Increment the contract major for an incompatible field or meaning change.
Use a bundle major change for incompatible entity semantics or import expectations,
a minor change for compatible assets or compatibility metadata, and a patch change
for a compatible metadata or digest correction. A manifest with
`contract_example` lifecycle must not be described as released or installed.
A manifest with `released` lifecycle requires both the immutable source commit and
the maintainer-created release tag.

The canonical UTF-8 JSON representation of a manifest must not exceed 64 KiB. A
bundle title is limited to 160 characters, the asset list to sixteen entries, each
repository path to 256 characters, and each declared artifact to 32 MiB. Consumers
must reject an over-limit manifest before allocating for or copying a declared
artifact. These limits bound contract parsing; they do not authorize artifact
installation or relax the separately verified digest and byte-size requirements.

## Manual-first import and rollback

1. Install or update the companion integration through HACS as a separate task, then
   confirm the companion domain and version satisfy the manifest.
2. Verify the manifest against the schema and recompute every declared digest and
   byte size. Inspect the raw YAML and the illustrative preview before selecting a
   Home Assistant dashboard.
3. In Home Assistant, inspect the destination dashboard and privately export or copy
   its current raw configuration and identifying details. Do not commit that backup;
   it can contain private entity IDs and local layout choices.
4. Present the intended destination, compatibility result, file changes, and rollback
   copy to the administrator. Continue only after explicit confirmation.
5. Using the supported Home Assistant dashboard editor, manually replace or create
   the destination raw configuration from `dashboards/hi-lab-operations.yaml`. Copy
   the required header image to the documented `www/hi-lab-controller/` location by
   an administrator-controlled file workflow.
6. Immediately read the saved raw configuration back through the supported editor.
   Compare it with the reviewed source, confirm both views render, and verify all
   eleven entities expose companion truth. Treat unknown, unavailable, or stale
   values as evidence, not success.
7. If verification fails, manually restore the private backup through the supported
   editor and read it back again. Removing the optional dashboard changes
   presentation only.

Entity IDs can be renamed by Home Assistant or an administrator. If a reviewed
manual mapping is necessary, record it privately and verify every replacement during
readback. The repository manifest continues to describe the canonical default entity
set; it must not absorb private entity IDs.

Future setup-assistant work would require a separately approved contract and Home
Assistant-supported save mechanism. This manual contract does not authorize or
simulate that implementation.
