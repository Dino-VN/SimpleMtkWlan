# Experimental MT7921 AWDL on Tahoe

On 2026-10-22, candidate `C85968EF-BEB5-39DC-B18B-CB230B587434`
caused two confirmed kernel panics at `IOSkywalkPacketQueue.cpp:321`
(`default packetCompletion()`). Do not install the historical AWDL RX fix ZIP.
The fault was pool-allocated RX being prepared with the RX completion queue
as its source. Skywalk completes RX by calling that source's completion
callback; the completion queue inherits the panic implementation.

The replacement uses a null source for directly allocated RX, with regression
coverage that reproduces the old panic callback before verifying success and
error cleanup. Native cache/traffic registration now keeps data membership and
replay independent of the three-second synchronization advertisement lifetime.
Expired radio schedules still cannot authorize a unicast TX slot. ROC now
carries channel configuration directly without a synchronous RLM wait on each
switch. The scheduler requests ahead and retains a grant across adjacent
equal-channel EAWs; firmware grant receipt and expiry still govern RF access.
BSD preparation clears hardware offloads and the enabled
checksum/TSO capabilities that Tahoe leaves stale when offload is zero.
These changes require a new boot and actual AirDrop transfer verification;
passing host regressions and static ABI checks does not establish kernel or
radio stability. The recovery boot has no native AWDL object.

Bluetooth is currently on and sharingd observes BLE peers marked
`AirDropUsable`. BLE connection timeouts in an earlier boot and current
AirDrop pseudonym provisioning errors do not yet identify a Bluetooth driver
defect. Recheck authentication after AWDL data transport works.

AirDrop is not confirmed working. The implementation is a development
candidate, not a release with verified AirDrop, Handoff or Continuity support.
The nearby iPhone did not see this PC with the original driver. macOS refused
the authorized hot-unload attempt on
2026-10-19 with `kext is in use or retained (cannot unload)` (-603946984).
At that stage, the loaded UUID was `737F79DC-10F1-3758-9664-53115E8543C3`.
On the 2026-10-20 boot, the default-enabled candidate UUID
`403F81DD-2C69-3337-BDFD-299B5CD9A7B9` is loaded and `en0` exists; the user
confirmed infrastructure Wi-Fi worked. `MTKAWDLEnabled` is true, but no native
AWDL instance or `awdl0` is present. The captured boot log has no
`VIRTUAL_IF_CREATE` calls and 152 failed cached-AWDL-interface lookups.
The latest verified boot on 2026-10-21 uses panic-containment v3, UUID
`B03CAE80-C1AE-313F-9980-2FA65A935D30`. The user's 01:44 manual diagnostic
returned unsupported (`0xe00002c7`) promptly, with stage
`native-data-path-unavailable`; `en0` stayed active at `192.168.1.179`.
Live read-only checks after that test confirmed the same UUID and interface
state. No AWDL interface was published. This verifies rejection of the known
panic path on this boot, not a functioning AWDL backend.
The experimental subclass now uses `IO80211AWDLProtocol` again: the attempted
`IO80211P2PInterface` superclass introduced four required symbols absent from
this machine's disk Boot KC. Disabling AWDL at runtime cannot remove those
load-time dependencies.
No reboot, OpenCore edit, NVRAM edit or AirDrop preference change was performed
during the implementation/reload stage.

## Native backend v4 candidate

`artifacts/awdl-native-v4/AirportMtkWlan.kext` is the new Tahoe Release
candidate. It adds native Skywalk pools/queues and packet transport, defers BSD
matching until native registration, and sets AWDL BSD registration to awdl0.
AWDL remains enabled by default; automatic creation timers remain removed.
Host backend/ownership, protocol, HAL/wait, command and log tests pass. Native
AWDL and packet/queue ABI checks pass against the installed Tahoe kernel.
The current boot is still v3. Loading v4, creating awdl0, native teardown, and
AirDrop interoperability require runtime verification. Run the v4 artifact's
Test-AWDL.command after loading that exact build; it refuses a different UUID.

## Requirements and implemented paths

Native AirDrop needs more than normal Wi-Fi association. AWDL needs a separate
peer interface and MAC, vendor action-frame discovery, synchronized availability
windows, master election, channel reservations while infrastructure Wi-Fi is
active, raw peer IPv6 transport, and integration with Apple's peer manager.
BLE discovery and the OS's sharing/authentication services are separate
requirements. Handoff and the different Continuity features additionally have
their own account, Bluetooth and service requirements; an AWDL implementation
does not by itself establish that those features work.

