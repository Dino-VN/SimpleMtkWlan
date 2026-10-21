# V10 live evidence and V11 sync candidate (2026-10-21)

V10 boot UUID 66AB134B-B70B-391B-B175-72F6BF9F7D84. The retained 17:31
diagnostic confirms native awdl0, en0 RUN, 10 host-accepted/native-delivered
iPhone frames and native peer OBSERVED → ROUTABLE at 17:27:18. Station
disconnect/re-enable succeeds, without V9 duplicate 0x10003 in retained logs.
MI/TX and ROC events/grants remain zero. V10 had no ROC submit counter.

Full boot native log build/awdl-v11-native-boot.log shows missing AW-start
events before overlapping sync enables return NotReady at 17:28:36, then
native LinkDown/doDisable. Reserve is rejected during continuous infra scans.

V11 serializes sync requests on the controller command gate across firmware
waits. Concurrent requests wait for the current owner; a self-recursive call
returns Busy; owner waits are bounded. Real firmware failures propagate.
Duplicate enable of the same already-enabled MAC succeeds even if a ROC or
peer command owns the HAL context. MAC replacement is blocked during sync.
Only the native superclass and reportLinkStatus perform enable link updates,
matching the pinned BCM implementation; the redundant explicit link update
is removed. Diagnostics expose transition state, waits/failures, native link,
actual ROC submits/send failures and scan/busy blockers. No grants fabricated.

Host concurrency, failure, teardown and packet completion tests pass; 569 AWDL
slots,244 native packet slots,1120 kernel imports match the pinned KC.
V11 has not booted; RF synchronization/AW events, ROC grants, AirDrop transfer
and kernel lifecycle remain unvalidated. Package artifacts/awdl-native-v11.

# Tahoe native backend investigation

Current hardware: Darwin 25.6.0, macOS 26.7.1 (25G241), x86_64 MT7921.
V8 UUID `8D2ECD60-8990-38B4-AC02-758D7F7B21FF` is loaded after the
2026-10-21 15:02:03 boot. Live tests at 15:08 and 15:16 confirm en0 remains
active, native awdl0 has Wi-Fi AWDL identity, repeated creation returns success,
and firmware/sync are enabled. No new panic report was found after this boot.
This observation does not validate teardown or all panic paths.

Native logs report unsupported AWDL_AF_TX_MODE (requested mode 3) and
AWDL_OOB_AUTO_REQUEST, with repeated "could not send Master Indication frame
template to fw" errors. Both the host and native peer managers report zero
peers; BSD awdl0 packet counters remain zero. sharingd logged resolveFailure
at 15:05:55 and missingEndpoint at 15:06:45. Action reception counters increase,
but they are incremented before RSSI/parser checks, so they do not prove a peer
was accepted. Raw frame contents and the exact rejection reason are not yet
captured. AirDrop transfer remains unvalidated. Logs are retained in
artifacts/awdl-native-v8/diagnostics/; runtime-check.json records the scope.

The v8 Test-AWDL.command now uses LC_ALL=C because ioreg can print binary MAC
OSData as invalid UTF-8, causing awk to truncate registry snapshots. This is a
userspace diagnostic fix; the loaded kext binary is unchanged.

V7 investigation found two specific mismatches: BSD CARD_CAPABILITIES copies
21 bytes starting after version, so wifip2pd's offset+4 test is capabilities[4]
bit0; and Tahoe setChannelSequenceUnconditional writes descriptors at ioctl
+0xc, channel at+0x10, flags at+0x14. The old header started descriptors at
+0x10 and interpreted flags as channel. Static evidence is in build/awdl-v7-*
files, against the KC digest below. V7 accepts native 110/440ms PSF periods
and secondary social channels; it retains unsupported MI/AF requests until
transmit mode and packed MI scheduling fields are verified. New counters
measure service ticks, ROC/grants, action submission and reception; successful
TX enqueue does not prove over-the-air transmission.

## Evidence identity

Disk `/System/Library/KernelCollections/BootKernelExtensions.kc` SHA256:
`21d6da1c4c3e7b72dddf5144da8a4c4b48e294249a16018a5006b61bb2155ccc`.
IOSkywalkFamily UUID `A6EDB8DB-175B-3A49-8919-5769FCDB6BED` matches the
00:44 panic. Selected static instructions and vtable slots are saved in
`artifacts/awdl-panic-fix-v3/diagnostics/awdl-backend-*.txt` and
`awdl-queues-registration.txt`. Inspection uses `tools/awdl/inspect-native.py`,
Mach-O fileset offsets, the existing symbol cache and Capstone. No Apple
framework code was executed by the inspection. Indirect call ownership and
return types cannot be established from symbol names alone.

