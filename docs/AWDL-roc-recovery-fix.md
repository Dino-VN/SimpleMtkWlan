# ROC queue admission and cancellation recovery

This candidate fixes two reproduced host-side ROC failures: counting MCU
queue admission against the grant response timeout, and issuing another
acquire after the preceding abort failed to enqueue. It includes the earlier
fix that retains a valid early grant through its original reserved AW.

## Reproduced failures

The MCU send path can wait up to 30 times for a full command ring, at 100 ms
per wait. Previously `awdlReserve` started its one-second response budget
before entering that path. A 1.2-second queue wait therefore expired the
request before firmware could receive it. The added production HAL regression
fails on the previous code at the submission timestamp/deadline assertion.

The abort helper previously cancelled local state and discarded the transport
result. An injected abort enqueue error still allowed the replacement acquire
to be sent. The separate old-code regression fails because that reserve call
returns success instead of reporting the abort error. Its wire trace contains
an acquire after the failed abort.

Saved baseline failure logs are `regression-queue-before.log` and
`regression-abort-before.log` under `build/awdl-roc-recovery-fix/`.

## Behavior after the fix

| Condition | Result |
| --- | --- |
| MCU admission waits before accepting an acquire | Start the full one-second response budget after successful enqueue; report queue admission delay separately |
| Matching grant arrives before the send helper returns | Preserve the observed grant and its real expiration; do not turn it back into a pending request |
| Abort cannot enqueue | Deny local TX, retain the cancelled token, return the error, and send no replacement acquire |
| Reserve retries after an abort error | Retry the original abort first; reserve-driven failed transport retries are limited to once per 10 ms |
| Cancelled token is retired | Refresh its quarantine timestamp at cancellation completion/teardown, preventing immediate reuse while old events may still arrive |
| Removing BSS/OMAC succeeds | Clear cancellation recovery because the old firmware context has been removed |
| Removing BSS/OMAC fails | Keep the recovery token and partial context for another cleanup attempt |
| An observed grant expires | Publish `MTKAWDLROCGranted=false`, even while the historical internal grant record remains stored |

Acquires and aborts retain the 28-byte and 16-byte Linux MT7921 wire layouts.
The request remains generic ROC, not JOIN. A successful abort means the host
queued the command; the firmware does not return an abort acknowledgement in
this path. The next acquire follows it in the same MCU command queue, as in
Linux. This change does not claim confirmed firmware cancellation.

The public grant flag is evaluated at the published observation time. Like
other IORegistry properties, it is sampled and may be read after that time.
Actual TX and AW events continue to check the live grant deadline and channel.

## Diagnostics, version 12

`MTKAWDLROCState` distinguishes `idle`, `waiting-grant`, `response-expired`,
`granted`, `grant-expired`, and `abort-pending` at
`MTKAWDLROCStateObservedAtUS`.

`MTKAWDLROCQueueDelayUS` and `MTKAWDLROCMaxQueueDelayUS` measure acquire send
call/queue admission time separately from the accepted grant response delay.
`MTKAWDLROCAbortSubmitted`, `MTKAWDLROCAbortFailed`,
`MTKAWDLROCAbortPending`, `MTKAWDLROCAbortToken`, `MTKAWDLROCAbortStatus`,
and `MTKAWDLROCAbortRetryAtUS` expose cancellation recovery. Existing response
timeout and grant rejection counters remain independent.

## Validation and limits

The fixed production HAL tests accept a grant 3 ms after a 1.2-second queue
wait, with a measured response delay of 3 ms. Tests also verify early reply
preservation, failed abort containment/retry ordering, old token retirement,
single timeout accounting across repeated abort failures, context cleanup,
expired grant publication and recovery diagnostics. Existing regulatory,
token/channel rejection, teardown and TX ownership tests remain in that suite.

All 13 relevant test groups and the macOS Tahoe x86_64 Release build pass.
The 569 AWDL and 244 Skywalk static ABI slots match the pinned native image.
They include the ten AWDL groups plus BSS wire checks, MCU gate wait checks
and detach lifecycle checks. ASan/UBSan execute the production HAL and AW
scheduler. The earlier sparse mixed-delay model still records 11 start/end
pairs and seven reserves in eight seconds; the dense 500 ms model still
records 10 pairs in six seconds. These are controlled results, not RF tests.

The loaded hardware baseline is still UUID
`AC1899FF-55E6-31A5-81A7-A11DAA3F041D`. The saved 15-second snapshot interval
had native synchronization disabled, so its zero counter deltas cannot assess
active ROC behavior. Cumulative timeout counters from that boot do not prove
either reproduced failure caused all unanswered firmware requests. The old
build lacks the separate abort and queue diagnostics needed for attribution.

After the user updates and boots normally, verify the new UUID, then measure
ROC response timeouts, queue delay, abort errors and actual AW/data activity.
Sustained hardware ROC reliability, full multichannel AW coverage and a
completed AirDrop transfer remain unverified. No driver installation, hot
unload, reboot or OpenCore edit was performed.

Candidate UUID: `1DA29DE1-EC4F-35D9-B964-DD764B363014`.
Executable SHA256:
`736442a2f548480c5f748d7c075081ac36e9ff668b52d91be8167eb5b854e1a3`.
