<!--
  README.md
  SimpleMtkWlan

  Created by laobamac (王孝慈) on 2026/5/5.
  Copyright © 2026 laobamac (王孝慈). All rights reserved.
-->

# SimpleMtkWlan

SimpleMtkWlan is an experimental macOS kernel extension for MediaTek MT792x PCIe
wireless adapters.

Author: laobamac (王孝慈)

## Status

This project is under active hardware bring-up. Current development focuses on:

- MT7921/MT7922 PCIe probe and attach
- Firmware loading
- DMA queue setup
- Hardware scan support
- Association/authentication TX path debugging

The driver is not release-stable yet.

## Supported Hardware

Currently targeted device:

- MediaTek MT7921, PCI ID `14c3:7961`
- MediaTek MT7921K/RZ608, PCI ID `14c3:0608`
- MediaTek MT7922, PCI ID `14c3:7922`
- MediaTek MT7922/RZ616, PCI ID `14c3:0616`

Other MediaTek devices are not currently supported.

## AirportMtkWlan (native Wi-Fi menu, macOS 15)

This fork adds a second target, `AirportMtkWlan`. It puts the same MediaTek
driver core behind IO80211/Skywalk, using laobamac's AirportItlwm Sequoia/WCL
glue, so the card shows up as a native Wi-Fi interface. You get the macOS Wi-Fi
menu, System Settings › Wi-Fi and `airportd`, with no helper app. It replaces
SimpleMtkWlan: **never load both at the same time.**

Tested on one machine only (Lenovo Legion Slim 5 16APH8, RZ616 `14c3:0616`,
macOS 15.8.1).

Works:
- scan on 2.4 and 5 GHz;
- WPA2-PSK join from the Wi-Fi menu;
- DHCP;
- 802.11ac VHT80 2x2;
- RX and TX A-MPDU (Block Ack);
- coexistence with MT7922 Bluetooth.

Known problems:
- download is capped at about 90-100 Mbit/s even when the link supports more,
  while upload is not (under investigation);
- no sleep/wake;
- no WPA3-only (SAE) networks;
- no 802.11ax and no 6 GHz;
- a firmware crash (for example, turning Wi-Fi off while connected on older
  builds) needs a cold boot to recover.

The kext is unsigned. SIP must allow unsigned and unapproved kexts
(`CSR_ALLOW_UNTRUSTED_KEXTS` | `CSR_ALLOW_UNAPPROVED_KEXTS`).

Build:

```sh
xcodebuild -project SimpleMtkWlan.xcodeproj -target AirportMtkWlan -configuration Debug ARCHS=x86_64 CODE_SIGNING_ALLOWED=NO build
```

`tools/mtkctl` (see `tools/mtkctl.c`) talks to either kext. It provides scan and
join for SimpleMtkWlan, and the driver log ring, debug counters and knobs for
both.

## Building

Requirements:

- macOS with Xcode
- Kernel SDK headers matching the local development setup
- The project-local firmware generation script and embedded firmware data

Build:

```sh
xcodebuild -project SimpleMtkWlan.xcodeproj -scheme SimpleMtkWlan -configuration Debug build
```

The debug kext will be produced by Xcode as `SimpleMtkWlan.kext`.

## Repository Layout

- `SimpleMtkWlan/` - kernel extension entry point and MediaTek HAL
- `SimpleMtkWlan/hal_mwx/` - MT7921/MT7922 driver implementation
- `mtk80211/` - compatibility, OpenBSD net80211, and support code
- `include/` - shared driver interfaces and generated firmware table
- `AirportMtkWlan/` - IO80211/Skywalk (WCL) front end for macOS 15
- `include/Airport/` - IO80211Family and Skywalk headers
- `tools/` - `mtkctl` command-line client
- `scripts/` - firmware generation helpers

## License

SimpleMtkWlan is distributed under GPLv2. See `LICENSE`.

Some source files include additional or more specific license notices inherited
from upstream GPL/BSD/OpenBSD/NetBSD/FreeBSD components. Those notices are
preserved in place and apply to their respective files.

## Credits

See `CREDITS.md`.
