# AWDL raw data transport follow-up

The installed queue-activation build (`b24320d`, UUID
`F79AE847-84BA-3E34-91B7-CE20A1707920`) accepts BSD/native TX, but its BSD and
native RX counters remain zero. Management peer discovery alone does not prove
data transport. This change fixes four source-confirmed data-path defects and
exposes the stages needed to locate any remaining radio/peer failure.

## Corrections

* Native Ethernet preparation calls the virtual `getHardwareAssists` before
  `ifnet_set_offload`. The inherited implementation exposes offloads although
  our submission callback only copies bytes and metadata is discarded. Return
  zero so the network stack completes checksums and segments packets before
  raw AWDL submission. The installed interface advertised TSO4, TSO6,
  PARTIAL_CSUM and ZEROINVERT_CSUM; the replacement must remove those options.
* MT7921 hardware deaggregation is enabled in `mwx_mac_init`, while its raw RX
  alignment correction was compiled out. Apply the mt76 two-byte header
  relocation/pull only to RXD4-marked, unprotected NoDS AWDL QoS A-MSDUs.
  Infrastructure frames and packets without that descriptor marker are untouched.
* Decode bounded A-MSDU subframes using their DA/SA/length and four-byte
  inter-subframe alignment. Validate all subframes before any delivery, require
  each source to match the transmitting peer, validate AWDL LLC/header and exact
  IPv6 length, and apply the existing replay window to each AWDL data sequence.
  Fragmented, protected, HT-control and mesh frames remain unsupported.
* Expire queued data on each service pass, including idle/no-grant periods.
  Previously the one-second limit ran only inside the granted TX loop, so a
  full queue could indefinitely block new BSD packets while ROC failed.

Peer membership and radio/channel validation remain in place. In particular,
this change does not manufacture a schedule for an expired peer, or treat
multicast self-echo as a received RF frame.

## Evidence

Pinned Tahoe BootKernelExtensions.kc SHA256:
`21d6da1c4c3e7b72dddf5144da8a4c4b48e294249a16018a5006b61bb2155ccc`.

Offline disassembly in `build/awdl-rx-fix/native-offload-evidence.json` records
the exact function bytes/file offsets. At VA `0xffffff8002b10f08`, native
Ethernet preparation calls `getHardwareAssists` virtually, then stores its
result and converts it at `0xffffff8002b10f5b` before calling
`ifnet_set_offload` at `0xffffff8002b10f67`.

Independent wire references:

* [OWL A-MSDU RX](https://github.com/seemoo-lab/owl/blob/master/src/rx.c)
  (`awdl_rx_data_amsdu`): subframe header, bounded payload and four-byte padding.
* [mt76 MT7921 RX](https://github.com/openwrt/mt76/blob/master/mt7921/mac.c)
  (`mt7921_mac_fill_rx`): RXD4 payload-format and two-byte correction when
  header translation is disabled. Exact fetched digests are saved with the
  candidate evidence, since these upstream branch URLs can change.

The installed build has no raw data-stage counters or permitted BPF capture.
These defects are established by source/native contracts; there is no capture
proving that every missing RX packet was an A-MSDU or had an incomplete checksum.

## Checks and installation verification

ASan/UBSan tests cover every Ethernet size 54..1514, two-subframe aggregates,
all alignment cases, two-byte hardware padding, truncated/invalid lengths and
spoofed sources, 200,000 mutations, actual receive replay/destination/peer
guards, HAL padding dispatch, actual TX failures and full-queue expiry/order.
The existing lifecycle, sync, controls, initialization and scheduler tests also
run. Release builds target x86_64/macOS 26; the static ABI check compares 569
virtual slots with the pinned native kernel.

The candidate is `build/awdl-rx-fix/Release/AirportMtkWlan.kext`; its ZIP,
UUID, hashes, check results and runtime baseline are in the same directory.
Installing it and rebooting are separate from building it.

After loading the UUID in `verification.json`, run:

```sh
python3 tools/awdl/check-data.py --expected-uuid NEW_UUID --seconds 30 \
  --output build/awdl-rx-fix/runtime-after.json
```

Generate peer traffic by opening AirDrop on a nearby device. The checker
requires new native/BSD TX and RX for a pass. New `MTKAWDLDataTxSubmitted`,
`DataTxFailed`, `DataTxExpired`, `DataTxStatus`, `DataTxPending`, `DataRxFrames`,
`DataRxInvalid`, `DataRxUnknownPeer`, `DataRxWrongDestination`, `DataRxReplay`
and `DataRxDecoded` properties distinguish acceptance, HAL submission, expiry,
raw RX and decoder rejection. They publish once per second. HAL submission
success does not prove a firmware ACK or a completed AirDrop transfer.

If `DataRxUnknownPeer` increases, investigate host/native peer lifetime next;
if `DataRxFrames` stays zero, investigate firmware/filter/channel delivery.
If `DataRxDecoded` increases while native RX stays zero, inspect Skywalk RX
allocation/completion and datapath state.
