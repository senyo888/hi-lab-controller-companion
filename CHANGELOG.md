# Changelog

## 0.4.1 - 2026-08-28

- Established the companion as an independently versioned custom-HACS integration.
- Added public-safe repository, architecture, security, validation, and branding
  surfaces.
- Corrected documentation and issue routes to the companion repository.
- Declared the integration as config-entry-only and removed invalid legacy uppercase
  enum translation maps without changing the underlying entity state values.
- Preserved the existing eight actions, eleven entities, status-schema-major 1 and 2
  support, local signed-mailbox protocol, and fail-closed behavior.
- Enabled the release-only HACS update channel, including operator-selected automatic
  updates. A HACS download still requires separate restart and runtime verification.
- Added no Git, SSH, provider, source-selection, package, target, deployment, baseline,
  Humidity Intelligence release, or Stable authority to Home Assistant.
