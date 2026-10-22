# Broadcom native AWDL event and control comparison

This comparison follows the macOS Tahoe x86_64 driver actually present in
`/System/Library/KernelCollections/BootKernelExtensions.kc`. It establishes
native producer and consumer behavior from static instructions. It does not
establish that a MediaTek candidate works on hardware or that AirDrop transfers
a file.

## Artifact and evidence

- KC SHA256: `21d6da1c4c3e7b72dddf5144da8a4c4b48e294249a16018a5006b61bb2155ccc`.
- IO80211Family UUID: `4184F404-9547-3499-A311-C1920829EA25`.
- AppleBCMWLANCore UUID: `D09C7323-1C09-36E3-B8C1-B58E52F48537`.
- Existing REA AW-start analysis:
  `ev_d4ebca8f3fc1d5bb17db5717cb948001cd5a5549964a741915059957103659b5`.
- Existing REA AW-end analysis:
  `ev_9814c0db09fadf8727dae8b55150476fc3039d00b7faa44898b0410716661586`.
- Complete local producer/control disassembly:
  `build/awdl-timing-fix/broadcom-forwarding-control.txt`.
- Existing dispatcher and payload evidence:
  `build/awdl-abi-annotated-20261021.txt`,
  `build/awdl-abi-payloads-20261021.txt`,
  `build/rea-awdl-monitor-offline.txt`.

The local report was generated with the existing KC/Capstone helper without
executing the target or touching the live REA session. Its address/file mapping
uses fileset segments and the KC symbol table. Next-symbol bounds may include
padding; indirect callees and firmware internals remain unknown. REA's earlier
focused Mach-O wrappers preserve original function bytes and addresses but do
not map external calls/data. Decompiled text is not original source.

## Firmware events become native messages

`AppleBCMWLANProximityInterface::handleAvailabilityWindowStart` begins at
`0xffffff8001718756`. It validates at least 28 bytes of firmware event data,
copies fields into a zero-initialized 36-byte native record, converts the
firmware channel specification, and posts message 41 with the final boolean
argument set to true (`0xffffff80017188b9` through `17188d1`).

| Native start offset | Width | Firmware input / conversion |
| --- | --- | --- |
| 0 | 4 | Zero-extended 16-bit AW counter from firmware offset 10 |
| 4 | 4 | Firmware role byte at 13: 0 becomes native 2; 1 becomes 3; 2 becomes 1 |
| 8 | 6 | Immediate-master MAC copied from firmware offset 4 |
| 14 | 6 | Top-master MAC copied from firmware offset 22 |
| 20 | 4 | Raw firmware timestamp bytes copied from firmware offset 0 |
| 24 | 12 | Firmware 16-bit chanspec at offset 15 converted to `apple80211_channel` |

The timestamp is not replaced with `mach_absolute_time`. Native consumers
byte-swap the timestamp to microseconds. Role translation is at
`17187c0` through `17187ec`; counter/MAC/time copying is at `1718849` through
`171887c`; channel conversion is at `171889a` through `17188a9`. The channel
comes from the event's reported chanspec, rather than a prediction from the
host channel sequence. Unknown role bytes take a diagnostic path and leave
the initialized native role zero.

`handleAvailabilityWindowEnd` begins at `0xffffff80017184b6`. It validates at
least 28 firmware bytes and posts message 43 with a 40-byte native record and
the final boolean true (`1718631` through `1718649`).

| Native end offset | Width | Firmware input / conversion |
| --- | --- | --- |
| 0 | 4 | Zero-extended firmware byte at offset 12, without start-role translation |
| 4 | 4 | Raw firmware timestamp bytes from offset 0 |
| 8 | 1 | Raw firmware byte at offset 17 |
| 9 | 3 | Zero padding |
| 12 | 4 | Raw firmware DWORD at offset 18 |
| 16 | 24 | Optional statistics; initialized zero unless a supported extension is present |

The optional statistics branch requires the driver flag at `ivars+0x75`,
valid extended bounds, and a supported extension identifier. It writes a
native statistics version of 1. Base event forwarding continues when the
optional supported statistics are absent. The base first DWORD is not proven
to be a native role by these instructions; do not infer its meaning from the
local C++ field name `role`.

