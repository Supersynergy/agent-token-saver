# ATS: TypeScript/Bun and task-specific evidence

Date: November 12, 2026. Status: implemented locally and published in the 5.1 line.
No automatic host rollout.

## Context

The redesign request required TypeScript/Bun and an account of which earlier
optimizations helped. Version 5.0 retained old Python and shell files;
5.1 retired that maintained surface after archiving existing local changes.

## Decision

Use one Bun entry for checks, bounded views, explicit cost arithmetic and help.
The installer and rollback use TypeScript. Starters are symlinks to a Bun-shebang
file. Remove providers, hook profiles and automatic routers. Keep historical
measurement data, current command descriptions and an explicit migration map.

Compare RTK on eight synthetic task contracts. Select a candidate only if all
required literals survive and the byte count decreases. Rejected or unavailable
candidates retain raw output. This does not prove semantic equivalence or lower
provider bills.

## Consequences

The product gate combines strict types and Bun behavior tests. The retired
Python gate disappears with its implementation. Tests cover failure paths and
installation in a temporary home. Live RTK measurements stay separate from
controlled tests so RTK is not a mandatory dependency.

No global host configuration or paid model run follows from this source change.
Existing v4 hooks need their own migration. A mechanical port of every old special
case would recreate the breadth that the redesign was intended to remove.
Version 5.1.1 updates the English presentation and shipped guidance without
changing these boundaries.
