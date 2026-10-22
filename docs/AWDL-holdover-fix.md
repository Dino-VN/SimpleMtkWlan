# Selected-clock holdover and AW channel switching

## Hardware baseline

The installed `795af6b` binary, UUID
`9990449F-531D-328E-8FFC-C9D8FCBCE823`, accepted 319 of 328 submitted ROC
responses on the 2026-10-22 20:36:45 +07:00 boot. There were zero rejected
events and five response timeouts. Those counters do not establish firmware
denial of the other submissions or timely radio availability. The maximum
accepted response delay was 998120 us.

The capture contained 267 starts and 267 ends, 163 skipped-start reports,
four counter failures, four spacing failures and two explicit missing-start
errors. AW activity then stopped while service ticks and action RX continued.
The selected synchronization parent expired; unrelated peer RX did not
replace it. Native synchronization remained enabled, effective role was 2,
host channel was zero and reservation attempts stopped advancing. Reopening
AirDrop still produced no new AWs in the subsequent 30-second observations.
The last recorded AW duration was 59.315 ms; no end-duration sanity failure
was found in that boot capture. Sustained AW coverage and data transfer failed.
Evidence is retained in `build/awdl-roc-fix/runtime-summary.json` and its
associated runtime context/property captures.

## Changes

- A native-selected clock whose peer RX cache expires now enters holdover.
  The host retains its counter, phase, native channel sequence, parent and
  root instead of setting the follower's channel to zero and stopping ROC.
  Entry requires a previously validated clock for that exact native parent.
  A missing initial parent or a new parent with a rejected clock cannot
  inherit holdover. Fresh compatible observations resume bounded phase
  tracking at a safe AW edge. A non-election master retains its own tree
  even when the previously selected peer remains in the RX cache.
- The secondary BSS RLM is initialized once. Temporary channel changes use
  ROC's channel/band/width fields directly, avoiding a synchronous BSS update
  at each switch. Linux `mt7921_remain_on_channel` similarly submits ROC
  without reprogramming RLM. An accepted matching token/channel and its real
  returned lifetime still gate TX. The TX node uses the requested channel.
- Early AW-end uses native's full 10-TU duration tolerance after subtracting
  start lateness. The timer wakes at that preparation edge instead of relying
  on a 2-ms polling interval. After closing an AW early, planning explicitly
  skips that completed window. This matters for short presence modes, where
  the old window can still lie inside the 8-ms start tolerance.
- The runtime checker also fails on native `Did not get AW start event`
  warnings. Previously, a warning-only missing-start capture could be
  classified merely as unverified. Wrong UUID or empty activity without
  failure evidence remain unverified.

Holdover does not refresh peer membership, claim RF synchronization, invent
received data, or announce AWs without a real firmware grant. It continues
while native keeps that selected parent and synchronization enabled. Its
phase may drift without fresh peer observations; no maximum drift is proven
by these tests. Diagnostics expose holdover state/transitions, selected and
clock parent, selected-clock validation, selected-peer liveness and the BSS
base channel. Liveness/clock validation do not prove over-the-air sync.

## Validation

Nine relevant suites pass, with ASan/UBSan execution of production protocol,
scheduler and HAL handlers. Tests cover five seconds of selected-parent
expiry, continuing unrelated RX, counter rollover, exact advancing wire
counters, start spacing within 5 TU, end duration within 10 TU, compatible
peer return, missing/incompatible replacement parents, and multicast/action
use under actual modeled grants. Expired peer entries stay expired.

The same final harness fails when only the old expiry behavior is restored
or the preparation-edge timer scheduling is removed. Before-fix logs are
`build/awdl-holdover-fix/regression-holdover-before.log` and
`regression-switch-edge-before.log`.

The channel-switch comparison models 15.019-ms synchronous RLM waits and
13.424-ms ROC response latency across groups of four same-channel windows.
It yields 47 starts with RLM waits versus 62 with ROC-only switching in four
seconds. The latter has continuous counters, native-compatible spacing and
duration. These are simulated results, not new hardware measurements.
The timer sweep also verifies 84 combinations of presence 1/2/4/8/16/32/64,
3/8-ms ROC latency and 0/250/750-us dispatch jitter, checking individual
counter/channel/timestamp/duration records rather than balanced totals alone.
HAL tests verify exact ROC packets and that a 504334-us RLM callback cannot
run on subsequent temporary switches.

Release builds for Tahoe x86_64. Static ABI checks cover 569 AWDL and 244
packet/pool/queue slots. Artifact identity and final check results are in
`build/awdl-holdover-fix/verification.json`.

## Remaining hardware checks

The candidate must be installed and loaded through the existing normal-boot
workflow, then measured with both AirDrop devices active. Stable-base RLM
with secondary IBSS data TX on a different granted channel still needs
MediaTek hardware confirmation; the Linux command sequence is supporting
evidence, not proof for this BSS configuration. Firmware responses slower
than the physical switching budget can still miss nonzero AWs, and true
grant loss/reset/disable can truncate a window. Native warmup adoption of
another master's discontinuous counter is unchanged. Successful sustained
AW coverage and AirDrop file transfer are unverified on this candidate.
