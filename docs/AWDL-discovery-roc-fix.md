# P2P discovery context and ROC management TX

The 2026-10-23 boot loads the ROC-ACK candidate
`17E9B561-A5D5-33A0-A502-B471DC377ADC`. The active AirDrop measurement in
`build/airdrop-check-20261023/active-windows.json` fails with 12 native sanity
messages, 8 missing-start errors and 38 missing-start warnings over 30 seconds.
There were 18 starts and 19 ends, with one window already open at the initial
snapshot. The concurrent data observation submitted three new packets and
received no new data. Separate registry snapshots show near-one-second grants
and repeated ROC timeouts despite successful command ACKs.

This candidate corrects three source/reference mismatches. Hardware improvement
and an AirDrop file transfer remain unverified until this exact candidate boots.

## Changes and evidence

### Disconnected P2P discovery BSS

The retained `mt76_connac_mcu_uni_add_dev` in
`build/reference-mt76-v6/mt76_connac_mcu.c:1192` initializes `conn_state=1`.
Its `NL80211_IFTYPE_P2P_DEVICE` case uses `CONNECTION_P2P_GO` but does not
populate a BSSID, PHY mode or legacy PHY mask. The separate
`mt76_connac_mcu_uni_add_bss` path at line 1540 populates these fields and
sets `conn_state=!enable`; `mt7921_start_ap` additionally configures BSS PM
and the broadcast station.

The AWDL constructor mixed those paths: it registered AP|P2P with
`conn_state=0`, an AWDL BSSID and 2.4-GHz PHY fields, without the GO beacon/PM
setup. It now matches the disconnected P2P discovery constructor. The DEV
MAC remains the AWDL local address; transmitted raw 802.11 frames still carry
the AWDL protocol BSSID. The exact BSS wire regression checks both enable and
disable, transport failure/epoch interruption and infrastructure isolation.

### Self-contained initial ROC

`mt7921_mcu_set_roc` in the retained
`build/reference-mt76-v7/mt7921/mcu.c:766` includes the control/center channel,
band, width and requested dwell. The MT76 P2P discovery device has no permanent
channel context. AWDL previously called the synchronous RLM setter before its
first acquire, establishing a persistent channel on the discovery BSS.
That call is removed. Initial and subsequent acquisitions both use the
self-contained ROC packet. The optional explicit preparation API remains
available but is not invoked by the AWDL scheduler.

The production HAL regression now verifies that a cold acquire emits exactly
one ROC command and no RLM, for channels 6, 44 and 149. Even a mocked slow or
failing BSS response cannot affect the cold acquire. Grant/token matching,
regulatory checks, abort retry, teardown, timeout and packet ownership checks
remain in force.

### ALTX for ROC action frames

The additional pinned Linux v6.18 references in the build directory establish
the complete routing chain:

- `mt7921-pci-v6.18.c:239` enables `MT_DRV_HW_MGMT_TXQ`.
- `mac80211-offchannel-v6.18.c:1034` marks ROC management TX as off-channel.
- `mt76-tx-v6.18.c:352` puts it on the off-channel pending list; line 617
  selects `MT_TXQ_PSD` for management frames on that list.
- `mt76_connac_mac-v6.18.c:527` maps PSD to `MT_LMAC_ALTX0`.

AWDL previously initialized every TXWI with `qid=MT_TXQ_BE`, causing PSF/MIF
to use WMM1 VO. The AWDL management path now chooses PSD/ALTX. Data retains
its QoS WMM queue. Four production TXWI cases check both PSF/MIF and
broadcast/unicast, the exact ALTX queue, cut-through format, OMAC/WCID and
ACK flags. Existing data descriptor checks and infrastructure management/RA
checks pass. Management and data transmission still require a matching live
ROC grant before the descriptor is submitted.

## Validation

The new BSS packet, cold ROC and management-queue assertions each fail against
the captured previous source and pass against the corrected source. Raw
failure logs are under `build/awdl-discovery-roc-fix/regression-*-before.log`.
All 19 relevant suites pass, including the production HAL, protocol/scheduler,
native controls, lifecycle, TXWI and TX cleanup under their sanitizer harnesses.
The Release x86_64/Tahoe build succeeds. The compiled 569 AWDL virtual slots
and 244 Skywalk packet/pool/queue slots match the pinned disk KC.

Candidate UUID: `13EE01BA-6B06-3C39-81EE-8539A0766814`.
Executable SHA256:
`24d9b594a00308eaab11a65b97c73e9aaca1f161b47a99bdc5b826b31180d677`.
Package:
`build/awdl-discovery-roc-fix/AirportMtkWlan-AWDL-discovery-ROC-fix.zip`.

Host regressions prove corrected construction/routing, not faster firmware
arbitration, native continuity or on-air delivery. The earlier 19.261-ms
switching replay still represents a physical delay exceeding native tolerance;
no timing tolerance, grant acceptance or reported AW timestamps were relaxed
to hide that case. Other AWDL interoperability/authentication gaps can remain.

### Hardware follow-up, 2026-10-23 11:34

After the 11:29 reboot this exact candidate is loaded. A registry snapshot
records 444 ROC submissions and 444 grants, no rejected grants/timeouts/command
failures, and a last grant delay of 12057 us (maximum 273159 us). However, the
active 30-second window check still has 51 skipped-start sanity failures.
Data RX remains zero while action discovery frames arrive. The user reports
that the Mac sees the iPhone but sending fails; sharingd logs `missingEndpoint`
and subsequent application-service `resolveFailure` after DNS stalls. AirDrop
is therefore still failing. Detailed evidence and interval distinctions are in
`build/awdl-discovery-roc-fix/runtime-check-20261023/report.md`.

Update the kext using the existing installation method and boot normally.
Open AirDrop on this Mac and the nearby peer, then run the packaged
`Check-AirDrop.command` or:

```sh
python3 tools/awdl/check-windows.py \
  --expected-uuid 13EE01BA-6B06-3C39-81EE-8539A0766814 \
  --seconds 30 --output build/awdl-discovery-roc-fix/runtime-windows.json
python3 tools/awdl/check-data.py \
  --expected-uuid 13EE01BA-6B06-3C39-81EE-8539A0766814 \
  --seconds 30 --output build/awdl-discovery-roc-fix/runtime-data.json
```

Compare ROC timeout/grant counts and latency, native missing/skipped starts,
PSF/MIF reception and actual file transfers in both directions. The diagnostic
property `MTKAWDLFirmwareContext=p2p-discovery` identifies this context.
The package includes the previous ROC-ACK kext as a rollback. No kext was
installed and no boot configuration or running services were changed while
preparing this candidate.