## Confirmed static facts

- `IO80211VirtualInterface::allocBpfResources()` calls `getTxPacketPool()`
  at slot `0xd88`, casts the result to a native packet-buffer pool, retains it
  and allocates a BPF packet. The observed pool-allocation error is consistent
  with the local class not overriding that accessor or providing a pool.
- `IOSkywalkPacketBufferPool::withName` allocates a native object of `0xc0`
  bytes. Use a native factory, not `new` through the old-sized declaration.
  Its initializer accepts pool kinds below 3 and nonnull options, then waits
  for resource `IOBSD` through `IOService::waitForService` with a null timeout.
  A future path must avoid invoking this dependency wait while holding the
  controller workloop gate without checking the resource first.
- `PoolOptions` fields read at offsets 0, 4, 8, 0xc, 0x10 and 0x14 match the
  old header. This does not establish the correct pool kind/flags for AWDL.
- `IOSkywalkPacket` inherits from `IOCommand` (not `IOService` as the old
  network-packet header says). Packet length/address getters are const.
  `setDataLength` can return `0xe00002c7`; old boolean/void declarations must
  be audited against instructions before use.
- The queue-array `registerEthernetInterface` copies registration information
  and calls `registerNetworkInterface`, which constructs a queue set and
  logical link. Its return value is `IOReturn` (zero means success), despite
  the current header declaring bool. Native registration owns its typed
  buffers; private registration-pointer copies must not be restored.
- `deferBSDAttach(true)` sets `IODeferBSDAttach` on the provider. False removes
  that property and calls `registerService(0)`. It also returns an IOReturn
  internally despite the current void declaration. Deferring must be done
  before superclass startup can publish the incomplete provider; releasing
  deferral must wait until the whole transport is registered.
- The simplest TX submission factory delegates with a null capacity callback
  and final queue ID `-1`; initialization requires capacity at least 8 and a
  nonnull submission callback. RX completion initialization requires capacity
  at least 2. These checks alone do not establish queue activation semantics.

## Verified factory symbols

```text
__ZN25IOSkywalkPacketBufferPool8withNameEPKcP8OSObjectjPKNS_11PoolOptionsE
__ZN26IOSkywalkTxSubmissionQueue8withPoolEP25IOSkywalkPacketBufferPooljjP8OSObjectPFjS3_PS_PKP15IOSkywalkPacketjPvES9_j
__ZN26IOSkywalkRxCompletionQueue8withPoolEP25IOSkywalkPacketBufferPooljjP8OSObjectPFjS3_PS_PP15IOSkywalkPacketjPvES8_j
__ZN26IOSkywalkTxCompletionQueue8withPoolEP25IOSkywalkPacketBufferPooljjP8OSObjectPFjS3_PS_PP15IOSkywalkPacketjPvES8_j
__ZN26IOSkywalkEthernetInterface25registerEthernetInterfaceEPKNS_16RegistrationInfoEPP20IOSkywalkPacketQueuejP25IOSkywalkPacketBufferPoolS7_j
__ZN26IOSkywalkEthernetInterface27deregisterEthernetInterfaceEj
```

## v4 implementation and verification

The v4 backend uses two factory-owned native pools (256 single-buffer packets,
2048-byte buffers) and native TX submission/TX completion/RX completion queues.
Queues use the controller/HAL workloop. The factory is called only after a
nonblocking IOBSD resource lookup; the protocol and controller never schedule
an automatic creation timer.

BSD attachment is deferred before superclass startup, then enabled after native
registration succeeds. The registration format is 1, size 0x130. The Tahoe
initializer calls Ethernet base getters directly rather than our AWDL overrides;
v4 explicitly sets the public payload's prefix pointer at 0x30 to "awdl" and
unit at 0x38 to zero. It does not write native private registration pointers.

TX callbacks return consumed packet count and defer completion until after
native submission increments outstanding count. Completion batches are limited
to 64 (the native API rejects count >= 128); failed enqueue deallocates through
the pool, completing preparation and notifying the source queue. Disabling
sync drains completions both before and after firmware waits, because waits
release the workloop gate and permit new drop completions. RX allocation uses
nosleep, prepares the packet before accessing buffers, and transfers ownership
on successful native RX enqueue.

