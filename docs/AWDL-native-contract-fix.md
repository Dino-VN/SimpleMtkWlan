# Native AW clock acquisition and delayed radio planning

This candidate corrects native clock selection and plans reachable radio
windows after a long ROC response has been measured. It does not establish
continuous AW coverage or a completed AirDrop transfer on the card.

## Native evidence

The pinned Tahoe kernel collection has SHA256
`21d6da1c4c3e7b72dddf5144da8a4c4b48e294249a16018a5006b61bb2155ccc`.
REA inspected mapped copies preserving the original function bytes and virtual
addresses; their external calls and data are unmapped. Original assembly, rather
than inferred pseudocode types, establishes the payload offsets.

`programChipWithNewMaster` at `0xffffff80021ec4b6` can skip the advertiser ioctl
and send only `AWDL_SYNC_STATE`. At `0xffffff80021ec5c6`, its warmup branch writes
mode bit `0x20`, with a log explicitly permitting immediate-master synchronization
and AW sequence-number adoption. The Broadcom setter at `0xffffff800171e164`
forwards that bit to firmware. It does not generate an AW event.

Saved REA evidence IDs are
`ev_02a424138842b8f8a4d232c72ab7fe1d8f4ec01939000e43d272b1c97c97432d`
for master programming and
`ev_853522fda6fe63d8c95a0e5e90c3c277619b1c0436cc5f443c77a0be6d89c485`
for start sanity. Full inline records, pseudocode, original setter disassembly,
and an independent contract review are retained in
`build/awdl-native-contract-fix/`.

## Changes and regression evidence

| Trigger | Previous behavior | Candidate behavior |
| --- | --- | --- |
| RX from the same immediate peer changes its root before native selects it | Rejected clock data overwrites the committed identity; the later native selection can become a duplicate and never acquire | Preserve the committed identity until an explicit acquisition succeeds |
| Native sends warmup `0x20` without advertisers | No parent acquisition is armed | Authorize a real received clock from the requested immediate parent; wait if no valid RX exists |
| Duplicate warmup or a pending advertiser root fence | Mode handling can miss the native contract | Compare requested controls, preserve root bounds, and avoid repeated acquisition or reservation abort |
| A clock sample is rejected, then timer election runs again | Timer can report synchronization without another accepted observation | Retain the acquired clock as holdover until fresh accepted RX; do not report the peer live |
| Native explicitly requests local master while controls are held | Old remote selection can survive the transaction | Cancel remote selection at the AW end and preserve the physical counter and phase |
| Dense short AWs with measured 500–1000 ms ROC delay | Request the nearest AW, which expires before the response | Choose a reachable future nonzero edge using the measured lead and its 8 ms preparation margin |

Entering warmup or changing the immediate parent authorizes one acquisition.
This is a conservative implementation of the observed permission; exact
Broadcom firmware retry behavior is not established. Channel sequence programming
remains separate from clock acquisition. A PSF-period `SYNC_PARAMS` update does
not cancel native peer selection.

The original root-identity regression and the original sync-state handler fail
their respective tests. With the original radio planner and otherwise current
code, the dense alternating-channel model records **0 starts / 0 ends in 6 s**
under a 500 ms response. The candidate records **10 starts / 10 ends**, with
54–74 TU accepted end durations. This is a controlled model, not RF evidence.
The sparse 500 ms regression still receives its real channel-44 AW.

Tests also cover RX arriving after warmup, held clock adoption, duplicate mode
refresh, a root fence across warmup entry, local promotion during an open AW,
one-second lookahead crossing more than 16 short windows, early grant expiry,
all-idle schedules, and schedule invalidation during reservation.

## Remaining hardware limits

The loaded baseline UUID `B8F98367-4E19-3FDC-BE5B-4349B084603A` still failed the
latest 30-second observation: 2 starts / 2 ends, one skipped-AW sanity failure,
one missing-start error, and 39 warning records. Its selected clock was not
validated in that snapshot. This observation predates loading the candidate.

Measured ROC response reaches about 0.98 s, while a presence-4 EAW lasts 65.536 ms.
Future planning improves reachability but cannot cover every different-channel
EAW at that latency. Missing nonzero AWs remain actual missing events. Historical
lead currently only increases; capped 1100 ms dwell can expire before a distant
target if a subsequent response is much faster. Actual grant coverage continues
to decide whether an AW can start.

Clock acquisition and wire synchronization share the same real clock. Events
still require an observed matching firmware grant and the current AW edge;
future targets never produce early starts, invented grants, or continuity
waivers. Hardware clock transitions, sustained AW coverage, and completed
AirDrop transfer require measurement after the user updates and normal-boots.
