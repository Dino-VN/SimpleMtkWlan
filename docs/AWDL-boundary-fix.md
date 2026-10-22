# AW control transitions and counter continuity

The software-events candidate `E3C52587-6E7C-379C-B6F4-69B53D886FCE`
was loaded on the 2026-10-22 19:23:22 +07:00 boot. Its 30-second runtime
capture recorded six starts/six ends but ten native sanity failures, including
0/10/20-TU ends, missing windows and a counter jump. Data reached HAL six
times while 130 queued packets expired; no data RX occurred in that interval.
Evidence is in `build/awdl-emulation-fix/runtime-summary.json` and
`runtime-aw-context.ndjson`. The short ends coincide with native opmode/master
or sequence reprogramming. This observation does not identify every setter or
grant path responsible for every failure.

## Changes

The native role, selected parent, channel sequence, presence and social channels
now form a bounded control transaction while an AW is open. Valid setters
record their latest requested values and return without ending or revoking the
current grant. Peer RX remains cached but election cannot mutate the active
radio schedule. AW-end uses the recorded real radio/schedule boundary; after
native consumes it, the latest controls commit together. Outgoing synchronization
TLVs and native AW events retain the same effective schedule until then.

Synchronous end callbacks can add to the transaction. Reentrant service cannot
open another AW before that transaction finishes. An early close for preparing
another channel stays within the existing 10-TU duration tolerance; the closed
physical EAW cannot reopen with a different role/master payload. Actual grant
loss, disable or reset still terminates an AW at the observed time. Missing RF
time is never represented as an extended or fabricated native window.

The native-selected clock identity is separate from effective election role.
Repeated role changes or temporary parent expiry cannot readopt that parent's
AW counter. Initial native selection may adopt a peer clock before any AW has
been announced. After a timeline begins, observations from even a different
parent receive bounded phase discipline: at most 512 us per fresh observation,
with discontinuities greater than 5 TU rejected. No AW payload-only counter
translation or replay is used. A genuinely incompatible parent clock may
therefore still need peer convergence or a new synchronized session; rejecting
its discontinuity preserves continuity but does not establish radio sync.

Accepted ROC response latency now travels with the grant snapshot. The
scheduler grows its lookahead from 55 ms up to 125 ms using that latency plus
the preceding HAL/RLM wait and an 8-ms margin. It can prepare earlier in an
idle interval, without starting the next AW early or truncating an open one.
`MTKAWDLReserveLeadUS` exposes the bound; `ControlsDeferred` and
`ControlsPending` expose staged changes. The previous physical-offload fix
remains included.

## Validation

The old code fails both new regressions: native role changes readopt a counter
of 224, and opmode changes inside an AW produce a short end. Failure output is
retained under `build/awdl-boundary-fix/regression-*-before.log`.

Eight relevant suites pass. Production scheduler/event tests with ASan/UBSan
cover changes at 0/10/20 TU, same-parent role toggles, new-parent selection,
unrelated counter rejection, counter rollover, sequence/presence/social-channel
updates, synchronous start/end callbacks, revocation/reset, and wire TLVs.
Forty-two consecutive EAW starts maintain counter increments and native start
spacing/end-duration tolerances while controls change every window. A modeled
97-ms off-channel grant delay with enough intervening idle time produces all
four target off-channel starts in two sparse schedule cycles. The 97-ms value
comes from the earlier measured maximum, but the regression is a simulation.

Release x86_64/Tahoe build and 569 + 244 static native ABI slots pass. UUID,
hash, source commit and test results are in
`build/awdl-boundary-fix/verification.json`. This candidate has not been loaded;
no install, hot-unload, OpenCore modification or reboot was performed here.

## Runtime limits

Native counter/timing correctness is still unverified on this candidate's
hardware run. A 97-ms firmware response between adjacent different-channel
AWs exceeds the available switching interval; lookahead cannot reserve both
channels concurrently. Scan arbitration, rejected grants and synchronous HAL
waits as large as 372 ms remain potential sources of missing nonzero windows.
This patch cannot guarantee complete AW coverage under those conditions or
prove an AirDrop file transfer. Validate the new UUID on normal boot and
measure actual AW events and data traffic before marking either fixed.
