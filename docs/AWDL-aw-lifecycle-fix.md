# Native AW start/end correction

## October 22 REA follow-up

The first candidate (`BF3A7235-32B8-353F-9B66-82D427B0FC6C`) was subsequently
loaded. Its initial 15-second observation produced seven starts and seven ends,
but seven new native sanity failures (one skipped-10, six skipped-7). Balanced
notifications did not establish correct RF scheduling. The final 10-second
observation in `build/awdl-rea-fix/installed-baseline.json` was idle with no new
start, so it is explicitly unverified.

REA's Apple Events permission now works. Direct KC byte reads succeeded;
Hopper did not define procedures in the fileset regions. Focused Mach-O
analysis wrappers preserve the exact original function bytes and virtual
addresses, with provenance in `build/rea-awdl-functions/manifest.json`.
External calls and data remain unmapped, and pseudocode is not source.
An earlier wrapper mapped zeros; its decompilation is excluded, and the valid
wrapper's byte read was verified before using its analysis.

The retained evidence in `build/rea-awdl-complete-evidence.json` includes:

- Direct complete KC AW-start bytes: `ev_da2753dd485f9c046fced2782488d882cd55b07ade819cd65fbb20283aef4fb7`.
- Valid mapped AW-start byte verification: `ev_e1f76375f611c1eb898e940fb9dd095b04e8d8d68972ec169faaa9fb248e5957`.
- AW-start analysis: `ev_d4ebca8f3fc1d5bb17db5717cb948001cd5a5549964a741915059957103659b5`.
- Program-master analysis: `ev_83d7698a38ebe5d6f3069b0568fafa6172f6e20900bcb443feea4659507bab9e`.
- AW-end analysis: `ev_9814c0db09fadf8727dae8b55150476fc3039d00b7faa44898b0410716661586`.

Native `programChipWithNewMaster` at `0xffffff80021ec4b6` sends ioctl 134
(`AWDL_SYNC_STATE`) with mode 1 or 2 and a remote immediate-master MAC.
The old mode-1 validation required the local MAC and therefore rejected a
real native request; the log's “can't set op_mode” refers to this sync-state
operation, not the separate ioctl 217. Native-managed mode 1 now accepts the
remote MAC, and duplicate mode/flag refreshes preserve pending and live ROCs.
Start payload role uses the accepted native mode.

Following a peer previously overwrote the native programmed radio sequence
on every RX/timer election. Native logs reported firmware sequence mismatch
and expected-149/reported-36 AW-start errors. Native-managed election now
uses the peer clock with the native programmed channel sequence and presence.
The sequence setter applies to the active schedule even while synchronized.
Duplicate advertisers compare against that programmed schedule so they do
not repeatedly cancel a grant just because the peer advertises another
sequence. New host sequence/presence/role properties expose this distinction.

The scheduler also returned immediately and aborted in every channel-0 slot,
preventing preparation for the next valid channel. It now prepares the next
window during the last 8 ms and retains its pending or granted ROC across
idle ticks. Production-code regression tests reproduced both scheduling
defects before the fix, then passed with delayed asynchronous grants,
consecutive windows, native mode-1/remote-master input, and repeated
advertisers/opmode requests. ASan/UBSan protocol, controls, MI/RX, sync,
partial-init, native startup and HAL checks passed, as did the 569-slot ABI
check and the Release x86_64/Tahoe build.

New candidate UUID: `AFD857F8-F7B0-3F90-B949-7DC46EBDF682`.
Kext: `build/awdl-rea-fix/Release/AirportMtkWlan.kext`.
Package: `build/awdl-rea-fix/AirportMtkWlan-AW-REA-fix.zip`.
Verification: `build/awdl-rea-fix/verification.json`.
REA evidence was exported and its native session closed. The user later
loaded this exact UUID (boot October 22 at 00:59:23 +0700). Its 20-second
runtime check failed: 13 starts and 13 ends, balance zero, but 14 new
“Skipped 7 AW start events” log failures. Host/native sequences match, and
the saved five-minute log has no opmode or firmware-sequence mismatch
messages; missing starts and an earlier 38-TU short end still remain.
The remaining RF/grant timing cause and AirDrop transfer are unresolved.
See `build/awdl-rea-fix/runtime-result-20261022.md` and raw runtime artifacts.

