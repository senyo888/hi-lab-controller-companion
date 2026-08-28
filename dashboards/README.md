# Optional dashboard gallery

## HI Lab operations

![Illustrative public-safe preview of the HI Lab operations dashboard](../docs/images/hi-lab-operations-dashboard.svg)

[`hi-lab-operations.yaml`](hi-lab-operations.yaml) is the canonical importable
template. It pairs a responsive, semantically colored **Operations** tab with a
separate exact-attribute **Evidence** tab. Both are read-only surfaces over the
companion's eleven native entities and use only built-in Home Assistant cards. One
compact **Open Actions tool** control is navigation only; it cannot
prefill or execute an administrator action or service call. The template exactly as
shipped requires Home Assistant 2026.4 or newer.

See [Using the companion](../docs/USING_THE_COMPANION.md#install-the-optional-read-only-dashboard)
for import, compatibility, responsive-layout checks, truth verification, and
presentation-only rollback.
