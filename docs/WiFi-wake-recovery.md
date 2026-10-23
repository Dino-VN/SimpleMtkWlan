# Wi-Fi wake recovery candidate — 2026-10-23

The inspected AirportMtkWlan boot could not restart Wi-Fi. The adapter remained
inactive after an enable request, with MCU command `0x46ed` timing out, WFDMA
interrupts masked, DMA enable bits absent, and the firmware's `NEED_REINIT`
marker cleared (`dummy_cr=0xffff0000`). Software ring indices still referred
to the previous DMA context. AWDL synchronization was disabled. Evidence and
the source baseline are in `build/airdrop-recovery-20261023-135314/`.

This is consistent with lost WFDMA context, but the snapshot does not establish
whether system sleep, firmware deep sleep or another firmware failure caused
it. The earlier AirDrop endpoint failure occurred while Wi-Fi worked: iPhone
discovery succeeded, service resolution timed out, and AWDL data RX stayed
zero. This recovery candidate does not establish a fix for that separate issue.

## Changes

- Initialization now requires successful host ownership and restores DMA when
  firmware clears `NEED_REINIT`, before sending the first MCU command. It uses
  the existing non-forced DMA reset; firmware is retained for this path.
- Recovery excludes queued interrupt callbacks through `IOWorkLoop::runAction`,
  masks hardware interrupts, rebuilds all six rings, refills RX, and restores
  DMA/interrupts. The gate contains no MCU response wait. Unallocated rings or
  an active interface cannot enter conditional recovery.
- DMA reset clears obsolete ring TXP pointers and returns old packet tokens
  and buffers exactly once, including during a complete firmware reload.
- AirportMtkWlan's power-on callback now enables the adapter when the user's
  Wi-Fi power preference is on. Power-off and power-on wait for the queued HAL
  transition before acknowledging PM, for up to four seconds. The wait releases
  the caller's gate so the task and MCU replies can progress. A timeout remains
  visible rather than claiming that the transition completed.
- A failed enable request makes one firmware reload attempt through the existing
  full-reset path. The pending ordinary reset is canceled first. Duplicate power
  tasks do not repeat the reload; a failed retry reports failure and leaves the
  interface down. Intentional Wi-Fi-off remains off at wake.
- Registry properties `MTKSleepStopStatus` and `MTKWakeStartStatus` expose PM
  transition results (`0` means success; a nonzero value is an IOReturn error).

The conditional recovery was checked against Linux v6.18
`mt792x_wpdma_reinit_cond` and `mt792xe_mcu_drv_pmctrl`. Retained reference:
`build/airdrop-recovery-20261023-135314/mt792x_dma.c`.

## Verification

Candidate UUID: `BECB9159-EADF-384A-829F-F695A1AB2003`.
Output: `build/wifi-wake-recovery/Release/AirportMtkWlan.kext`.
Unsigned Release, x86_64, macOS Tahoe (`__MAC_26_0`). It includes the preexisting
local AWDL changes. No installed driver or boot configuration was modified.

Production-function regressions pass under ASan/UBSan:

- 100 recoveries from lost DMA context; retained context; host ownership, busy
  DMA and RX allocation failures; gate ordering; partial attachment; live-ring
  protection; stale pointers; exact buffer/token reclamation; full-reset tokens.
- 100 PM sleep/wake cycles; completion-before-ACK ordering; Wi-Fi preference;
  one reload after a failed restart; duplicate suppression; failed retry status;
  bounded PM timeout; detachment.

The saved baseline compiles and fails both regressions at assertions. Existing
AWDL protocol/native-window, HAL, TXWI, TX-free and detach checks pass. The
Release build succeeds. Static checks match 569 AWDL virtual slots and 244
packet/pool/queue slots against the pinned local Tahoe kernel collection.
These tests establish source behavior in the harness and compiled ABI layout;
they do not establish kernel scheduling, firmware stability or RF operation.

## Hardware check

Install the candidate using the machine's existing boot-loader deployment path,
preserve the current driver for rollback, and reboot. Check that the loaded UUID
matches, connect Wi-Fi, sleep normally and wake. Run the package's
`Check-Wake.command` after wake. Repeat several cycles and check that Wi-Fi
reconnects, RX/interrupt counters advance, and MCU timeout counts do not grow.
The checker is read-only and does not put the computer to sleep or change Wi-Fi.

The four-second PM wait is bounded: a unusually slow firmware reload can finish
after it times out. The diagnostic reports that limit. A PCI/power failure that
prevents driver ownership can also defeat the single reload attempt.

AirDrop requires a separate real file-delivery test with advancing AWDL data RX
and no native-window sanity errors. Discovery or firmware multicast completion
alone is insufficient. The previously measured dense channel-6 to channel-149
schedule can still miss a window at approximately 32 ms grant latency; this
change does not alter that schedule.
