# HI Lab Controller Companion agent rules

This public repository owns only the Home Assistant-side `hi_lab_controller`
companion. The external HI Lab Controller remains a separately governed private
control plane.

## Hard boundaries

- Keep the domain `hi_lab_controller`, display name `HI Lab Controller`, config-entry
  identity, action names, entity identities, and signed-status semantics stable.
- The companion may authenticate an administrator, write signed requests to its fixed
  local mailbox, read signed status, and request a restart only after the external
  controller approves the exact activation or rollback.
- Never add Git, SSH, repository discovery, arbitrary URL/ref/path/target selection,
  package assembly, provider credentials, deployment policy, or release authority.
- Never include secrets, tokens, private target identities, addresses, local machine
  paths, runtime evidence, or real shared-secret values.
- Missing, stale, malformed, unsigned, incompatible, or permission-unsafe status must
  remain unavailable or degraded; UI entities must not reconstruct controller truth.
- HACS is the normal installation and update owner. Automatic HACS updates are
  supported, but only maintainer-published releases are eligible. A downloaded update
  is not restart completion, runtime verification, deployment acceptance, or release
  authority for Humidity Intelligence.
- The external controller's transactional bootstrap is recovery-only after HACS
  ownership is intentionally reconciled. Do not create two concurrent package owners.

## Validation

Run:

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q custom_components tests
git diff --check
gitleaks git --redact --no-banner .
```

HACS Action and Hassfest must also pass on GitHub before a release is treated as an
installable companion candidate.
