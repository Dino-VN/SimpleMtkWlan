# Retain early ROC grants through their reserved AW

## Reproduced failure

The previous candidate (`AC1899FF-55E6-31A5-81A7-A11DAA3F041D`, commit
`2b13e56`) loaded correctly but stopped producing AW events. A 30-second
read-only check observed zero new start/end pairs and 60 missing-start warning
records. A separate 20-second observation recorded 20 ROC submissions,
19 response timeouts, one accepted grant and one rejected event.

The saved radio timestamps identify an accepted reservation being replaced
before its original target:

| Observation | Monotonic time, microseconds |
| --- | ---: |
| Token 148, channel 6, submitted | 543910283 |
| Matching grant received | 544368338 |
| Grant expires | 545438338 |
| Reserved AW starts | 544910259 |
| Reserved AW ends | 544975795 |
| Token 149, channel 36, submitted | 544434567 |

The grant covered the entire original AW. The next request replaced it
475692 microseconds before that AW. The controller and interface publish
diagnostics asynchronously; these timestamps are evidence of replacement,
not a trace of the exact call stack. The production scheduler regression
reproduces the replacement using those times, with channels mapped to the
test HAL's supported channels.

## Change

Before moving the planning horizon to `now + reserveLeadUS`, the scheduler
checks whether the current, observed firmware grant still covers its original
future AW. It keeps that grant through idle slots and slots on other channels
until the reserved edge. The check compares the original window's channel,
counter, presence, start and end against the current schedule.

An intermediate AW on the same granted channel can still start. Its early
switch path also preserves the later reservation instead of aborting the
grant to prepare an adjacent channel. The original future AW is never
announced early: production start handling still requires a current edge,
an observed matching grant, and enough real grant duration.

Expired/insufficient grants, revoked grants and changed target coordinates
allow replanning. Explicit native control changes retain their existing
abort/deferral behavior. This change does not invent grants or skipped AWs,
relax counter continuity, or change firmware response timeout policy.

## Validation

The added timestamp replay fails on the previous production scheduler at
the assertion that the valid original grant must remain reserved. It passes
with the fix, emits no event before the original AW, then produces one
start/end pair at its actual edges. Additional regressions cover an
intermediate same-channel AW, expiry before the target, changed target
channel, and changed counter with an otherwise identical channel index.

An eight-second sparse-schedule model uses a one-second preparation lead
and varying 3, 97, 458.055 and 980 ms grant response delays:

| Production scheduler | Starts | Ends | ROC requests |
| --- | ---: | ---: | ---: |
| Previous candidate | 6 | 6 | 13 |
| Fixed candidate | 11 | 11 | 7 |

Every modeled start checks live matching RF ownership; each end stays within
the native presence-4 duration tolerance of 54–74 TU. The existing dense
500 ms model remains at 10 starts / 10 ends in six seconds. These are
controlled tests, not hardware or completed AirDrop transfer results.

All ten AWDL test groups pass, including production event/scheduler execution
under AddressSanitizer and UndefinedBehaviorSanitizer. The macOS Tahoe
x86_64 Release build succeeds. Static native ABI validation reports are
included in the build package.

## Hardware follow-up

The high firmware response timeout rate remains unexplained by this fix.
Holding an early valid grant removes the reproduced scheduler starvation,
but cannot guarantee every different-channel AW with 0.5–1 second response
latency. Continuous hardware operation and AirDrop file transfer require a
fresh measurement after the user updates the kext and boots normally.

The candidate UUID is `4BFBB896-4A91-3BC0-8443-0A7D8CBA6576`. Its executable
SHA256 is `713003e839bc2cfddb85e70a1cf005cb6738b9671cbd57d7b76f34b3e0f9616c`.
The previous runtime reports remain under `build/awdl-native-contract-fix/`;
new regression, build and ABI evidence is under
`build/awdl-reserved-grant-fix/`.
