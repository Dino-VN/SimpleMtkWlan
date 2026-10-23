# ROC command ACK contract and waiter isolation

This candidate includes the AW radio-edge timestamp and preparation-history
changes in `AWDL-rhythm-fix.md`. It additionally matches Linux's asynchronous
ROC command header and consumes ROC command results without corrupting other
firmware waiters. Full multichannel AW continuity remains unverified.

## Evidence and changes

The saved Linux `mt76_connac2_mcu_fill_message` at
`build/reference-mt76-v6/mt76_connac_mcu.c:3159` always writes
`MCU_CMD_UNI_EXT_ACK` for unified commands. That value is 7: ACK, unified, SET.
`mt7921_mcu_set_roc` and `mt7921_mcu_abort_roc` in
`build/reference-mt76-v7/mt7921/mcu.c:766` and `:833` use that builder even
though their send calls do not synchronously wait for command completion.
The separate unsolicited ROC grant determines radio readiness.

The local builder previously wrote option 6 when no wait-sequence pointer
was supplied, including both ROC paths. ROC CID `0x27` now uses option 7.
Other asynchronous command headers retain their existing options. The change
requests the Linux wire behavior without adding a blocking ACK wait in the
AW timer. These are source/reference observations, not new REA evidence.
Exact reference SHA256 values are saved in `verification.json`.

Requesting ACKs exposes another defect: the generic receive path routes command
results using only their four-bit MCU sequence. A late ROC result could overwrite
and complete a later BSS/STA waiter after sequence reuse. ROC unified result
CID `0x27` is now consumed before that generic path, with bounded body decoding
and mbuf release. It never accepts a radio grant or changes the current ROC
token, deadline, cancellation state or response timeout.

The result contains CID and status, not the ROC token or acquire/abort TLV.
Therefore its diagnostic status does not identify which old/new acquire or
abort completed. An ACK error is recorded rather than attributed to the current
request. The normal grant decoder remains the only radio authorization.

## Diagnostics

`MTKAWDLROCCommandResults`, `MTKAWDLROCCommandFailed`, and
`MTKAWDLROCCommandMalformed` count command results separately from accepted
grants. `MTKAWDLROCCommandLastStatus` and `MTKAWDLROCCommandLastResultUS` retain
the last well-framed result. A successful abort enqueue or ACK still does not
prove when firmware stopped RF ownership; replacement TX needs its own grant.

## Verification and next measurement

The new production test compiles and executes the complete MCU DMA header
builder and receive event dispatcher under ASan/UBSan. It verifies both acquire
and abort headers, asynchronous/synchronous header construction, BSS waiter
isolation after sequence reuse, unchanged pending grant state, malformed result
handling, unrelated BSS completion, grant/ACK separation and exact mbuf ownership.
The old header fails its ACK assertion. With only the header corrected, the old
receive path separately fails the waiter-isolation assertion. Raw failure logs
are in `build/awdl-roc-ack-fix/`.

All 14 relevant suites and the Release Tahoe x86_64 build pass. The 569 AWDL and
244 Skywalk static ABI slots still match the pinned KC. The new header's effect
on firmware latency or radio arbitration is not established by host mocks. The
19.261-ms transition replay remains a failing full-coverage case because those
tests preserve the real observed delay; the patch does not pretend ACK changes
it without a hardware measurement.

Candidate UUID: `17E9B561-A5D5-33A0-A502-B471DC377ADC`.
Executable SHA256:
`de2ce9951814c19988ac30f26e398252ee3de1ebffadd390a69ce6cd798b850a`.
Package: `build/awdl-roc-ack-fix/AirportMtkWlan-AW-ROC-ACK-fix.zip`.
The loaded baseline remains `DD38CCA5-D659-3C3C-AAA5-91F25BED5D57`.

After updating and booting normally, open AirDrop discovery near the peer and
run the AW checker for the new UUID. Compare command ACK errors, ROC response
delay, native AW sanity messages and actual data TX/RX. Full coverage and an
AirDrop transfer require that hardware evidence. Neither installation nor boot
configuration was changed in this investigation.

```sh
python3 tools/awdl/check-windows.py \
  --expected-uuid 17E9B561-A5D5-33A0-A502-B471DC377ADC \
  --seconds 30 --output build/awdl-roc-ack-fix/runtime-windows.json
```
