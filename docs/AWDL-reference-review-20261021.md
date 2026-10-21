# AWDL reference review — 2026-10-21

## Scope and conclusion

Reviewed the published C/C++/header sources in AirportItlwm-Tahoe, omdrop-owl's pinned OWL implementation and patches, and relevant GitHub issue/PR discussions. This is reference research; no driver changes, build, installation or new live test were performed.

The sources identify ioctl `AWDL_AWDL_ADVERTISERS` as 229 and the availability-window-start message as 42. They do **not** supply a definition of `awdl_peer_advert_add`, its native setter implementation, or evidence for the AW-start message payload layout. OWL's on-air TLVs must not be substituted for either native ABI.

This conclusion covers the searched source files and discussions, not disassembly of packaged beta binaries. Issue discovery covered the 100 most recently updated entries per user-supplied repo; it was not an exhaustive search of all issue history.

## Pinned references

- AirportItlwm-Tahoe: `9b7d5ffd72099cc75d358bb203e9608c599172d6`, local `build/reference-AirportItlwm-Tahoe-20261021`.
- omdrop-owl: `8213aee9f018ffd78a3fc71863a364fcddd938cd`, local `build/reference-omdrop-owl-v9`.
- OWL dependency: `832d70f815c3d4a06a02117bf0fc5e868daa1ff0`, local `build/reference-ios26-owl-v9`; confirmed by omdrop's `pins` file.

## Native macOS declarations

- [ioctl 229](https://github.com/kgp-macPro/AirportItlwm-Tahoe/blob/9b7d5ffd72099cc75d358bb203e9608c599172d6/include/Airport/apple80211_ioctl.h#L317).
- [event 42](https://github.com/kgp-macPro/AirportItlwm-Tahoe/blob/9b7d5ffd72099cc75d358bb203e9608c599172d6/include/Airport/apple80211_var.h#L652).
- [virtual ioctl setters](https://github.com/kgp-macPro/AirportItlwm-Tahoe/blob/9b7d5ffd72099cc75d358bb203e9608c599172d6/AirportItlwm/AirportVirtualIOCTL.cpp#L206): `setSYNC_ENABLED` stores a flag; `setAWDL_SYNC_STATE` stores state; `setAWDL_SYNC_PARAMS` logs and returns success. These functions do not establish a complete radio synchronization implementation.
- [AWDL lifecycle notifications](https://github.com/kgp-macPro/AirportItlwm-Tahoe/blob/9b7d5ffd72099cc75d358bb203e9608c599172d6/AirportItlwm/AirportItlwm.cpp#L566): enables the virtual interface and updates its link state. Useful lifecycle reference, not proof of AW-start reporting.

## Useful OWL synchronization code

- [sync.c](https://github.com/jedbillyb/owl/blob/832d70f815c3d4a06a02117bf0fc5e868daa1ff0/src/sync.c#L23): AW period 16 TU, default presence 4; EAW is therefore 64 TU = 65.536 ms. Current AW counter and next EAW boundary derive from an epoch and baseline counter. `awdl_sync_update_last` reconstructs the epoch from the received countdown and masks the baseline counter to a multiple of four. That mask assumes the default presence, so it is not a generic rule for every configuration.
- [rx.c](https://github.com/jedbillyb/owl/blob/832d70f815c3d4a06a02117bf0fc5e868daa1ff0/src/rx.c#L34): reads countdown at offset 1 and AW counter at offset 29 **within the sync TLV value**. Records signed phase offsets per peer; only the elected sync master updates the local clock.
- [MIF scheduling](https://github.com/jedbillyb/owl/blob/832d70f815c3d4a06a02117bf0fc5e868daa1ff0/daemon/core.c#L184): sends on a nonzero current channel and rearms for the middle of the next EAW. The host send time must be distinguished from actual RF transmit time.
- [channel scheduling](https://github.com/jedbillyb/owl/blob/832d70f815c3d4a06a02117bf0fc5e868daa1ff0/daemon/core.c#L286): chooses the channel from the current EAW slot and rearms at the next boundary. Does not advance its current-channel state when submission fails. Its asynchronous Linux channel request is not a native macOS AW-start event.
- [unicast gate](https://github.com/jedbillyb/owl/blob/832d70f815c3d4a06a02117bf0fc5e868daa1ff0/src/schedule.c#L32): decodes the peer sequence with the peer's encoding, compares channels and applies guard timing. Documents how an encoding mismatch can allow RX while preventing all unicast TX. Applying arbitrary nonmaster clock offsets is explicitly cautioned against.
- [wire TLVs](https://github.com/jedbillyb/owl/blob/832d70f815c3d4a06a02117bf0fc5e868daa1ff0/src/frame.h#L102): sync/election/channel fields. Election v2 carries separate top-master and sync-node addresses. Their presence does not alone determine whether a captured mismatch is valid.
- [metric-first election patch](https://github.com/t4t5/omdrop-owl/blob/8213aee9f018ffd78a3fc71863a364fcddd938cd/patches/owl-04-election-metric.patch#L57): author's Apple capture observations motivated metric-before-counter ranking. Current MTK host election already ranks metric first; this is not an entirely missing feature.

## MediaTek-specific radio evidence

- [PR 24](https://github.com/t4t5/omdrop-owl/pull/24) adds an active monitor carrying the station MAC to ACK incoming unicast on Linux cards without IBSS. That is a radio/MAC setup reference, not a native macOS ioctl handler.
- [Independent MT7922 capture](https://github.com/t4t5/omdrop-owl/issues/14#issuecomment-6127187359): injected unicast used 1 Mbps CCK regardless of the radiotap request; 0/132 appeared over air on channel 44, versus 115/121 on channel 6 with 100 ACKed. Reporter identified `mt76_connac2_mac_write_txwi` ignoring `IEEE80211_TX_CTRL_RATE_INJECT` as the likely cause.
- [MT7921 follow-up](https://github.com/t4t5/omdrop-owl/issues/14#issuecomment-6177921979): a cleaned rate fix broadened to MT7921 PCIe `14c3:7961` produced successful iPad transfers both ways on channel 44. This establishes a relevant Linux failure mode and remedy, not proof that the macOS TXWI path has the same defect.
- [PR 55](https://github.com/t4t5/omdrop-owl/pull/55): opt-in P2P-GO setup for a tested MT7922 gives monitors the group's MAC; rebased validation confirms a Mac-to-Linux upload, with limitations documented. It does not establish concurrent infrastructure Wi-Fi or native macOS compatibility.

## Relationship to the current MTK source

At review time `AirportMtkAwdlInterface.hpp:95` still returns unsupported for advertisers. Current working source also contains `notifyAvailabilityWindowStart` at `.cpp:506`, posting message 42 with `NULL, 0`, called when an allowed transmit channel is newly observed. Its comment claiming an empty legacy payload is **not validated by these references**. This callback is a newer source change than the previously tested Claude build; this research does not prove it is built, loaded or accepted by the native peer manager.

Further implementation evidence should establish the native AW-start consumer's required payload/length and timing semantics, and the advertisers producer/consumer's field offsets, sizes, versioning and ownership. Then correlate AW counter/channel/boundary with a real matched firmware ROC grant. Merely posting message 42 or returning success for ioctl 229 does not verify synchronization.

The OWL findings also justify checking actual MIF RF transmission, channel encoding, clock phase, TXWI rate and MAC/WCID/ACK setup. Successful TX enqueue and ROC counters alone cannot establish those results.

Saved GitHub discussion data: `build/awdl-github-issues-20261021.json` and `build/awdl-github-comments-20261021.json`.
