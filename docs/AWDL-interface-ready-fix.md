# AWDL interface creation before Wi-Fi association

The loaded `8b879c3` build rejected native role-6 creation requests with
`infrastructure-not-connected` while en0 was powered on and unassociated.
The boot ring records running firmware (`flags=0x8847`) and repeated rejected
requests while infrastructure remained in SCAN. After a Wi-Fi power cycle
and successful association, wifip2pd created awdl0 automatically. These
observations are in `build/awdl-holdover-fix/runtime-mtk-ring.log` and
`runtime-summary.json`; they identify the association gate as a registration
blocker, not the cause of the initial Wi-Fi handshake failure.

Both the manual command wrapper and shared native creation path previously
required `IEEE80211_S_RUN`. The wrapper now delegates readiness to the shared
path. Native role-6 requests can register awdl0 in INIT, SCAN, AUTH, ASSOC or
RUN once firmware is running, the infrastructure provider and BSD interface
exist, and at least one supported social channel is available.

The HAL readiness snapshot checks `IFF_RUNNING` and rejects reset, detach,
stop and MAC reconfiguration. Missing HAL/lock and unavailable native data
path also reject creation before allocation. Neither AP association nor an
already enabled secondary BSS is required. Early firmware failures use the
retryable `firmware-not-ready` diagnostic stage.

Creation continues on the existing native request caller, with the manual
command serialized by its gate. No timer or controller-start allocation was
introduced. Native wifip2pd already issues automatic role-6 requests on boot
and Wi-Fi availability; the driver now accepts those requests without
requiring an AP connection. Existing registration remains idempotent across
association loss and power transitions: duplicate native requests return
EEXIST with awdl0's name, and controller/manual requests reuse the interface.

Ten relevant suites and the Tahoe x86_64 Release build pass. Production
creation tests exercise both native request entry points, every association
state, firmware-not-ready retry, unchanged infrastructure state, wrong role,
version and MAC rejection, one BSD publication, duplicate requests and
balanced teardown. HAL tests execute the production readiness method with
power/reset/stop/detach/MAC-reconfiguration failures, missing context/lock,
and independent secondary-BSS/command-owner state. Existing allocation,
queue, native-start, packet ownership and protocol/scheduler tests pass.
Restoring either old association gate causes the new regression assertions
to fail. Static ABI checks pass for 569 AWDL and 244 Skywalk slots.

This candidate has not been installed or loaded. Verify after a normal
update/boot with Wi-Fi enabled and unassociated: awdl0 should register after
the native automatic request, and its provider should report `registered`.
Firmware readiness alone does not guarantee a native request has arrived.
Actual unassociated boot behavior still needs hardware confirmation.

Registration and AW synchronization are separate. The latest loaded-build
capture had a registered interface but no native sync-enable request, no AW
events and no completed AirDrop transfer. Active scanning still prevents
firmware ROC reservations under the existing arbitration policy. This patch
changes interface readiness only; it does not establish AW activity during
scan, repair the first-boot Wi-Fi handshake or prove AirDrop data transfer.
