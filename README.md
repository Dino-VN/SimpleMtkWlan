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

## AirportMtkWlan (native Wi-Fi menu, macOS 15 and 26)

This fork adds a second target, `AirportMtkWlan`. It puts the same MediaTek
driver core behind IO80211/Skywalk, using laobamac's AirportItlwm Sequoia/WCL
glue, so the card shows up as a native Wi-Fi interface. You get the macOS Wi-Fi
menu, System Settings › Wi-Fi and `airportd`, with no helper app. It replaces
SimpleMtkWlan: **never load both at the same time.**

Developed on one machine (Lenovo Legion Slim 5 16APH8, RZ616 `14c3:0616`,
macOS 15.8.1 and macOS 26.7.1). One more tester ran the 802.11ax build on an
MT7922 desktop (macOS 15.8.1) with a Wi-Fi 6 mesh AP. Sequoia and Tahoe use
different IO80211 ABIs, so each needs its own build (see below). A build only
starts on the macOS major version it was built for.

Works:
- scan on 2.4 and 5 GHz;
- WPA2-PSK join from the Wi-Fi menu;
- DHCP;
- 802.11ac VHT80 2x2;
- 802.11ax (HE) at up to 80 MHz, opt-in with the `amtk_he=1` boot-arg (experimental);
- RX and TX A-MPDU (Block Ack);
- coexistence with MT7922 Bluetooth.

Known problems:
- no sleep/wake;
- no WPA3-only (SAE) networks;
- 802.11ax is experimental and off by default; no 160 MHz, no 6 GHz;
- a firmware crash (for example, turning Wi-Fi off while connected on older
  builds) needs a cold boot to recover.

The kext is unsigned. SIP must allow unsigned and unapproved kexts
(`CSR_ALLOW_UNTRUSTED_KEXTS` | `CSR_ALLOW_UNAPPROVED_KEXTS`).

Build for macOS 15 (Sequoia 15.2 and later):

```sh
xcodebuild -project SimpleMtkWlan.xcodeproj -target AirportMtkWlan -configuration Debug ARCHS=x86_64 CODE_SIGNING_ALLOWED=NO build
```

Build for macOS 26 (Tahoe):

```sh
xcodebuild -project SimpleMtkWlan.xcodeproj -target AirportMtkWlan -configuration Debug ARCHS=x86_64 CODE_SIGNING_ALLOWED=NO AMTK_IO80211_TARGET=__MAC_26_0 build
```

A Sequoia build loads on Tahoe but never attaches (`AirportMtkWlan::probe`
fails right after `init`), so no Wi-Fi interface appears.

`tools/mtkctl` (see `tools/mtkctl.c`) talks to either kext. It provides scan and
join for SimpleMtkWlan, and the driver log ring, debug counters and knobs for
both. `mtkctl sta` prints the current link (mode, channel, width, RSSI, MCS,
rate, BSSID) without the SSID, so it is safe to paste into a report.

## Installing

Prebuilt kexts are on the [Releases](https://github.com/eiyuumiru/SimpleMtkWlan/releases) page. Download only one of
them: `AirportMtkWlan` (native Wi-Fi menu, recommended) or `SimpleMtkWlan`
(Ethernet-style, join with `mtkctl join`). For AirportMtkWlan, pick the zip for
your macOS version: `AirportMtkWlan-Sequoia` for macOS 15,
`AirportMtkWlan-Tahoe` for macOS 26. Both contain a kext named
`AirportMtkWlan.kext`.

Before you start, remove itlwm, AirportItlwm, or any other driver for the card,
and any SSDT that disables the Wi-Fi PCI device. Check that the card shows up
in `ioreg -l | grep pci14c3`. Bluetooth is not handled by these kexts.

### Load after boot (tested)

```sh
sudo mkdir -p "/Library/Application Support/MtkWlan"
sudo cp -R AirportMtkWlan.kext "/Library/Application Support/MtkWlan/"
sudo chown -R root:wheel "/Library/Application Support/MtkWlan/AirportMtkWlan.kext"
sudo kmutil load -p "/Library/Application Support/MtkWlan/AirportMtkWlan.kext"
```

The first load is usually refused:
1. Click **Allow** in System Settings › Privacy & Security.
2. Reboot.
3. Run the `kmutil load` command again.

Every new build needs approving again. To load the kext at every boot, run the
same `kmutil load` command from a LaunchDaemon with `RunAtLoad`, a few seconds
after boot.

If you also run other unsigned kexts from the Auxiliary Kernel Collection (for
example NullMoth), approving a new kext makes macOS rebuild that collection,
and it can leave the others out. Check that they are all still loaded after
the reboot.

To uninstall, remove the LaunchDaemon and
`/Library/Application Support/MtkWlan`, then reboot.

### OpenCore (untested)

Add the kext to `EFI/OC/Kexts` with a `Kernel › Add` entry:
- `ExecutablePath` = `Contents/MacOS/AirportMtkWlan`
- macOS 15 build: `MinKernel` = `24.0.0`, `MaxKernel` = `24.99.99`
- macOS 26 build: `MinKernel` = `25.0.0`, `MaxKernel` = `25.99.99`

It does not depend on Lilu. Keep a backup EFI.

### Boot arguments

| Boot-arg | Effect |
|---|---|
| `-novht` | disable 802.11ac |
| `-noht40` | disable 40 MHz channels |
| `amtk_cc=XX` | AirportMtkWlan: override the country code |
| `amtk_he=1` | AirportMtkWlan: offer 802.11ax (experimental, 80 MHz, no 160 MHz). `mtkctl knob 0x1002` turns it off again from the next join. |

### Troubleshooting

| Symptom | Fix |
|---|---|
| `kmutil load` says "not approved" | Approve the kext in Privacy & Security, then reboot. Also check that SIP allows unsigned kexts. |
| The kext loads but there is no Wi-Fi | Another driver owns the card, or an SSDT hides it. |
| Wi-Fi died and does not come back after a restart | The firmware crashed. Shut down fully, wait 10-15 s, then power on. |
| Bluetooth disappeared together with Wi-Fi | A chip reset (`mtkctl reset`) also takes down Bluetooth. Reboot. |

When reporting a problem, include:
- your PCI ID;
- your macOS version;
- the output of `mtkctl sta`, `mtkctl debug` and `mtkctl log`;
- whether `amtk_he=1` is set.

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
- `AirportMtkWlan/` - IO80211/Skywalk (WCL) front end for macOS 15 and 26
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
