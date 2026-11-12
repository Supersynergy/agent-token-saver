# Security policy

The maintained source is the TypeScript/Bun product described in README.md.
Historical reports are retained as data; they do not establish current support
for the retired hooks or provider adapters.

Report vulnerabilities through GitHub private vulnerability reporting. Include a
small sanitized reproduction, expected behavior and affected source revision.

## Boundaries

- ATS does not change agent permissions, approval policy, sandbox or host hooks.
- Commands execute as an argument list. ATS does not interpolate them into a shell.
- The installer and rollback operate only when `--apply` is present.
- Installation keeps prior starters and generation receipts. Rollback refuses later edits.
- Raw logs are local and can contain secrets printed by the invoked command.
- `verify` is noninteractive. Its timeout kills the direct child; it does not guarantee
  termination of processes deliberately detached by that child.
- RTK is optional external software. The comparison disables its telemetry in an isolated
  home and passes only synthetic fixture text. ATS does not install RTK or trust plugins.
- Byte counts and supplied-price calculations are estimates, not provider invoices.

No global installation or live host acceptance is implied by passing source tests.

A command can print a credential into a log even when ATS itself has never read
a configuration file or contacted a provider. Keep those artifacts local until
their contents have been checked.
