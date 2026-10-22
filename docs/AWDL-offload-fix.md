# AWDL physical assists and Skywalk software offload

The running `B887DD9B-4053-3A8E-A7AD-DDEC7F1ADEAB` candidate reports
successful BSD preparation while `ifconfig awdl0` shows TSO4/TSO6,
PARTIAL_CSUM and ZEROINVERT_CSUM. Earlier reports incorrectly classified
these flags alone as unsupported physical offload. The installed Tahoe
kernel deliberately advertises them for Skywalk's software path.

## Evidence

The exact KC SHA256 is
`21d6da1c4c3e7b72dddf5144da8a4c4b48e294249a16018a5006b61bb2155ccc`;
IOSkywalkFamily UUID is `A6EDB8DB-175B-3A49-8919-5769FCDB6BED`.
Focused offline instructions are retained in
`build/awdl-offload-fix/native-control.txt` and `native-host.txt`.
The REA session was closed/target-free; these new findings use the local
KC/Capstone helper, not a new REA runtime observation.

At `0xffffff80009ea3a0` through `09ea3c2`, native-host activation saves
its driver's hwassist/supported/enabled fields. With a native host beneath
the flowswitch, it ORs BSD capabilities with `0x6000` for software partial
checksumming (`09ea42d..09ea44a`) and `0x60` for software TSO when TCP
aggregation is enabled (`09ea452..09ea474`). It chooses a software GSO
output function when the saved hardware TSO flags are zero
(`09ea196..09ea1cb`). The internal helper is included within next-exported-
symbol bounds; that bound does not mean all instructions belong to the
exported activation function.

Apple's matching source architecture is described in
[nx_netif_host.c](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/skywalk/nexus/netif/nx_netif_host.c):
`nx_netif_host_adjust_if_capabilities` explicitly advertises software
copy/checksum and TSO, and `nx_netif_host_catch_tx` installs
`netif_gso_dispatch` when appropriate. `nx_netif_mbuf_to_kpkt` requests
combined copying/checksumming for partial mbufs. In
[nx_netif_gso.c](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/skywalk/nexus/netif/nx_netif_gso.c),
the no-hardware path computes per-segment TCP checksums. Local source
snapshots are under `build/awdl-offload-fix/xnu-*`; upstream main is mutable.
Source and static instructions establish architecture, not correctness of
every packet emitted on this machine.

## Change

The AWDL getter continues to advertise zero physical assists. The matching
setter now keeps the inherited cache zero too, including native registration
and restore updates. Before attach, preparation clears hwassist and both
supported/enabled checksum/TSO/LRO capabilities while preserving unrelated
flags such as Skywalk. It reads the values back and reports an error if
unsupported assists remain despite successful setters.

`MTKAWDLDriverHardwareAssists` reports the actual inherited cache.
`MTKAWDLBSDPreparedOffload`, `PreparedCapabilities` and `PreparedEnabled`
record the verified driver preparation snapshot. `CurrentOffload`,
`CurrentCapabilities` and `CurrentEnabled` observe subsequent BSD state.
Diagnostics do not clear Skywalk's software flags after host activation.
No global TCP aggregation setting or other interface is modified.

The data checker now evaluates the verified driver snapshot. BSD software
flags alone do not produce an unsupported-hardware failure. Older builds
without readback evidence remain unverified. A passed offload configuration
does not mark data transfer passed: native/BSD TX/RX and AW sanity are still
evaluated separately.

## Verification and limits

Five relevant suites passed, including an offload regression, native
enable/disable and packet ownership, AW scheduling, MI/data RX/TX and sync
transitions. Tests inject supported/enabled errors and a setter returning
success without clearing bits; they also model later software activation
and ensure diagnostics preserve it. The previous live snapshot is classified
as unverified rather than a physical-offload failure. Release build and
569 + 244 static native ABI slots pass.

The new candidate has not been installed or loaded; its UUID/hash and test
logs are in `build/awdl-offload-fix/verification.json`. Check its driver
readback on the next normal boot. A remaining BSD TSO/partial checksum flag
can be expected in native Skywalk mode. Successful AirDrop and checksum
correctness over the radio still require traffic validation. This change
does not fix the separately reproduced AW reservation/clock problem.