The sections below describe the initial candidate and its original baseline.

The boot-loaded driver UUID is `8C74040F-45E7-36B3-8852-C6205478F9BD`.
Live registry initially showed two AW-starts, two AW-ends and 19,732 late
observations. The boot log records “Skipped 14 AW start events” at 23:43:47
and “Skipped 15 AW start events” at 23:43:49 on October 21, 2026. Earlier
retained V16 logs also contain sequence, start interval and AW duration failures.
These are baseline observations, not results from the rebuilt candidate.

The scheduler now prepares the next EAW during its last 8 ms lead interval
when the current boundary has been missed and no native window is open.
It requests the full supported 70 ms dwell and rechecks window, presence,
parent, root and channel sequence after MCU calls that can release the gate.
A prepared grant never causes a start before the target boundary.

Start events use the role captured with their window. Deduplication uses the
AW counter, presence, masters and nearby boundary time, including small clock
corrections in either direction. The same channel still gets events for
successive AW counters, and 16-bit counter rollover does not suppress them.

A native window records the earlier of its scheduled end and the matched
grant expiry. Grants must support a duration inside native's 10 TU tolerance;
a 32 ms grant cannot represent a 64 TU EAW. Too-short grants are counted
separately. Timer dispatch lateness no longer inflates the encoded end timestamp.
Grant revocation, firmware reset, disable and shutdown close an open window
once; reentrant end dispatch cannot duplicate the end. Both native payloads
have size and offset assertions (start 36 bytes/event 41, end 40 bytes/event 43).
Optional end statistics remain zero, matching the native producer without stats.

`tests/awdl/test-native-windows.py` executes production event builders and
scheduler code with grant, clock and callback scenarios under ASan/UBSan.
`tests/awdl/run.sh` includes it. Existing MI, partial-init and HAL test mocks
were updated to match the production timeline and scan cancellation interfaces.
The HAL suite now checks the actual 70 ms limit and scan-yield failures.

Build and validation results are recorded in `build/awdl-fix/verification.json`.
Release x86_64/Tahoe build succeeded. AW lifecycle, protocol/parser, MI/RX,
sync, startup, native controls, partial init, advertisers decoder, HAL, firmware
wait and BSS checks passed. Static native ABI checks passed for 569 AWDL
virtual slots and 244 packet/pool/queue slots against the pinned Tahoe KC.
Offline native instructions were checked using the repository Capstone helper;
REA registration was healthy but its MCP tools were not connected to this chat.

Candidate UUID: `BF3A7235-32B8-353F-9B66-82D427B0FC6C`.
Kext: `build/awdl-fix/Release/AirportMtkWlan.kext`.
Package: `build/awdl-fix/AirportMtkWlan-AW-lifecycle.zip`.

After the intended candidate is loaded, the read-only runtime checker is:

```sh
python3 tools/awdl/check-windows.py \
  --expected-uuid BF3A7235-32B8-353F-9B66-82D427B0FC6C \
  --seconds 10 --output build/awdl-fix-live-check.json
```

It checks the loaded UUID before observing activity, then verifies new starts,
start/end balance and native sanity logs. An idle AWDL interface cannot pass
just because no errors were printed. The current check returns **unverified**
because the machine still runs the older UUID. No candidate was loaded, no
OpenCore files were edited, and no reboot was performed by this task. Native
RF timing, scan/preemption behavior and AirDrop transfer with this candidate
remain to be validated on hardware. Genuine absent/short/late firmware grants
still produce missed windows; the driver does not synthesize notifications to
hide missing RF availability.
