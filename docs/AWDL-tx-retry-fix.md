# AWDL data TX retention and discovery station setup

On the audited `1B8AC89E` boot, data TX counters initially recorded 22 HAL
submissions, 55 failures and 10 expired packets. A later source-review snapshot
showed 44 submissions, 151 failures and 38 expired packets. The last status was
success, so these cumulative counters cannot identify which earlier blocker
caused the failures. Native AW scheduling and selected-parent synchronization
also fail on this boot and still limit usable radio windows.

## Corrected paths

The previous `awdlTransmit` always freed a packet on error. The scheduler also
removed it from its queue before calling that function. A busy firmware
transaction, missing station, expired grant, DMA mapping failure or full shared
TX ring therefore destroyed data that could have been retried. The new
`awdlTryTransmit` uses an explicit pointer ownership contract: a non-null packet
on return remains queued; a null packet has been submitted or permanently
rejected. The regression test reproduces the old packet loss before the change.

Before consuming TX, the HAL checks the shared TXWI/ring capacity as the
infrastructure path does. It duplicates the attempt because `mwx_tx` consumes
its input on DMA errors too. Failed attempts retain the original bytes and
sequence number. Successful DMA submission frees the queued original.
Malformed shape/local identity is rejected permanently. Management frames
keep their existing always-consumed contract. This adds one mbuf duplication
per submission; its hardware throughput/allocation cost remains unmeasured.

Busy/grant/ring/allocation failures retain FIFO and stop the current batch.
A missing station rotates that packet so other peers and multicast can proceed.
The original one-second expiry is preserved on every retry; an absent usable
radio schedule still expires data rather than inventing a grant.

Discovery unicast may precede native peer cache/traffic registration. Queued
destinations observed in valid AWDL advertisements now get a bounded firmware
station before sending. Three tracking slots match the HAL unicast WCIDs
15..17. Unknown destinations do not create stations. Expired discovery stations
are disconnected unless native cache/traffic still owns them. Cache removal,
MAC change, transport reset and disable invalidate the tracking. Firmware waits
revalidate enabled state and membership; a stale add is removed, and a revived
owner during deletion has its station restored. Restored stations remain tracked
until expiry; failed stale-add cleanup also remains tracked for the next tick.
Window/grant snapshots are recomputed after these waits.

## Linux and reported MT7921/MT7922 evidence

The user-provided [Linux MT7921 source](https://github.com/torvalds/linux/tree/master/drivers/net/wireless/mediatek/mt76/mt7921)
uses a station WCID for unicast and vif WCID when there is no station
(`mt792x_tx`), and resumes its TX worker when firmware releases tokens
(`mt7921_mac_tx_free`). Local master-source snapshots and SHA256 provenance
are saved under `build/awdl-tx-fix/linux-reference/`; master is mutable.

[Owly issue 14](https://github.com/t4t5/owly/issues/14) reports no IBSS on
MT7921 and mixed active-monitor/shared-mode results. The
[tested legacy-rate patch](https://github.com/shaecodes-wilde/mt76/commit/02b6c9a1ef87e55f2ccf90739e5dbcab55390cc7)
saves an injected rate before Linux status bookkeeping overwrites it, then
uses the complete common fixed-rate builder. Reports describe 1Mbps CCK
unicast instead of requested OFDM, including absent 5GHz transmissions.
Those Linux monitor reports are not evidence of the same execution path on
this macOS P2P backend.

This driver already encodes 6Mbps OFDM directly. AWDL now always enters the
complete fixed-rate 802.11 builder even when infrastructure rate adaptation is
enabled, rather than applying only a partial override afterwards. Descriptor
tests verify OFDM mode/rate, 20MHz width, fixed-rate/HTC settings, WCID, OMAC,
WMM/TID, supplied sequence, unicast ACK and multicast no-ACK. Infrastructure
rate adaptation remains separately tested. No IBSS fallback or blind channel
pinning is introduced; regulatory availability and live matching ROC still
gate transmission.

## Validation and runtime limits

The seven AWDL suites plus TX unwind and TXWI tests pass under ASan/UBSan.
They cover original packet identity/age across retries, bounded expiry, FIFO,
missing-station fairness, discovery setup/cleanup/native ownership, reentrant
firmware waits, malformed rejection, each DMA failure return, and 24 TXWI
configurations. The Release x86_64/Tahoe build and static native ABI checks
are recorded with the candidate's UUID/hash in
`build/awdl-tx-fix/verification.json`.

`MTKAWDLDataTxDeferred` counts retry deferrals, not dropped packets. HAL
`MTKAWDLTXNoGrant`, `TXBusy`, `TXNoPeer`, `TXBackpressure`, `TXCopyFailed`,
`TXDMAFailed`, `TXBadFrame` and `TXLastErrno` distinguish blockers. The updated
`tools/awdl/check-data.py` records their interval deltas. `DataTxSubmitted`
still means HAL/DMA accepted a frame, not firmware ACK or accepted file transfer.
The candidate must execute on hardware before successful AWDL TX is claimed.