Production-function host tests use ASan/UBSan and inject every factory failure,
queue-add failure, superclass-start failure, registration failure, repeated
create/stop, deferred TX completion, full completion buffers, disabled TX,
completion enqueue errors, and RX preparation/transfer errors. A firmware-wait
injection exercises submission immediately before sync timer cancellation.
The AWDL vtable matches all 569 native slots; packet/pool/queue declarations
match 244 compiler-emitted slots. These are static and mocked checks; they do
not prove kernel lifecycle or RF interoperability.

Focused static instruction evidence is saved in build/awdl-v4-*.txt and copied
into the v4 diagnostic artifact. All candidate imports are present in the disk
Boot KC. kextlibs cannot find library kexts on this sealed system; its "No
libraries found" result is not used as a loader validation.

## v4 runtime identity failure and v5 fix

Saved runtime logs show airportd reporting “awdl0 is not an AirPort interface”
and cached AWDL lookups failing. Public BSD ioctl identified awdl0 as wired
(type 2, Ethernet media 0x20). Registry IOMACAddress and native peer-manager
initialization were all zero while the custom BSD address was nonzero.
BLE/iPhone discovery was present; sharingd resolution over AWDL timed out.
These observations explain why native interface creation alone was insufficient.

Tahoe initializer directly calls Ethernet base getters; v5 fills public registration
subfamily 3 at offset 0x0c and IEEE80211 media 0x80 at 0x28, alongside v4's
prefix/unit. Native virtual configureIfnet already applies IFEF_AWDL for role 6;
v5 does not duplicate this configuration or write private native fields.
Evidence: build/awdl-v5-bsd-client.txt, awdl-v5-layer-address.txt,
awdl-v4-identity.txt and reference XNU kpi_interface.h/if_private.h.

Native getSelfMacAddr returns zero before the MAC agent exists; superclass
startup can construct the peer manager in this interval. V5 overrides it with
initialized protocol identity. After superclass start, the qualified native MAC
setter invokes our setMacAddress callback then updates its agent. The callback
now updates protocol state and returns success, avoiding reentry into the setter.
A qualified native getter verifies the actual agent address before publication.
Registration is followed by publication of the verified IOMACAddress.
Evidence: build/awdl-v5-self-mac.txt, awdl-v5-mac-agent.txt,
awdl-v5-mac-update.txt, awdl-v5-native-get-mac.txt. Static instructions establish
call relationships; they do not prove which path caused v4's zero property.

V5 production extraction tests cover early identity, recursive-callback detection,
setter failure/address mismatch, BSD MAC consistency, invalid/busy/stopping
updates, and subfamily/media. Release build, 569 AWDL slots, 244 native queue
slots, 1118 imports and existing host protocol/HAL/command/log tests passed.

## V5 AirDrop failure and v6 candidate

Runtime evidence: build/awdl-v5-kernel-start.log,
awdl-v5-kernel-enable-all.log, awdl-v5-driver-live.log and
awdl-v5-airdrop-live.log. Airportd recognizes awdl0 as an AirPort interface.
Sharingd discovers the iPhone via BLE, then resolution using AWDL times out
with resolveFailure/missingEndpoint. No successful RF synchronization was seen.

Native SYNC_FRAME_TEMPLATE failed with 0xe00002c2. Static instructions in
build/awdl-v6-native-enable.txt and awdl-v6-native-tlvs.txt establish that
Tahoe supplies supplemental TLVs, without a vendor action header or sync TLV.
V6 validates bounded TLVs and appends them after the host scheduler's header
and sync TLV. The previous setter demanded a complete frame. Native service,
election and data-path TLVs are preserved. Election-tree agreement with the
host scheduler remains to be checked on real received frames.

Firmware accepted DEV_INFO (0x20001), then rejected BSS_INFO (0x20002) with
0xc00000bb. The IBSS context failed before the broadcast station command.
V6 uses AP|P2P (P2P GO transport), as Linux MT76 uses for a P2P device. It
retains host-generated AWDL frames; it does not implement GO beacons.
The broadcast station now uses BC|INFRA, which Linux MT76 also uses for IBSS;
the previous BC|IBSS combination is not a supported connection constant.
Unicast records use STA|P2P. Packet ordering, isolated infrastructure fields,
failure propagation and interrupted waits are checked by tests/awdl-hal/bss.py.
Firmware acceptance of these new contexts is not established by host tests.
Reference: pinned Linux v6.17, build/reference-mt76-v6/mt76_connac_mcu.c.