The Tahoe-only experimental code targets a role-6 `IO80211AWDLProtocol`
interface whose native implementation would own the `awdl` BSD interface.
Creation is blocked in v3 until its Skywalk backend is complete.
The protocol code forwards native configuration and BSD commands,
reports enable/link state, consumes native management buffers, and routes
unencrypted AWDL IPv6 frames separately from infrastructure traffic.

The host protocol engine parses action frames, follows a received synchronization
clock, handles election/replay/peer expiry, and rewrites native action templates
to advertise its actual schedule. Supported sequence encodings are 0/1/3;
presence is limited to 1, 2, 4, 8, 16, 32 or 64 availability windows. Unknown
encodings, duplication, fragments, A-MSDU, HT control and incomplete IPv6 frames
are rejected.

The MT7921 transport uses a separate BSS/OMAC/WMM context, broadcast WCID18,
and up to three unicast WCIDs15..17. The unified remain-on-channel request
includes channel/band/width, validates regulatory availability, and permits
TX only on a matching unexpired grant. Lifecycle generations and operation/API
drains protect teardown across MCU waits; native waits release the command gate
so replies can be delivered. Receive-filter restoration preserves unrelated bits.

### Continuous native windows

The D957401C boot recorded 9715 ROC submissions but only 597 accepted grants
and five paired native windows. The scheduler previously waited for synchronous
BSS RLM programming at channel changes and aborted RF at every native EAW end.
It also discarded pending requests when the target EAW ended, earlier than the
firmware response timeout.

The replacement uses the self-contained unified ROC acquire TLV, a 25ms request
lead during idle time, and a dwell covering consecutive same-channel EAWs plus
the lead and a 4ms guard, capped at 1000ms. MT76 advertises up to 5000ms for the
same command; the smaller cap bounds infrastructure disruption. Actual firmware
grants may be shorter and must still be validated. Native EAW end no longer
unconditionally cancels a usable ROC. At a channel change or renewal, the prior
window may end up to 8ms early, reduced by its start lateness so total duration
remains within native +/-10TU tolerance. Each next start requires an observed
matching grant and enough remaining duration. No catch-up events are emitted.

REA/Hopper evidence `ev_95cc907161f49ec46f3f765bac02369f4ddd3b0a948063c72f7cdd59e92923cd`
for native `sanityCheckAWEnd` at `0xffffff80021e4f5e` confirms that a duration
difference of 11TU or more is rejected. Source KC SHA256 is
`21d6da1c4c3e7b72dddf5144da8a4c4b48e294249a16018a5006b61bb2155ccc`;
the mapped offline function SHA256 is
`7ffa03854ad6f54bf833b12fa3d84742ab1b14795053821418d60d86cd0e40d8`.
This is static evidence; the wrapper omits external callees and data.

Production scheduler regression tests require every non-idle EAW across counter
wrap, 3/8ms grant delays, alternating channels and bounded grant renewal, plus
20ms early grants from idle and delayed pending responses. They validate event
order, AW counters and actual start/end durations with 750/1250us timer jitter.
Under the 8ms grant-delay case the old scheduler emitted 13 starts instead of
the required 42; the replacement emits all 42 with 41 ends and one open window.
Kernel timing, the firmware's
granted interval and continuous windows on hardware remain unverified until the
new UUID boots and `tools/awdl/check-windows.py` observes active synchronization.

## Remaining gaps

- No over-the-air exchange with the iPhone, discovery, accepted transfer, or
  Handoff/Continuity session has been observed with the candidate.
- Timing uses host RX arrival time rather than verified hardware TSF. MCU and
  scheduler latency can miss availability windows; the native timer recalculates
  the channel after a reservation wait.
- Multicast rendezvous and the complete availability-window extension policy
  remain incomplete. Some configuration modes explicitly return unsupported.
- The host election engine implements a bounded subset of Apple's election
  behavior; automatic OS capability detection is unresolved.
- OOB discovery/action requests, secondary payloads, encryption, companion LLW,
  DFS/6GHz, and several optional native controls are unsupported.
- Firmware peer cleanup on BSS removal, arbitrary delayed 8-bit grant-token
  reuse, native callback lifecycle, and Bluetooth coexistence during AWDL have
  not been verified on hardware.

## Build and enablement

Build for x86_64 Tahoe:

```sh
xcodebuild -project SimpleMtkWlan.xcodeproj -target AirportMtkWlan -configuration Debug ARCHS=x86_64 CODE_SIGNING_ALLOWED=NO AMTK_IO80211_TARGET=__MAC_26_0 build
```

