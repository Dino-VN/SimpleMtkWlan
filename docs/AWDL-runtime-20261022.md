# AWDL runtime check, 2026-10-22

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
