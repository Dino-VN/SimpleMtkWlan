# AWDL ROC response lifetime and missed windows

## Observed baseline

The loaded boundary candidate `0F6A4065-2F11-33FE-826D-B8416B5C705D`
recorded 556 ROC submissions, 125 events, eight accepted grants and 117
rejected events on the 2026-10-22 20:01:49 +07:00 boot. These are host
acceptance counters, not evidence that firmware denied 548 requests. The
reopened AirDrop observation had four AW-start/end pairs, five native sanity
failures and repeated missing-start errors. Observed ends were approximately
57–65 **milliseconds**, with no duration sanity failures in that sample.
Counter/spacing and AirDrop data transfer remained unsuccessful/unverified.
Evidence: `build/awdl-boundary-fix/runtime-summary.json`,
`runtime-reopened-context.ndjson`, and `runtime-final-properties.json`.

## Confirmed source defects and changes

1. A pending response expired at 100 ms. Linux mt7921 `mt7921_set_roc`
   waits `HZ`, one second. A matching response arriving after 100 ms could
   never be accepted by the old host code, even though firmware could still
   complete it. The bounded asynchronous response timeout is now one second.
   Submission time is stored explicitly instead of derived from a hardcoded
   deadline offset. RF availability still begins at the observed matching
   grant and ends at its actual returned interval.
2. A synchronous BSS RLM wait could outlive the planned AW. Even when HAL
   subsequently submitted a fresh ROC, the scheduler immediately aborted it
   because the original AW had passed. Revalidation now checks the original
   schedule coordinates, role and master identity. A successful live pending
   response or grant for that unchanged channel survives a missed target.
   Schedule changes, failed submission, disable/reset and stale grants still
   invalidate it. A late grant can serve a later covered AW or real partial
   data transmission; it never replays the missed start.
3. An idle slot aborted an already accepted, unexpired grant merely because
   its original target AW had ended. The scheduler now retains both pending
   responses and live grants across idle slots, until expiry or a required
   channel change. Zero-channel slots still produce no AW event or TX.

These three old behaviors fail isolated regressions with the same current
production scheduler harness. Logs are retained as
`build/awdl-roc-fix/regression-{timeout,idle,rlm}-before.log`. A 200-ms response
and a 200-ms synchronous RLM wait reproduce the losses. Their exact role in
all 117 hardware rejections cannot be established from the previous aggregate
counters; the new diagnostic candidate is needed for that attribution.

## Wire decoding and diagnostics

The grant layout is checked against Linux `mt7921_roc_grant_tlv`: tag/length,
BSS, token, status, primary channel, request type, and returned interval. The
bounded decoder walks the complete unified-event TLV body, tolerates unknown
well-framed TLVs, and rejects truncation, wrong lengths, trailing fragments
and duplicate grants before mutating reservation state. Token/channel,
request lifetime, enabled state and maximum dwell checks remain mandatory.
Tokens are quarantined for 2.1 seconds (response timeout plus maximum dwell).

IORegistry publishes `MTKAWDLROCReject*` counts for malformed/no-grant,
wrong BSS, firmware status, request type, disabled, not pending, token,
channel, late and duration failures. `MTKAWDLROCLast*` publishes parsed fields,
result, observation time and elapsed time from the current pending request.
That elapsed time does not identify the age of a mismatched old token.
`MTKAWDLROCResponseTimeouts` separately counts pending requests that expire
without an accepted grant when aborted; it is not a firmware denial count.
Counters sum accepted plus rejected events independently of timed-out requests.
The existing accepted-latency lookahead remains capped at 125 ms.

The runtime checker now fails on native “aw start event missing” errors even
when no SANITY FAILURE is logged. Empty AW activity and a wrong loaded UUID
remain unverified, and interface counter resets fail verification.

References:
- https://github.com/torvalds/linux/blob/master/drivers/net/wireless/mediatek/mt76/mt7921/main.c
- https://github.com/torvalds/linux/blob/master/drivers/net/wireless/mediatek/mt76/mt7921/mt7921.h
- Local snapshots: `build/reference-mt76-v7/mt7921/{main.c,mt7921.h,mcu.c}`.

## Validation and remaining limits

Nine relevant suites pass, including ASan/UBSan execution of production
scheduler and HAL handlers. Raw grant fixtures cover 504334-us response
delay, every rejection class, malformed TLVs, duplicate/cancelled tokens,
reset/teardown, deadline expiry and exact RF lifetime. Production scheduler
fixtures verify preserved grants through idle slots and later actual AW
counter/time/duration, without an event for the missed AW. Existing rollover,
role/control boundary, drift, sparse/adjacent-channel and retained-TX coverage
passes. Runtime-check fixtures cover native missing-event errors separately
from sanity failures.

Release x86_64/Tahoe and 569 + 244 static ABI checks pass. Artifact identity,
source commit and check results are in `build/awdl-roc-fix/verification.json`.
The new UUID is not loaded. No hot-unload, install, reboot or OpenCore change
was performed. Install through the existing normal-boot workflow and verify
its UUID before measuring AirDrop/AWDL again.

Waiting longer prevents premature host cancellation; it does not reduce
firmware response latency or reserve two channels concurrently. A 200-ms
response may still miss its first target, and a one-second unanswered request
can delay another channel. Adjacent different-channel AWs cannot be fully
covered when real firmware latency exceeds the switching interval. Physical
grant loss can still truncate an AW. Hardware counter/spacing, sustained AW
coverage and a completed AirDrop file transfer remain unverified on this build.