Native AWDL is enabled by default on Tahoe, with no boot argument required.
The boolean `MTKAWDLExperimental=false` in the NetworkController personality
disables it; `amtk_awdl=0` also disables it. `amtk_awdl=1` overrides that
property and enables experimental AWDL. The controller's `MTKAWDLEnabled`
property records the effective setting.
Creation requires an explicit role-6 `VIRTUAL_IF_CREATE` request; controller
start and infrastructure link-up never schedule AWDL creation. The fallback
timer has been removed following boot lag and missing-interface reports.
The diagnostic build also accepts `mtkctl awdl-create` after infrastructure
association reaches `RUN`. This executes on the user-client caller's thread
inside the controller command gate. It creates/registers the native interface;
it does not enable firmware sync or prove AirDrop works. The controller records
`MTKAWDLCreateSource`, `MTKAWDLCreateStage`, and `MTKAWDLCreateStatus`, and writes
`MTK AWDL` messages with `IOLog` before and after native initialization stages.
`MTKAWDLDiagnosticVersion>=1` identifies a build that supports this command.
Version 1 was tested on hardware: native initialization and attach succeeded,
then `initRegistrationInfo(&info, 6, sizeof(info))` returned false. `en0`
remained associated with its IP address after cleanup. Version 2 passes `1`
as the registration-format argument, matching the working infrastructure path
and the reference source; AWDL role remains `6`. Version 2 also records creation
stages in the `mtkctl log` ring and zero-extends IOReturn values for IORegistry.
Version 2 subsequently froze during the manual request. The saved 00:44 panic
is a null dereference in `IOSkywalkNetworkBSDClient::start()+0x31d`. The local
IOSkywalkFamily UUID matches the panic (`A6EDB8DB-175B-3A49-8919-5769FCDB6BED`);
the fault reads the absent logical-link set at the provider's `+0xc8`.
Copying `RegistrationInfo` into private pointers did not register queues,
packet pools, or a logical link. Native BCM performs `registerEthernetInterface`
with its own queues and pools after its superclass start; this driver had
omitted that step entirely. The superclass also publishes its service during
`start()`, so guarding only the final `registerService()` is too late.

Version 3 rejects controller creation before native allocation and overrides
native `start()` to reject direct IOService startup until the Skywalk data path
is implemented. It removes the manual registration-pointer copies and the
associated allocator workaround. `MTKAWDLEnabled` still records the user-selected
default setting, while `MTKAWDLNativeDataPathAvailable=false` records the missing
backend. Creation returns unsupported with `native-data-path-unavailable`,
rather than publishing an incomplete BSD provider. This is a panic containment
fix; AWDL and AirDrop remain unavailable. The v3 CLI refuses v1/v2 kernels
before issuing the creation external method.
The hardware diagnostic at 2026-10-21 01:44 confirms that rejection preserves
the existing `en0` configuration and returns without the v2 startup hang.
Its log is `artifacts/awdl-panic-fix-v3/diagnostics/manual-20261021-014422.log`.
The updated diagnostic reports a passing containment check only when it sees
the expected unsupported result and stage, a missing backend, and unchanged
active `en0` configuration. Passing this check does not mean AWDL works.
The CLI's log reader now captures the initial log head and stops at that
snapshot, so ongoing kernel logging cannot keep its read loop running forever.
The updated script and rebuilt CLI passed a live test at 02:02:50 in about
0.7 seconds, with exit status 0 and unchanged `en0` configuration; see
`artifacts/awdl-panic-fix-v3/diagnostics/manual-20261021-020250.log`.
This diagnostic update does not change the v3 kext executable or UUID.
At 02:09 on the same boot, 80 live creation requests (64 serial and 16 across
four concurrent clients) all returned unsupported. The longest request took
22 ms; a 72,379-byte log snapshot took 14 ms. `en0` configuration remained
unchanged and `awdl0` was absent. The report is
`artifacts/awdl-panic-fix-v3/diagnostics/stress-20261021-020938.json`.
Protocol, HAL builders, MCU-wait routing, creation/start rejection, bounded-log
and static 569-slot ABI checks passed again. This stress exercises rejection
and command dispatch, not native queue startup or over-the-air transport.

