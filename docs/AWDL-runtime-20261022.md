# AWDL runtime check, 2026-10-22

Correction: this historical report's classification of BSD TSO/partial
checksum flags as unsupported hardware is superseded by
[the native-host offload investigation](AWDL-offload-fix.md). Tahoe may
advertise these flags for software processing after saving driver assists.

## Continuous-window candidate boot at 14:48:30 +0700

The user updated/rebooted into the audited candidate at commit `fbbe85f`.
Read-only inspection confirms loaded UUID
`1B8AC89E-50DC-34A9-B5CF-0D6A4D12E513`, with active infrastructure `en0`
and native `awdl0`. This supersedes the prior not-loaded observation; host
tests passed, but **this hardware run fails native window validation**.

From this boot through 14:52:07, native logged 545 AWDL sanity failures:
542 skipped-start messages, two short ends (47TU and 45TU versus 64 +/-10TU),
and one 83ms start interval versus 65 +/-10ms. Initially the driver had
876 starts/875 ends; later it stopped at 1102/1102. Host/native programmed
channel sequences match. These counters and matching sequences do not prove
correct timing, and the raw logs do not identify the precise cancellation
or clock-update path responsible for the short ends.

Two subsequent 30-second observations, including one after the user opened
AirDrop on both devices, produced zero new starts/ends and no new sanity log.
They are **unverified**, not passed: the timer advanced 14700/14727 ticks and
received 171/42 action frames, while host channel stayed zero and host role
was follower (2). The source returns channel zero for a follower without a
synchronized selected parent; receiving frames from other peers alone cannot
activate that schedule. The selected-parent lifecycle needs further diagnosis.

BSD totals initially showed 21 received/91 transmitted packets with zero
interface errors. HAL data totals were 21 decoded RX, 22 submitted TX,
55 failed TX and 9 expired TX (later 10). Unsupported TSO4/TSO6/partial
checksum flags remain enabled despite the offload setter's status zero.
At 14:56:19 and 14:56:35, sharingd logged service resolver failures followed
by fallback. No accepted file transfer is established by this run.

Evidence is saved locally under `build/awdl-window-fix/` as
`runtime-updated-summary.json`, `runtime-updated-boot-sanity.ndjson`,
`runtime-windows-updated.json`, `runtime-windows-airdrop-open.json`,
`runtime-updated-active-samples.json`, and registry/recent-log snapshots.
Private raw runtime logs remain excluded from source control. The audit
performed read-only checks; it did not unload, install, or reboot the driver.

## Earlier RX/peer/radio candidate

The RX/peer/radio candidate at commit `3ae12bc` built and passed the seven
host regression suites, 569 AWDL ABI slots and 244 packet/queue ABI slots.
Its executable UUID is `D957401C-783E-3FFF-AF3F-7203782A039F` and SHA256 is
`32d0fd00b48c1165b20d560872707816299406166e2398f5375a0f354bd2857e`.

Authorized `kmutil load -p` returned exit 27 (approval required). Normal
unload returned exit 3 because no AirportMtkWlan was loaded.
`kmutil load --no-authorization -p` returned exit 28 (reboot required) and
rebuilt Auxiliary KC containing the exact candidate and RemoteVirtualInterface.
The existing four NullMoth graphics extensions remained included.

On the subsequent boot at 12:21, the intended UUID and its IO80211Family,
corecapture and IOSkywalkFamily dependencies were loaded. Wi-Fi `en0` was
active with an IPv4 address; native `awdl0` existed and was active.

| Check | Observation |
| --- | --- |
| AWDL_ADVERTISERS | 79 calls, status 0, last stage duplicate |
| Peer/timestamp correlation | Last matched RX age 418253 microseconds |
| Sync | Disabled during the later 20-second observation; last status 0 |
| Radio/MI | 9719 reserve attempts, 898 MI submissions, no interval increase |
| Firmware ROC | 9715 submissions, 873 events, 597 accepted grants, 276 rejected |
| Native windows | 5 starts and 5 ends; 5 skipped-AW-start sanity failures |
| BSD traffic | RX 6 / TX 66, zero interface errors, zero interval increase |
| Data transport | 6 decoded RX, 4 HAL TX submissions, 37 expired TX |
| AirDrop | Attempt 13:10:53–13:12:15 failed with missingEndpoint, size 0 |

Two service resolver failures preceded the AirDrop send failure. Pseudonym
provisioning failures were also logged; they do not establish the cause of
the resolver failure or a Bluetooth driver defect.

`awdl0` still advertised TSO4, TSO6, PARTIAL_CSUM and ZEROINVERT_CSUM despite
BSD offload setup reporting status 0. No panic report newer than this boot
was found. Limited RX and absence of a report do not establish stability or
successful file transfer. Native window timing, offload lifecycle and
bidirectional transfer still require verification.

Local raw evidence is under `build/awdl-goal-fix/hotload-20261022` and
`build/awdl-goal-fix/check-table-20261022`; generated bundles, logs and private
runtime artifacts remain excluded from source control.
