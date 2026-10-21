# BSD awdl0 data queue activation (2026-10-22)

The installed AW lifecycle candidate `AFD857F8-F7B0-3F90-B949-7DC46EBDF682`
has registered queues, sync enabled and native link state 2, but no datapath
enable diagnostic and zero BSD input/output packets and bytes. Three all-nodes
IPv6 pings replied only from this interface's own address; the counters stayed
zero. Those replies are local loopback, not evidence of radio traffic.

## Cause and change

`AirportMtkAwdlInterface` overrode `enableDatapath` and `disableDatapath` but
inherited the native `enable(unsigned)`/`disable(unsigned)` entry points. Tahoe's
`IO80211SkywalkInterface::enable` calls the network base enable, which calls
`setInterfaceEnable`; neither starts the packet queues. The BCM proximity
subclass explicitly calls the datapath virtual at slot `0xd98` after base enable
and slot `0xda0` before base disable. The MTK subclass omitted these calls, so
BSD could become active while all three queues remained disabled.

The MTK subclass now overrides both entry points, preserves the superclass
calls, starts the queues after successful enable, and stops submission/drains
completions before disable. Enable rejects incomplete registration, missing
command gate and shutdown. Startup publishes false datapath state and zero
native packet counters; BSD enable/disable statuses are also exposed.

## Native evidence

Pinned BootKernelExtensions.kc SHA256:
`21d6da1c4c3e7b72dddf5144da8a4c4b48e294249a16018a5006b61bb2155ccc`.

- BCM proximity enable: `0xffffff800172a198`, file offset `0x162a198`.
- BCM proximity disable: `0xffffff800172a2c2`.
- Wi-Fi base enable: `0xffffff80022f990c`.
- Network base enable: `0xffffff8002b0b41a`.
- `getDataVirtualAddress`: `0xffffff8002b06518` returns segment address plus
  buffer segment offset; it does not apply packet data offset. The existing
  TX copy applies that offset once and is retained.

REA `ev_3136c5c482bb189c375a62127177bb131f1cdc9d7e2dea688d72dfdeaeb575fe`
read all 298 bytes of the BCM enable wrapper, verified against the original KC.
REA function analysis
`ev_f8fb3330eac7b2d677bd9590e4b601401b8567e7e1f581d30657076a519a9793`
shows the base call followed by virtual slot `0xd98`. Wrapper provenance and
complete evidence are retained in `build/rea-awdl-data/`. Calls and data outside
the mapped page are unmapped; pseudocode is inferred, not original source.
Annotated KC disassembly is in `build/awdl-data-native.txt` and
`build/awdl-data-state-native.txt`. Static evidence does not establish execution.

## Verification and hardware check

The production lifecycle/packet harness now invokes enable/disable through a
base pointer instead of manually enabling datapath. It checks failed enable,
missing gate, shutdown, repeated enable, disable with pending TX, disabled RX,
re-enable and a nonzero TX data offset, with ASan/UBSan. The seven existing AWDL
suites pass. Release x86_64/__MAC_26_0 build and 569 virtual-slot checks pass.

Candidate UUID: `F79AE847-84BA-3E34-91B7-CE20A1707920`.
Package: `build/awdl-data-fix/AirportMtkWlan-AWDL-data-fix.zip`.
The candidate has not been loaded; real TX/RX remains unverified. After loading
the candidate and generating peer traffic, run:

```sh
python3 tools/awdl/check-data.py \
  --expected-uuid F79AE847-84BA-3E34-91B7-CE20A1707920 --probe --seconds 10 \
  --output build/awdl-data-fix/runtime-data.json
```

The checker requires new native and BSD TX/RX counters, so a local ping reply
cannot pass it. TX acceptance does not prove a firmware ACK, and the check does
not validate an AirDrop file transfer. AW scheduling sanity failures remain a
separate unresolved issue documented in `AWDL-aw-lifecycle-fix.md`.
