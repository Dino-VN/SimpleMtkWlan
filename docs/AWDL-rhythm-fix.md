# AW timing recovery and radio edge timestamps

This candidate fixes two host emulation defects while retaining real ROC
ownership as the requirement for every AW event. It does not establish full
multichannel coverage or a completed AirDrop transfer on hardware.

## Native contract

The pinned Tahoe KC SHA256 is
`21d6da1c4c3e7b72dddf5144da8a4c4b48e294249a16018a5006b61bb2155ccc`.
The earlier REA AW-start dossier is
`ev_d4ebca8f3fc1d5bb17db5717cb948001cd5a5549964a741915059957103659b5`;
the AW-end dossier is
`ev_9814c0db09fadf8727dae8b55150476fc3039d00b7faa44898b0410716661586`.
The local mapped wrappers and their original-byte digests are listed in
`build/rea-awdl-functions/manifest.json`.

Retained native instructions establish three separate checks:

| Check | Native location | Accepted timing |
| --- | --- | --- |
| Reported start spacing | `monitorTimeline`, `0xffffff80021e1ab8` | Error at most 5120 us (5 TU) |
| Host event receipt spacing | `sanityCheckAWStart`, `21e2c06` through `21e2c44` | Error at most 10 ms after integer conversion |
| Reported duration | `sanityCheckAWEnd`, `21e4f98` through `21e4fb0` | `abs(((end-start)>>10)-presence*period) <= 10 TU` |

The producer forwards firmware timestamps independently of host receipt
time. See `AWDL-broadcom-comparison.md`, `build/rea-awdl-monitor-offline.txt`,
`build/awdl-abi-sanity-20261021.txt`, and
`build/awdl-abi-aw-end-sanity-20261021.txt` for exact instructions. A new REA
Ghidra open attempt was unavailable because Ghidra and Java were not configured;
these findings use retained REA evidence and ordinary static disassembly.

## Changes

An AW start reports `max(scheduled edge, matching grant observation)`.
When the accepted grant precedes the edge, host timer jitter cannot move the
reported radio edge. A genuinely late grant retains its late timestamp. End
admission, early switching and disable waits all use that same start. Current
TX eligibility still checks the live grant at the current host time.

The previous preparation estimate only grew. One startup response near a
second therefore moved later reservations far ahead even after recovery. The
estimate now uses the maximum of the last eight accepted response/preparation
samples plus 8 ms, bounded between 55 ms and one second. Repeated polling of
one grant does not add a sample. Slow responses still increase it immediately.

`MTKAWDLLastAWStartUS` is the reported radio edge;
`MTKAWDLLastAWStartDeliveryUS` and `MTKAWDLLastAWStartDeliveryDelayUS` expose
host delivery separately. `MTKAWDLReserveTimingSamples` and
`MTKAWDLReserveLeadDecreases` expose estimate recovery.

## Verification

All 13 relevant suites pass, including production scheduler and HAL tests
under their ASan/UBSan harnesses. Release x86_64/Tahoe builds successfully;
569 AWDL and 244 Skywalk ABI slots match the pinned native image.

The old start dispatcher fails the new prepared-grant regression. The new
dispatcher emits 42 paired AWs with alternating 0/7900-us host delivery
delays, exact scheduled start timestamps, and counter and wire-clock rollover.
A late 56-ms grant dispatched 4 ms later uses its actual RF observation and
still ends within native duration tolerance.

A 40-second replay of the recorded channel shape and a 984947-us initial
response followed by 19261-us responses reduces skipped nonzero windows from
438 to 236 and increases starts from 148 to 353. The lead recovers from about
993 ms to 55 ms. These are modeled results, not a radio measurement. The model
still loses windows: 19.261 ms exceeds the combination of the 10-TU early end
allowance and 5-TU start spacing allowance. The patch cannot promise native
continuity for that physical transition.

The native monitor also uses four-counter descriptor steps and 16 slots.
Local presence sweeps beyond the default presence 4 establish local safety,
not equivalence to that native monitor. Physical late grants, host scheduling
stalls and native timestamp rollover edge cases remain hardware concerns.

The current loaded baseline is UUID
`DD38CCA5-D659-3C3C-AAA5-91F25BED5D57`. A fresh 15-second read-only sample
had AWDL disabled and no starts, so it cannot validate this candidate.

Candidate UUID: `833BDB94-9DCB-3CFD-9013-05B9F74D7F68`.
Executable SHA256:
`f5a4e50b5c3cfe7dd90c1fa5122655ef69e92291ba031d09624d480e5897081b`.
Package and detailed verification are under `build/awdl-rhythm-fix/`.

After updating the kext and booting normally, enable AirDrop discovery and run:

```sh
python3 tools/awdl/check-windows.py \
  --expected-uuid 833BDB94-9DCB-3CFD-9013-05B9F74D7F68 \
  --seconds 30 --output build/awdl-rhythm-fix/runtime-windows.json
```

Actual full AW coverage and AirDrop transfer remain unresolved until an active
hardware observation. No installation or boot configuration was changed.
