_default:
    @just --list

# Schnellpruefung: Lint, Format, Test.
check:
    uv run ruff check .
    uv run ruff format --check .
    uv run pytest -q

pre-pr: check
    gitleaks detect --source . --redact
    osv-scanner scan source -r .
