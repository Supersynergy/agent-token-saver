_default:
    @just --list

check:
    bun run check

pre-pr: check
    bun tools/release.ts audit
    osv-scanner scan source -r .
