# AirDrop endpoint candidate — 2026-10-23

AirDrop on the inspected boot discovers the iPhone but fails to resolve its
service endpoint. `sharingd` records `resolveFailure`, then `missingEndpoint`
with zero file bytes and no TLS certificate digests. Discovery action frames
arrive, but raw/native AWDL data RX stays at zero. Successful ROC requests
and DMA submissions alone do not establish peer reception.

The diagnosis is retained in
`build/airdrop-diagnosis-20261023-current/report.md`. Its loaded UUID was
`A33533B2-7B18-3B11-BB71-689B9EF70189`; the exact source provenance of that
binary was not established. Baseline source snapshots for this change are
in `build/awdl-endpoint-fix/baseline/`. Existing local changes are preserved.

## Candidate behavior

- **Peer schedule parsing:** a captured iOS 26 MIF uses different master
  addresses in synchronization parameters and election v2. The parser now
  retains the valid radio schedule and uses the election-v2 root for election
  decisions. A sanitized real-frame regression verifies that the Mac still
  cannot elect its own follower. A missing selected parent is not by itself
  an error when this Mac is operating as master.
- **Multicast:** queued multicast data, including service-resolution traffic,
  waits for EAW slot 0 or 10 of the 16-slot cycle and a 16-TU edge guard.
  The guard is capped at one-quarter of the window in short presence modes.
  Packet bytes and the original queue deadline are retained while waiting.
  A live matching firmware grant is still mandatory.
- **Radio grants:** same-channel windows separated by idle slots share one
  reservation where possible. A different channel terminates coalescing;
  trailing idle slots do not enlarge it. The existing 1100-ms dwell cap and
  physical grant checks remain in force. Idle slots never become native AWs.
- **Scan arbitration:** an actual firmware scan is canceled once, under the
  AWDL operation generation guard. Invalid or busy reservations do not cancel
  it. Further scan requests remain pending while AWDL is enabled; disabling
  AWDL schedules scan completion/recovery once. Short, inactive, stale-sequence
  and duplicate scan completions cannot restart the old cancellation loop.
- **Firmware TX evidence:** AWDL unicast, multicast and action traffic use
  separate software PIDs and request firmware TX status. Reserved WCIDs
  15–18 are handled independently of infrastructure rate sampling. Packed
  MCU TX-done events now reach the status decoder. Published counters
  distinguish unicast ACKs, multicast/action completion, and firmware
  queue/RTS/ACK failures. Multicast completion does not prove peer reception.
  The data checker reports these failures and counter resets and excludes
  last-status/sequence/PID/WCID gauges from counter deltas.

The multicast and parser rules were checked against the retained OWL source
under `build/reference-ios26-owl-v9/`. TX status layout was checked against
Linux v6.18 `mt7921/mac.c` and `mt76_connac2_mac.h`, retained in
`build/awdl-endpoint-references/`. The package records exact file hashes.

## Validation

Candidate UUID: `4E711087-6AC2-387E-B0D3-E838BB36FFF1`.
Target: unsigned Release `AirportMtkWlan.kext`, Tahoe (`__MAC_26_0`), x86_64.
Output: `build/awdl-endpoint-fix/Release/AirportMtkWlan.kext`.

Host validation passes for protocol parsing and mutation tests, production
native-window scheduling, multicast queue retention, idle-gap radio planning,
HAL firmware builders and teardown, TXWI construction, TX-status dispatch,
scan request generation/arbitration, and data-checker interpretation. Scan
coverage includes 100 repeated deferred requests, invalid/busy ROC calls,
reset during cancellation, foreground/background recovery, and stale/short/
duplicate completion events. Fifteen additional control, lifecycle, transport
ownership and diagnostic suites passed; individual results and logs are in
`build/awdl-endpoint-fix/`.

The saved old source fails the parser, multicast, idle-planner, TXWI,
TX-status, and scan-wrapper regressions at assertions after compiling.
These checks establish the tested source defects and resulting behavior;
they do not establish that those defects explain every hardware symptom.

The final Release build succeeds. Static checks match 569 compiled AWDL
virtual slots and 244 packet/pool/queue slots against the disk Tahoe kernel
collection, SHA256
`21d6da1c4c3e7b72dddf5144da8a4c4b48e294249a16018a5006b61bb2155ccc`.
ABI matching does not validate kernel object lifetime or hardware stability.

The measured sparse 6/149 replay produces all 32 expected starts after
startup. The idle-separated same-channel case reduces four reservations to
one. The historical dense 19.261-ms switching-latency replay still reports
377 starts and 212 skipped windows in its approximately 40-second interval.
The candidate does not fabricate starts when the radio cannot cover them.

## Remaining hardware validation and limits

This candidate has not been loaded. AirDrop transfer and raw data RX are
unverified. Long firmware grant latency and dense channel schedules can
still violate native timing. The diagnosis does not establish an internet
DNS, Apple ID, or Bluetooth defect.

Scan deferral prioritizes AWDL on this single radio. It may delay Wi-Fi
network discovery, roaming or association until AWDL is disabled. This is a
material limitation, especially if the OS keeps AWDL enabled for a long time;
the change is not a complete simultaneous scan/AWDL arbitration solution.

The package includes `Check-AirDrop.command`, which requires the exact
candidate UUID and runs concurrent 30-second window/data checks. After
installing this kext through the machine's existing boot-loader deployment
path and performing a normal reboot, run the checker while attempting a
small AirDrop transfer in both directions. Successful acceptance requires
actual file delivery, advancing raw/native RX and firmware TX status, and
no native sanity failures. Passing counters alone is insufficient.

No hot-unload, reboot, boot configuration edit, or installed-kext replacement
was performed for this candidate. No rollback binary is supplied as matching
the inspected boot because that binary's provenance is unknown. Preserve
the user's current working deployment before testing a replacement.