The separate 00:49 report is an APFS mount-root panic approximately two seconds
into boot, with no AWDL stack. Its cause has not been established by this fix.
Native disassembly and the panic report are preserved under
`artifacts/awdl-panic-fix-v3/diagnostics/`; REA's Hopper route was blocked by
macOS Apple Events permission, so the exact fault instructions were checked
with `nm`, Mach-O fileset offsets, and Capstone without executing native code.
Further native inspection confirms that the pool initializer waits without a
timeout for the `IOBSD` resource, and `deferBSDAttach` sets the
`IODeferBSDAttach` property (removing it republishes the provider). The old
pool/packet headers also differ in return types and inheritance from Tahoe.
Queue completion ownership, callback teardown, and RX/TX integration remain
unimplemented. v4 replaces the permanent rejection with native queue/pool registration and
BSD deferral. The running v3 remains the rollback baseline.

The checked-in reference clone of `kgp-macPro/AirportItlwm-Tahoe` at
`6d14093de576c0d278f9bdc9f82b100393143fd3` uses `setVIRTUAL_IF_CREATE` in
`AirportSTAIOCTL.cpp` to initialize/attach/register an `IO80211P2PInterface`.
Its Skywalk `setVIRTUAL_IF_CREATE` returns unsupported. This confirms that
framework/request routing matters; its legacy P2P lifecycle and opaque
capability bytes do not establish compatibility with this machine's native
Tahoe Skywalk AWDL protocol.
Normal unsigned-kext approval requirements still apply. Earlier test bundles
may have an opt-in property in their plist; check it before reuse.
For infrastructure recovery, add `GCC_PREPROCESSOR_DEFINITIONS='$(inherited)
AMTK_DISABLE_NATIVE_AWDL=1'` to the Tahoe build command. This omits the native
AWDL class and its private P2P imports from the binary; `amtk_awdl=1` cannot
enable AWDL in that build.
Do not load AirportMtkWlan and SimpleMtkWlan together.

## Validation performed

- AirportMtkWlan Tahoe, AirportMtkWlan Sequoia and SimpleMtkWlan builds succeed.
- ASan/UBSan protocol tests pass: channel timing/rollover, roles, expiry/replay,
  supported template encodings, every IPv6 size54..1514, truncations and100,000
  malformed input mutations.
- Extracted real HAL builders pass golden RLM/ROC/WTBL packet, regulatory,
  grant expiry, aliased peer deletion, peer capacity, firmware failure,
  lifecycle cancellation/drain, token quarantine and masked-filter tests.
- Extracted sleep/wakeup tests pass for ordinary and command-gate callers.
- Existing lifecycle, scan, TX completion/unwind/output, RX handoff and
  association suites pass. Stale mocks were updated to the current production
  APIs while retaining behavioral assertions.
- The compiled AWDL object's569 virtual slots through0x11c0 match the current
  native BCM signatures and layout. The checker pins this machine's
  IO80211Family UUID4184F404-9547-3499-A311-C1920829EA25 and BCM UUID
  D09C7323-1C09-36E3-B8C1-B58E52F48537. This is static verification only.

The reverse-engineer-anything skill guided evidence reuse and independent
reviews. Native evidence came from the local BootKernelExtensions.kc using
nm/Mach-O parsing and Capstone, not an executed REA analysis session. REA6.7.0
doctor confirmed aligned registration, but no REA tools were connected. OWL
and Linux mt76 were protocol/firmware references; runtime compatibility remains
unverified.

## Delivered artifacts and reload result

`artifacts/awdl-2026-10-19/candidate/AirportMtkWlan.kext` is the unsigned
experimental Tahoe bundle, UUID71A7C7C1-E910-35F3-AECA-DDE645A3C915.
The adjacent zip contains the same kext with its test personality opt-in.
Executable SHA256:
`61926e7c2c934a675995e4404b39c202dad189264ef28d61ab759d850ea00765`.

The rollback bundle was rebuilt from original HEAD9eff544, UUID
BDFE66B1-6AE5-327A-AC51-05EA87D6D459. It is a source-baseline rollback, not a
byte-identical copy of the boot-loaded driver; its original disk bundle could
not be found, and a read-only EFI mount failed.

`tools/awdl/hot-reload.sh` stages root-owned bundles, attempts normal unload,
verifies the candidate UUID on load, and attempts the baseline rollback if
candidate load fails. It never restarts, edits boot configuration, or forces
service termination. The attempted run stopped at unload refusal. Its log is
saved alongside the artifacts as `hot-reload.log`.

For manual installation, preserve the existing boot-loaded kext and replace
only its bundle using the machine's existing installation method. The current
session cannot establish that installation location or approval/reboot outcome.
After the candidate boots, verify its UUID, `awdl0`, native sync enable and
last-peer properties, then test a small iPhone AirDrop transfer in both
directions. Capture `mtkctl debug` and `mtkctl log` plus AWDL interface state
before reporting success.