`handleAvailabilityWindowExtension` begins at `0xffffff8001718942`. It copies
firmware byte 12 into native DWORD 0 and raw firmware timestamp bytes 0 into
native DWORD 4, then posts message 42 with size 8 and the final boolean true
(`171897e` through `17189ac`). This is separate from end message 43.

These three handlers forward supplied event fields. Their inspected bodies
do not reconstruct an AW boundary from received peer frames, generate a
missing idle-slot start, or close an AW merely because host election state
changed. Firmware production of the events is outside the inspected bodies.

## Host synchronization state is a firmware command

`setAWDL_SYNC_STATE` begins at `0xffffff800171e164`. Native mode 1 maps to
firmware role 2 (`MASTER`), native mode 2 maps to firmware role 0 (`SLAVE`),
and native mode 3 maps to firmware role 1 (`NE_MASTER`). This is the inverse
of the start event translation.

The setter ORs the native byte at offset 20 into the firmware role byte. It
copies the low byte of the native DWORD at offset 16 into command byte 0,
the supplied master MAC at native offset 8 into command bytes 4 through 9,
and the cached non-election broadcast period into command bytes 2 through 3.
Command byte 1 contains the mapped firmware role plus the flags. Remaining
bytes start zero. It submits a 28-byte `awdl_opmode` virtual IOVar through
`AppleBCMWLANCommander::sendVirtualIOVarSet` at `171e2ce`, with a completion
record rather than a synchronous get operation. The getter at `171b528`
uses `runVirtualIOVarGet` for `awdl_opmode`.

No inspected `setAWDL_SYNC_STATE` instruction emits an AW-start/end or
calls the AW handlers. Submitting a mode change is therefore distinct from
receiving an actual availability-window event.

Native `programChipWithNewMaster` at `0xffffff80021ec4b6` supplies the remote
immediate-master MAC to ioctl 134 (`AWDL_SYNC_STATE`). Its warmup path sets
the mode-flags byte to `0x20` at `21ec5c6`; the adjacent log explicitly says
it allows synchronization to the immediate master and adoption of its AWDL
sequence number. Preserve that explicit control when designing clock
adoption, rather than assuming every received peer frame requests an
unbounded sequence-number replacement. The precise firmware behavior of
the other mode bits is not established here.

## What native validation requires from the MediaTek path

The native dispatcher stores the reported start counter and uses it to
select the expected channel descriptor. Its `sanityCheckAWStart` at
`0xffffff80021e21de` requires paired starts/ends, advancing counters and
the expected nonzero sequence windows. The skipped-start loop explicitly
excludes channel 0 (`21e2398` through `21e23b8`). Genuine absent nonzero
grants cannot be fixed by reporting idle-slot events.

Native start timing uses both firmware timestamps and host event receipt
time. `monitorTimeline` checks next counter against the next nonzero slot
in either old/new sequences and checks firmware start spacing within 5 TU
when the counter matches. Accepted master changes affect diagnostic wording,
not the continuity comparison. Its returned top-master-change flag is used
after `sanityCheckAWStart`, not as a pre-validation reset.

`sanityCheckAWEnd` at `0xffffff80021e4f5e` checks the decoded firmware
`(end-start)>>10` duration against `presence*AW_period` with a 10 TU
tolerance. Host clock corrections or master changes do not waive that
duration check. A host-derived MediaTek timeline must preserve the already
announced AW and its matched radio grant through compatible phase updates,
while still ending it for genuine grant loss, disable or reset. Timer
lateness must not be presented as extra firmware radio time.

An observed native limitation is that `logAWEnd` decodes/stores the end
timestamp at `21e4d4d` through `21e4d57` only after passing its `0x2000`
debug-log gate. The duration calculation uses that stored value. This
investigation's failing hardware logs have that gate enabled; disabling
logging is not evidence of a corrected radio lifetime.

Extension message 42 updates extension metadata and `ivars+0x198` in the
inspected native dispatcher. It does not reset the current counter,
sequence index, open-window flag, or preceding start timestamp. Inventing
extension messages cannot heal missing or shortened real windows.

The comparison supplies ABI and scheduling constraints. MediaTek firmware
grant latency, cross-channel behavior, lifecycle under real clock changes,
and successful AirDrop file transfer still need independent hardware
validation for the final candidate.