V6 returns success with secondary-payload capability zero, accepts zero peer
addresses for inactive traffic registration and reports dual-band capability
bit 29 on this 5 GHz capable HAL. The bit is verified by native instructions
in build/awdl-v6-card-capabilities.txt; it does not advertise simultaneous
dual-radio operation. GET SUPPORTED_CHANNELS on AWDL is rejected by native
infrastructure-only dispatch, so v6 does not invent an AWDL override for it.

## Remaining runtime work

Run the current UUID-checked Test-AWDL.command after booting its matching kext. Verify template acceptance,
MTKAWDLFirmwareStage=enabled and MTKAWDLSyncEnabled=Yes, then perform an actual
AirDrop file transfer. The script opens AirDrop and observes sync for 20 seconds
before collecting the firmware ring and native logs. It records registration
and sync separately; neither result proves a file transfer.

Kernel teardown under traffic, RF timing, native peer-cache synchronization,
Bluetooth coexistence, scan-control support and service-count callbacks remain
unverified or incomplete. V5 rollback is preserved when installing v6; v3
recovery remains intact. The unrelated 00:49 APFS panic is unresolved.
No force-unload, reboot or shutdown was attempted in this turn.

## V7 boot panic and V8 repair

Panic 2026-10-21 13:19:09 identifies v7 UUID 2232713D-6D6B-3F87-9EB8-0BB832BAA497.
Stack: wifip2pd VIRTUAL_IF_CREATE -> createAwdlInterface -> failed init cleanup
-> IO80211SkywalkInterface::free+0x11, dereference NULL ivars+0xb8. Exact
failure return address maps to controller cleanup of initWithController failure.
Early creation can fail before any native init when HAL has no social channel.
V8 rejects offline/no-channel requests before allocation, establishes Skywalk
base separately, and uses lower NULL-safe cleanup for a failed base allocation.
Receiver cleanup is conditional on ownership. Actual init/free code is tested
with failures at no-channel, base-init, virtual-init, timer and timer-add stages.
Static native evidence and the original panic are retained in v8 diagnostics.
V8 boot/registration/sync were observed on 2026-10-21; kernel teardown and AirDrop transfer remain outstanding. See the current runtime findings above.


## V9 MI and peer-discovery candidate

V8 runtime confirmed unsupported AF mode3 and OOB MI programming, zero peers
and sharingd endpoint-resolution failure. V9 copies the borrowed MI TLVs at
Tahoe offset+48 synchronously, supports the observed broadcast/all-slot bitmap,
and emits a MIF after the microsecond start delay only when HAL has a real ROC
grant. It emits at most once per EAW; arbitrary bitmap mapping is not implemented.
Native `setMiBitmap` establishes that ioctl+16 is a bitmap, not a millisecond
period. AF0 allows PSFs, AF3 suppresses them; MIF is independently scheduled.
Wire subtype0 is PSF and subtype3 is MIF. Template election is reconciled with
the host scheduler clock; stale native sync-tree paths are omitted.

Native RX is no longer gated on the narrower host sync/election parser.
Envelope/RSSI/length guards remain, native performs its own semantic validation,
and bounded accepted/rejected/native/no-buffer diagnostics expose the next
problem without treating pre-parser receive counts as discovered peers.

omdrop-owl `8213aee9f018ffd78a3fc71863a364fcddd938cd` contributes concrete
iPhone trailing-zero padding and metric-first election fixes. Its pinned OWL
`832d70f815c3d4a06a02117bf0fc5e868daa1ff0` tracks every peer's clock phase;
this host State already retains a per-peer epoch. Linux monitor/hostapd/noack
workarounds are not ported. The project's MT7921 shared-mode limitations do
not establish behavior of this macOS HAL. References and static native
instructions are retained in v9 diagnostics. Hopper AppleEvents was unavailable;
static instructions came from the existing Capstone KC inspector.

V9 builds and host tests pass; kernel boot, exact MI cadence, native peer discovery
and actual AirDrop file transfer are still unvalidated.
