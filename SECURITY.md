# Security policy

## Supported version

Security fixes target the latest GitHub release.

## Report privately

Please use GitHub's private vulnerability reporting for this repository. Do
not open a public issue for secrets, command injection, unsafe hook rewrites or
configuration loss.

Include the affected version, agent, operating system, minimal reproduction
and expected safe behavior. You should receive an acknowledgement within 72
hours.

## Boundaries

- Hooks never bypass an agent's approval or sandbox policy.
- Unsupported compound shell commands are left unchanged.
- Existing JSON settings are backed up before merge.
- The installer does not install third-party tools or send telemetry.
- Token estimates are not provider billing records.
