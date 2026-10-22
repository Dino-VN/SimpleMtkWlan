# Software AW events with one radio clock

This candidate fixes a reproduced host scheduling failure: a fresh PSF from
the selected synchronization parent moves the AW edge during the synchronous
secondary-BSS RLM wait. The old exact-edge revalidation aborts the ROC request
even though its channel, counter, sequence and master are unchanged. The
regression fails on the previous implementation at the pending-grant assertion;
the saved failure is `build/awdl-emulation-fix/regression-before.log`.

The [Broadcom comparison](AWDL-broadcom-comparison.md) supplies the native event
ABI and validation rules from the exact installed Tahoe kernel collection.
Broadcom forwards firmware events; it does not regenerate an AW when a host
control changes. MediaTek has no equivalent AW firmware event producer in the
inspected transport, so this remains a software event backend bound to real
ROC grants. It does not establish equivalence to undocumented Broadcom firmware.

## Clock and lifetime

Before entering the RLM/ROC transaction, hold the selected-parent clock through
the first requested EAW end. Keep accepting peer observations while it is held.
An open AW extends that hold to its own scheduled end. Both native messages and
outgoing synchronization TLVs use the same epoch/base counter, so a retained
event does not disagree with the advertised radio clock.

On release, election uses the newest observation and applies at most 512 us
of phase correction. It does not add together deferred corrections or replay
each received PSF. A hold expires at its absolute boundary even without a
grant. Samples more than 5 TU away remain rejected. Initial parent selection,
real role/master changes, disable and reset retain their existing lifecycle
semantics and clear obsolete holds; this patch does not implement undocumented
firmware opmode bits or defer administrative sequence changes.

AW-start still requires a matching observed grant near the real EAW edge and
adequate actual dwell. AW-end keeps the recorded radio/schedule time despite
a delayed timer. Missing/short grants do not produce artificial native windows,
counter renumbering or idle-slot starts. Exact post-wait validation remains in
place to catch genuine schedule changes.

## Runtime diagnostics

Interface properties expose `MTKAWDLClockDeferred`, `ClockHoldUntilUS`,
`ReserveWaitUS`, `ReserveMaxWaitUS`, `ReserveInvalidations` and
`ReserveInvalidReason`. The reason is a bit mask: 1 = role/master/sequence,
2 = window edge/channel/counter/presence, 4 = requested EAW expired during
the synchronous wait. `RequestedAWChannel/Counter/StartUS/EndUS` retain the
last target. Wait time includes RLM and HAL work, not the later grant latency.

Controller properties expose `MTKAWDLROCGrantDelayUS/MaxGrantDelayUS`,
`ROCChannel`, `ROCToken`, `ROCObservedAtUS`, `ROCDeadlineUS` and `ROCGranted`.
Grant latency starts at ROC submission after RLM, and counts accepted grants
only. The snapshot is taken under the existing receive lock; property
publication happens outside it. A retained granted flag needs its deadline
checked before inferring current radio availability.

## Verification and remaining limits

Eight relevant suites pass, including the actual production scheduler under
ASan/UBSan. New scenarios deliver selected-parent observations during a 10-ms
RLM wait, pending ROC, an active AW and a synchronous native start callback.
Positive/negative drift tests cover sparse schedules and uninterrupted same-
channel EAWs across counter rollover, checking each event's counter, 5-TU start
spacing and 10-TU end-duration tolerance. Protocol tests verify newest-sample
replacement, bounded release with no grant, and role-change cancellation.
The 10/35/45-ms firmware delays are modeled, not measured on this card.

Release x86_64/Tahoe build and 569 + 244 static ABI checks pass. Candidate UUID,
hash, source commit and validation are in
`build/awdl-emulation-fix/verification.json`. The currently loaded offload
candidate is a different UUID. No candidate install, hot-unload, OpenCore edit
or reboot was performed here.

Hardware AW continuity and AirDrop file transfer remain unverified for this
candidate. Genuine master/sequence transitions can still shorten an AW;
firmware arbitration can still deny or delay nonzero channel windows. The
software clock fix cannot supply missing RF time. Validate the new UUID on a
normal boot with real AirDrop traffic before marking AWDL or AirDrop fixed.
