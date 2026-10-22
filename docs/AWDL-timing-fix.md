# AWDL timing and off-channel preparation

The running TX candidate `56E1929B-B163-3C72-A951-D02324508354`
submitted data to DMA but still failed native AW validation. The 30-second
AirDrop capture recorded 286 starts/286 ends and 121 skipped-start failures.
A later sample contained 44 starts, all on channel 36, advancing by 64 AW
counters approximately every 1.048576 seconds. The native sequence also
contained channels 6 and 149. Channel-zero slots do not count as missing AWs
in native validation, so this evidence indicates absent nonzero windows.
It does not identify the firmware's exact reason for missing the grants.

## Reference and changes

[The local Broadcom comparison](AWDL-broadcom-comparison.md) establishes the
producer payloads and native consumer constraints from the exact Tahoe KC.
Broadcom forwards firmware AW timestamps/counters/channels. Sync opmode
commands do not generate AW events or waive start continuity/end duration.
MediaTek still uses host scheduling matched to real ROC grants because the
inspected MediaTek transport has no equivalent autonomous AW event stream.

The HAL now configures secondary-BSS RLM on channel changes before submitting
ROC acquire. The configured channel is cached; a failed/stale RLM operation
does not submit ROC. Scheduler revalidation after the firmware wait remains
mandatory. The lookahead in preceding idle slots increases from 25 to 55 ms.
The existing bounded early close for adjacent nonzero channels stays within
native's 10-TU duration tolerance. Longer preparation time does not allow
an early or fabricated AW-start.

An announced window retains its channel/counter/end through compatible RX
phase updates while its matching token and radio grant remain live. The
timeline records the accepted sequence, role, presence and master addresses.
Changes to those values, radio revocation, disable and reset still end the
window. Reentrant event callbacks are checked against the recorded sequence.

Native-managed synchronization adopts a peer clock on initial selection.
Later fresh same-parent samples slew by at most 512 microseconds; samples
outside 5 TU are counted and rejected rather than jumping the counter.
Timer ticks and replayed/older sample timestamps cannot apply the correction
again. Standalone election behavior is unchanged. Same-parent advertiser
refreshes no longer cancel a ROC merely because the new clock estimate has
a different counter. `MTKAWDLClockCorrections` and `MTKAWDLClockRejected`
expose this behavior for hardware measurements.

## Validation and limits

The regressions reproduce lost off-channel windows with the old 25-ms lead
in a sparse 16-slot sequence with a modeled 45-ms off-channel grant delay.
The candidate emits all four off-channel starts over two cycles. **45 ms is
a modeled test delay, not a measurement of this card's firmware.** The tests
also cover pinned ends during phase changes, administrative sequence changes,
reentrant callbacks, paired events, short grants, rollover and presence modes
1 through 64. Clock tests exercise positive/negative corrections, AW counter
rollover, repeated timer ticks, discontinuous counters and older samples.
HAL tests verify ordered RLM/ROC, cached channels, firmware error and stale
epoch rejection, and timeout accounting after the RLM wait.

Nine suites passed under their existing ASan/UBSan harnesses. The Release
x86_64/Tahoe candidate and static native ABI checks are recorded in
`build/awdl-timing-fix/verification.json`. The comparison is static; there is
no supported Broadcom card runtime capture in this investigation.

This candidate has not been installed or loaded. The hardware effect of RLM
and the 55-ms lookahead, clock drift/reselection behavior and AirDrop file
transfer remain unverified. Rejected discontinuous samples require native
reselection to recover; the patch does not silently renumber events. DMA
acceptance remains distinct from radio ACK or completed transfer. Adjacent
channel switches with firmware latency exceeding the duration tolerance may
still miss windows. Use a normal boot of the packaged candidate for the next
measurement; no hot-unload, OpenCore edit or reboot was performed here.
