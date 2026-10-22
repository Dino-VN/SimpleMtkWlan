# Native AW clock acquisition, disable duration and ROC preparation

The loaded `726c2cf` build registered awdl0 and exchanged real AWDL packets,
but its 30-second capture still contained 13 paired starts/ends, 7 skipped-AW
sanity failures, 11 missing-start errors and 43 missing-start warnings. The
selected clock remained unvalidated with 78 rejected observations. Accepted
ROC responses reached 984069 us, with the final response taking 463668 us.
The retained baseline is `build/awdl-interface-ready-fix/runtime-summary.json`.

## Clock acquisition

Local warmup windows previously prevented first acquisition of the native
selected peer's counter namespace. A legitimate counter far from the local
counter then failed the 5-TU drift limit indefinitely. Explicit native
selection now authorizes acquisition of that parent/root at an AW boundary.
The same acquired clock is used for wire advertisements and native events.
Repeated selections of the current tree do not authorize discontinuous drift;
ordinary RX still uses the existing 5-TU rejection and 512-us slew bounds.
Deferred selection records its parent/root and cannot adopt another tree
arriving while the old AW closes. Selecting the current tree again cancels a
pending change. Aborting an old unannounced reservation clears its clock hold.

The advertiser handler also used to overwrite a newer peer epoch with an older
cached native PSF while retaining the newer observation time. It now preserves
the newer same-tree sample, or restores the selected sample with its original
time when changing trees. Diagnostics expose acquisition count and pending
state. Native `programChipWithNewMaster` saved in
`build/awdl-roc-fix/native-master-control.txt` supplies counter/down/timestamp;
this is static native evidence, not a new REA execution or hardware result.

## Administrative disable

The boot's 41-TU duration failure occurred at 21:44:02 immediately after native
`disableAWDL`, inside an open 64-TU AW. Disable now stops new traffic and waits
on the command gate until the actual elapsed AW reaches native's lower
duration tolerance (54 TU for 64 TU), provided the exact grant token, channel,
observation and deadline remain valid. Each wait is at most 10 ms; the total
is bounded by the real AW duration (up to 1024 TU at presence 64).

Gate sleep releases ownership; concurrent sync requests remain serialized.
Unexpected sleep status, teardown, reset or grant revocation ends promptly
with the actual observed time. HAL is not reentered after teardown. No future
timestamp, fabricated grant, exempt flag or synthetic start is introduced.
If disable originates on the workloop thread, that thread waits; other gated
callers can run, but workloop event servicing may be delayed. Grant snapshots
are checked at each wake. Native callback/workloop behavior still needs hardware
validation. Genuine loss of RF may still produce a truthful short AW.

## ROC preparation

Adaptive lead was capped at 125 ms despite observed responses near one second.
It now follows measured response delay plus synchronous submission wait and
8 ms margin, bounded by the one-second response timeout. Idle gaps can use
this lead without changing the native channel sequence or announcing early AWs.
An old same-channel grant ending in the idle gap no longer postpones renewal
past the next request edge. A shortened grant for the target retains its token
and usable partial TX time rather than being replaced every tick.

The new regression fails with the old grant-retention condition. Restoring
the 125-ms cap independently fails the 500-ms response/590-ms idle-gap case.
Tests exercise production methods, real elapsed-time disable waits, recursive
gate release, concurrent revocation and detach, clock wrap, stale sample
replay, selected root identity, normal short grants and matched event pairs.
Ten relevant suites, the Release build, 569 AWDL and 244 Skywalk static ABI
slots pass. Build and test records are in `build/awdl-clock-disable-fix`.

## Hardware validation still required

This candidate is packaged for a normal user update; it has not been installed
or loaded by this task. Check its UUID before measuring selected-clock
validation, AW-start/end pairing, counter/spacing, duration, missing starts and
bidirectional data. Successful AirDrop file transfer remains unverified.

Dense adjacent different-channel 64-TU AWs cannot all be covered when actual
firmware arbitration takes 0.5-1 s. Increased lookahead only helps where the
real schedule leaves preparation time; it does not establish continuous RF
coverage. Active scan arbitration and physical grant latency remain unresolved.
Automatic creation before Wi-Fi association also remains hardware-unverified.
