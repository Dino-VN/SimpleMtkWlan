# AWDL data queue deadlines

This candidate includes the native AW clock/event fixes, reserved-grant
retention and ROC cancellation/admission recovery, then fixes premature AWDL
data expiration. It targets macOS Tahoe x86_64.

## Reproduced defect

The data queue used a fixed one-second lifetime both during idle/ROC waiting
and when draining a granted channel. ROC itself permits one second for the
firmware response after queue admission. A valid packet could therefore expire
before the first usable AW even when firmware responded within its allowance.

The production scheduler regression supplies a 980ms response and a channel
sequence with one active EAW per 1048.576ms cycle. It queues multicast and
unicast data from the start and observes a valid peer advertisement. With the
previous source, both packets expire and neither is submitted. With the new
source, both reach the HAL after 1,048,826us and neither expires. The test uses
live simulated reservation deadlines and the production peer/channel gates;
it does not create an AW or permit TX without a matching grant.

Baseline failure: `build/awdl-data-queue-fix/regression-data-before.log`.
The baseline source is saved beside it. Reproduce it with:

```sh
python3 tests/awdl/test-native-windows.py \
  build/awdl-data-queue-fix/baseline-interface.cpp
```

## Resulting queue policy

Each packet snapshots an absolute expiration when production Ethernet output
encodes and queues it. Its budget includes one maximum MCU queue-admission
wait (30 times 100ms), the one-second ROC response allowance, one complete
channel cycle, and an 8ms scheduler margin. The cycle uses the longest valid
current, configured or known destination sequence, with the default 16-slot,
presence-4 cycle as a floor.

The default lifetime is 5,056,576us. The longest supported sequence gives a
finite maximum of 20,785,216us. Retries, missing stations, ring pressure, queue
rotation and subsequent schedule changes preserve the original bytes, sequence,
enqueue time and deadline. A longer later schedule only changes the budget of
new packets. Expiration still runs without a grant and releases the bounded
64-packet queue. Unicast still needs a live matching peer schedule and an
installed firmware station; a longer queue lifetime creates neither.

Diagnostic version 13 adds `MTKAWDLDataTxOldestAgeUS` and
`MTKAWDLDataTxNextExpiryUS` at the existing one-second publication interval.
The latter is an absolute monotonic timestamp and is zero for an empty queue.
Existing expired/submitted/deferred and HAL blocker counters retain their
meanings.

## Verification and testing limits

All 13 existing test groups pass, including production Ethernet enqueue,
deadline snapshots and exact expiry, slow local/peer sequences, mixed expired
and live entries in a full queue, transient HAL failure ownership, station
fairness, native RX, complete aggregate validation and replay rejection.
Production HAL and scheduler harnesses execute with ASan/UBSan. The Tahoe
Release build passes; the 569 AWDL and 244 Skywalk static ABI slots match the
pinned native image.

Candidate UUID: `DD38CCA5-D659-3C3C-AAA5-91F25BED5D57`.
Executable SHA256:
`28ec872b3af1a096f57bf727c7c125bea7a0944ba35992d5239f14d6914fa2ac`.
Combined package:
`build/awdl-data-queue-fix/AirportMtkWlan-AWDL-combined-fix.zip`.

These results establish the reproduced host queue fix. They do not establish
hardware ROC reliability, firmware ACKs, sustained RF throughput or a completed
AirDrop file transfer. One bounded queue budget cannot guarantee success after
repeated firmware failures or when local and peer schedules never intersect.
The candidate has not been installed or loaded in this task; the user will
update and boot normally before measuring it.

After that update, with AirDrop open on both devices and actual peer traffic:

```sh
python3 tools/awdl/check-windows.py \
  --expected-uuid DD38CCA5-D659-3C3C-AAA5-91F25BED5D57 --seconds 30 \
  --output build/awdl-data-queue-fix/runtime-windows.json
python3 tools/awdl/check-data.py \
  --expected-uuid DD38CCA5-D659-3C3C-AAA5-91F25BED5D57 --seconds 30 \
  --output build/awdl-data-queue-fix/runtime-data.json
```

Native TX counts protocol queue acceptance. DataTxSubmitted counts HAL/DMA
submission, not a firmware ACK. RX and BSD deltas should be evaluated separately
from those TX stages. A local multicast ping reply cannot prove RF transfer.
