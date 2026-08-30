# Optional dashboard gallery

## HI Lab operations

![Illustrative public-safe preview of the HI Lab operations dashboard](../docs/images/hi-lab-operations-dashboard.svg)

[`hi-lab-operations.yaml`](hi-lab-operations.yaml) is the canonical importable
template. It pairs a responsive, semantically colored **Operations** tab with a
separate exact-attribute **Evidence** tab. Both are read-only surfaces over the
companion's eleven native entities and use only built-in Home Assistant cards. One
compact **Open Actions tool** control is navigation only; it cannot
execute an administrator action or service call, and it supplies no action data. The
native tool can retain its own prior editor state. The template exactly as shipped
requires Home Assistant 2026.4 or newer. Its Operations header displays the official
companion artwork and controller mark from the fixed local path
`/local/hi-lab-controller/companion-header.png`; copy
`assets/hi-lab-controller-companion-header.png` to the matching Home Assistant
`www/hi-lab-controller/` directory as part of import.

See [Using the companion](../docs/USING_THE_COMPANION.md#install-the-optional-read-only-dashboard)
for import, compatibility, responsive-layout checks, truth verification, and
presentation-only rollback.
