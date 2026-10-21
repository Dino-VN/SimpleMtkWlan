# AWDL_ADVERTISERS: tài liệu triển khai cho Claude

Ngày kiểm tra: 2026-10-21. Repository: `/Volumes/App/SimpleMtkWlan`.

## Mục tiêu

Implement `AirportMtkAwdlInterface::setAWDL_AWDL_ADVERTISERS(awdl_peer_advert_add*)` để driver áp dụng parent/master và timing mà IO80211Family yêu cầu. Kết quả cần là native và host scheduler cùng lựa chọn sync peer, clock, presence và sequence, với status phản ánh việc áp dụng thực tế.

Hiện setter ở [AirportMtkAwdlInterface.hpp](/Volumes/App/SimpleMtkWlan/AirportMtkWlan/AirportMtkAwdlInterface.hpp:95) vẫn trả `kIOReturnUnsupported`. Kiểu `awdl_peer_advert_add` mới có forward declaration trong [IO80211AWDLProtocol.h](/Volumes/App/SimpleMtkWlan/include/Airport/macOS26/IO80211AWDLProtocol.h:46). ioctl ID là **229**.

Đây là native control record 44 byte. Không dùng nguyên on-air sync TLV thay cho record này. Việc hết lỗi advertisers không tự chứng minh AW-start/end đúng hoặc AirDrop chuyển file thành công.

## 1. Bằng chứng ABI và giới hạn

Binary dùng để xác minh:

```text
KC: /System/Library/KernelCollections/BootKernelExtensions.kc
SHA256: 21d6da1c4c3e7b72dddf5144da8a4c4b48e294249a16018a5006b61bb2155ccc
IO80211Family UUID: 4184F404-9547-3499-A311-C1920829EA25
AppleBCMWLANCoreMac UUID: D09C7323-1C09-36E3-B8C1-B58E52F48537
```

Các địa chỉ là VA tĩnh của KC này, chưa cộng kernel slide. Nếu đổi binary/macOS phải xác minh lại.

| Hàm | VA | Kết quả quan sát |
|---|---|---|
| `IO80211AWDLPeerManager::programChipWithNewMaster` | `0xffffff80021ec4b6` | Tạo record advertisers 44 byte và gọi ioctl nội bộ 229 |
| External `setAWDL_AWDL_ADVERTISERS` wrapper | `0xffffff8002289eb1` | Kiểm tra length bằng `0x2c` và pointer không null |
| `IO80211AWDLPeerManager::setAwdlAdvertisers` | `0xffffff800221c19e` | Route ioctl 229 tới interface |
| `AppleBCMWLANProximityInterface::setAWDL_AWDL_ADVERTISERS` | `0xffffff800171c932` | Copy 44 byte vào Broadcom firmware command `awdl_advertisers` |

Broadcom command có prefix version u16=0, length u16=44, sau đó native record. **Prefix này thuộc transport Broadcom**, không nằm ở đầu payload vào MTK setter và không chứng minh MTK có firmware command tương ứng. Không thêm `APPLE80211_VERSION` vào đầu record native.

Đã xác nhận bằng symbol và Capstone disassembly offline. REA/Hopper bị chặn Automation/Apple Events; REA inspect-macho helper lỗi assertion. Không coi kết quả này là decompilation REA thành công.

## 2. Layout 44 byte đã khôi phục

Offset là tính từ pointer `awdl_peer_advert_add*`. Các số nguyên thông thường được producer ghi theo host endian x86_64; timestamp +20 được byte-swap trước khi ghi. Một số tên/ngữ nghĩa còn chưa đủ bằng chứng, đã ghi rõ trong bảng.

| Offset | Byte | Decode | Nguồn native / ý nghĩa |
|---|---:|---|---|
| +0 | 2 | LE u16 | AW counter; peer state +0x6a |
| +2 | 2 | LE u16 | Down counter; +0x2f6, có getter `getDownCounter` |
| +4 | 2 | LE u16 | Low16 sync contention; +0x2f0, có getter `getSyncContention`; producer log gọi `tx_delay`, đơn vị cần xác minh |
| +6 | 2 | LE u16 | AF period; +0x2fc, có getter `getAfPeriod`; không tự coi là ms |
| +8 | 2 | LE u16 | Peer +0x304, từ sync TLV +0x10 trong native parser; tên/ý nghĩa đầy đủ còn cần xác minh |
| +10 | 2 | LE u16 | Producer ghi constant 16 trong nhánh đã trace; kiểm tra peer +0x300 bằng 16; không suy rộng mọi mode |
| +12 | 2 | LE u16 | AW period; +0x2fa, có getter `getAwPeriod` |
| +14 | 1 | signed i8 | RSSI; producer lấy peer RSSI/fallback |
| +15 | 1 | u8 | Zero trong producer đã trace |
| +16 | 1 | u8 | Presence, low byte +0x2ec, có getter `getPresenceMode` |
| +17 | 1 | u8 | Zero trong producer đã trace |
| +18 | 1 | u8 | Low byte peer +0x23f; liên quan election distance, còn cần xác minh ý nghĩa chính xác |
| +19 | 1 | u8 | Zero trong producer đã trace |
| +20 | 4 | **BE u32** | FW AF receive timestamp; `bswap(peer +0x390)`, có getter `getFwAFReceiveTimeStamp` |
| +24 | 4 | LE u32 | Self metric của peer, từ +0x247 |
| +28 | 4 | LE u32 | Root metric, từ +0x243 |
| +32 | 6 | bytes | Top/root-master MAC, từ peer state +0x22f |
| +38 | 6 | bytes | Immediate parent/peer MAC, từ peer base +0x58 |

Offset/kích thước và thao tác ghi của producer đã có bằng chứng. Những tên như `raw8`, `raw10`, `raw18` bên dưới cố ý giữ trung lập cho đến khi trace đủ ngữ nghĩa.

### Declaration đề xuất

Đặt trong header ABI Tahoe thích hợp, hoặc dùng record nội bộ khác tên và `memcpy` từ pointer. Trước khi định nghĩa đúng tag `awdl_peer_advert_add`, tìm toàn repo để tránh duplicate definition. Không thay đổi vị trí virtual method/vtable.

```cpp
struct __attribute__((packed)) awdl_peer_advert_add {
    uint16_t awCounter;          // +0
    uint16_t downCounter;        // +2
    uint16_t syncContention;     // +4; units not yet established
    uint16_t afPeriod;           // +6
    uint16_t raw8;               // +8
    uint16_t raw10;              // +10; observed value 16
    uint16_t awPeriod;           // +12
    int8_t rssi;                 // +14
    uint8_t reserved15;          // +15
    uint8_t presence;            // +16
    uint8_t reserved17;          // +17
    uint8_t raw18;               // +18
    uint8_t reserved19;          // +19
    uint32_t fwAfRxTimeBE;       // +20
    uint32_t peerSelfMetric;     // +24
    uint32_t rootMetric;         // +28
    uint8_t rootMaster[6];       // +32
    uint8_t immediatePeer[6];    // +38
};

static_assert(sizeof(awdl_peer_advert_add) == 44);
static_assert(offsetof(awdl_peer_advert_add, awCounter) == 0);
static_assert(offsetof(awdl_peer_advert_add, downCounter) == 2);
static_assert(offsetof(awdl_peer_advert_add, syncContention) == 4);
static_assert(offsetof(awdl_peer_advert_add, afPeriod) == 6);
static_assert(offsetof(awdl_peer_advert_add, raw8) == 8);
static_assert(offsetof(awdl_peer_advert_add, raw10) == 10);
static_assert(offsetof(awdl_peer_advert_add, awPeriod) == 12);
static_assert(offsetof(awdl_peer_advert_add, rssi) == 14);
static_assert(offsetof(awdl_peer_advert_add, reserved15) == 15);
static_assert(offsetof(awdl_peer_advert_add, presence) == 16);
static_assert(offsetof(awdl_peer_advert_add, reserved17) == 17);
static_assert(offsetof(awdl_peer_advert_add, raw18) == 18);
static_assert(offsetof(awdl_peer_advert_add, reserved19) == 19);
static_assert(offsetof(awdl_peer_advert_add, fwAfRxTimeBE) == 20);
static_assert(offsetof(awdl_peer_advert_add, peerSelfMetric) == 24);
static_assert(offsetof(awdl_peer_advert_add, rootMetric) == 28);
static_assert(offsetof(awdl_peer_advert_add, rootMaster) == 32);
static_assert(offsetof(awdl_peer_advert_add, immediatePeer) == 38);
```

Nên tách raw ABI record khỏi `DecodedAdvertisers`: decode endian bằng helper đọc byte, giữ bản copy 44 byte cho diagnostics. Tránh dereference u32 có thể unaligned. Không byte-swap metrics một lần nữa trên x86; chỉ timestamp +20 đã chứng minh BE.

## 3. Những dữ liệu record không cung cấp

Record này không chứa đầy đủ:

- Channel sequence và encoding/opclass.
- Election master counter của TLV election.
- Toàn bộ sync TLV để chạy lại parser hiện tại.
- Interface/schedule generation.
- ROC grant hoặc bằng chứng RF đã đổi channel.

Vì vậy phải ghép với peer/RX frame thực tế và các native setters liên quan. Không tạo peer giả từ MAC trong payload, không lấy AW counter +0 làm election counter. `peerSelfMetric` +24 là metric của parent peer; không tự ghi đè metric thiết bị của mình (`state.metric`).

## 4. Nối vào source hiện tại

Các điểm cần đọc/sửa:

| File / hàm | Trách nhiệm |
|---|---|
| [AirportMtkAwdlInterface.hpp](/Volumes/App/SimpleMtkWlan/AirportMtkWlan/AirportMtkAwdlInterface.hpp:95) | Đổi inline unsupported thành declaration; thêm state advertisers đã request/applied và diagnostics |
| [AirportMtkAwdlInterface.cpp](/Volumes/App/SimpleMtkWlan/AirportMtkWlan/AirportMtkAwdlInterface.cpp:804) | Setter mới và phối hợp `setAWDL_SYNC_STATE`, `setAWDL_SYNC_PARAMS`, `setAWDL_ELECTION_PARAMS`, channel-sequence/presence setters |
| [AwdlProtocol.hpp](/Volumes/App/SimpleMtkWlan/include/AWDL/AwdlProtocol.hpp:189) | `setSyncRole`, `elect`, peer lookup, epoch/counter; bổ sung policy áp dụng parent native chọn |
| [MtkMwx.cpp](/Volumes/App/SimpleMtkWlan/SimpleMtkWlan/hal_mwx/MtkMwx.cpp:3761) | ROC generation/cancellation và grant snapshot; chỉ sửa nếu cần cho schedule transition |

Source đang có hai nguồn chọn master: `state.elect()` và native setters. `state.elect()` chạy mỗi service tick và có thể ghi lại `sync/master/epoch/baseCounter/sequence/presence` từ peer đã chọn. Nếu setter chỉ ghi một lần rồi return success, tick sau có thể mất kết quả.

`setAWDL_SYNC_STATE` hiện dùng `setSyncRole` để chọn forced parent. `setAWDL_ELECTION_PARAMS` hiện tìm candidate có root MAC phù hợp rồi chọn candidate đầu tiên. Advertisers có **immediatePeer +38**, nên có thể xác định parent cụ thể hơn; cần phối hợp các setters, không để election-params hoặc sync-params kế tiếp vô tình đổi parent khác.

### Luồng xử lý đề xuất

```text
copy 44 bytes
  -> decode / validate supported ABI values
  -> capture interface + request generation
  -> match immediatePeer + rootMaster với peer/RX frame
  -> resolve timestamp mapping và sync phase
  -> build candidate sync configuration
  -> validate native role / presence / channel sequence consistency
  -> retire old schedule/request/grant có kiểm soát
  -> commit configuration và applied generation
  -> rearm scheduler
  -> return actual status
```

1. Copy record ngay khi pointer còn hợp lệ. Setter không có tham số length: external wrapper đã kiểm tra length ở đường đó, nhưng không được giả định mọi internal caller đều đi qua wrapper. Decoder nhận buffer+length để test; setter dùng contract ABI 44 byte của caller native. Không retain pointer payload cho asynchronous task và không đọc thêm byte ngoài 44.
2. Decode MAC, AW counter/down, period/presence và BE timestamp. Validate trước khi thay state. Record invalid không làm mất sync cũ.
3. Tìm peer theo **immediatePeer**, kiểm tra peer còn sống và advertised root khớp **rootMaster**. Nếu root khác hoặc frame quá cũ, trả status/diagnostic rõ; không đồng bộ theo peer có root giống nhưng MAC khác.
4. Correlate record với RX snapshot tương ứng, tránh dùng “frame mới nhất” nếu native request được tạo từ frame trước. Lưu bounded history theo interface generation, peer MAC và RX timestamp/counter để tra cứu. Chỉ `seen` và một epoch trên mỗi peer hiện tại có thể chưa đủ.
5. Dùng sequence đã decode từ RX hoặc native sequence ioctl có thứ tự/generation rõ. Record advertisers tự nó không đủ chọn channel. Nếu hai nguồn mâu thuẫn, trace invocation order và native semantics, không âm thầm chọn một bên rồi báo success.
6. Chọn policy để parent native yêu cầu được duy trì qua `elect()` và những setters sau đó. Peer timeout/disable/reset phải gỡ selection theo lifecycle rõ ràng. Không sửa trực tiếp object private IO80211Family.
7. Commit master/clock/sequence/presence từ một candidate snapshot nhất quán. Cập nhật native-facing getter/diagnostics để root và immediate parent không bị đánh đồng. Xác minh semantics getter trước khi đổi.
8. Khi schedule thực sự đổi, tăng generation, xử lý AW lifecycle đang Open, hủy request/grant cũ và rearm timer. Record trùng không tăng generation hoặc abort ROC vô điều kiện; nhiều advertisers update nhỏ không được làm radio liên tục mất dwell.

Pseudocode này chỉ mô tả flow, không phải API đã tồn tại:

```cpp
IOReturn setAWDL_AWDL_ADVERTISERS(awdl_peer_advert_add *input) {
    // Check lifetime/state and copy native ABI bytes synchronously.
    // Decode to a value object; retain no caller-owned pointer.
    // Run applyAdvertisers on the established interface workloop/gate.
    // Prepare from a real correlated peer/RX snapshot.
    // Revalidate generations after any operation that releases the gate.
    // Commit atomically or report a concrete failure without fake success.
}
```

## 5. Timing: chỗ cần xác minh trước khi viết công thức

Timestamp +20 là `getFwAFReceiveTimeStamp` của native peer. Nó phải được giải mã BE và nối tới cùng clock domain với RX metadata và AW-start/end timestamps.

Source RX hiện tạo metadata 72 byte zero-init, điền MAC/channel/RSSI rồi giao cho native; cần trace reader để xác minh timestamp RX ở offset nào, đơn vị/endian nào, có flag báo hợp lệ không. Không chọn một offset trống tùy ý để điền `now`.

`state.receiveAction()` hiện học epoch từ host RX time và countdown. Setter advertisers tới sau RX có độ trễ; không lấy thời điểm vào setter làm thời điểm nhận AF. Cũng không tự gọi timestamp native là host monotonic microsecond nếu chưa có mapping.

Chỉ sau khi xác minh counter/down thuộc thời điểm nào, units và tx-delay có cần hiệu chỉnh không mới dùng phép dựng clock tương tự parser hiện tại. Trong **giả thiết đã xác minh** period/down là TU và AW counter chỉ AW chứa RX:

```text
EAW length TU = presence * awPeriod
elapsed in EAW TU = EAW length TU - downCounter
EAW epoch host = correlated AF receive host time - elapsed * 1024
EAW baseline counter = AW counter - floor(elapsed / awPeriod)
```

Đây là công thức tham khảo có điều kiện, chưa phải công thức advertisers đã chứng minh. Cần kiểm tra boundary/countdown rounding, giá trị zero, delay +4 và raw8/raw10. Không lấy `counter & ~3` nếu presence không cố định 4. Không gán `epoch=now` và `baseCounter=payload.counter` để ép sync.

U32 microsecond wrap khoảng 71.6 phút, u16 AW counter cũng wrap. Correlation phải dùng modular delta với giới hạn tuổi frame nhỏ, phân biệt wrap với reset/master change; zero timestamp có thể xuất hiện lúc wrap, không mặc định zero luôn invalid.

## 6. Validation, status và serialization

Phân biệt **record malformed**, **configuration chưa hỗ trợ** và **chưa có dữ liệu để áp dụng**:

| Trường hợp | Hướng xử lý đề xuất |
|---|---|
| Null input / MAC không hợp lệ theo mode đã xác minh / dữ liệu cấu trúc sai | `kIOReturnBadArgument`; giữ applied state trước đó |
| Period/presence/raw mode hợp lệ nhưng backend chưa hỗ trợ | `kIOReturnUnsupported`; log field/value cụ thể |
| Chưa có peer hoặc RX timestamp mapping, interface đang stopping/reset | `kIOReturnNotReady`; log dependency thiếu |
| MCU/transport operation cần thiết bị lỗi | Propagate lỗi thật; xử lý state/grant đã bị invalidate |
| Candidate đã áp dụng đúng, hoặc duplicate của applied config cùng generation | `kIOReturnSuccess` |

Các reserved byte zero chỉ là quan sát nhánh producer hiện tại, chưa chứng minh mọi mode bắt buộc zero. Trace thêm/capture trước khi biến tất cả raw/reserved values khác zero thành lỗi. Valid MAC/self-parent cases cũng cần xét mode native, không áp dụng quy tắc follower cho top-master mode.

Không bắt buộc enabled trước khi nhận cấu hình nếu native thực tế gửi advertisers trong warmup. Trace ordering. Nếu backend hỗ trợ staging khi disabled, phân biệt `requested/staged/applied` và định nghĩa rõ success nghĩa là gì; không báo “sync applied” khi mới copy record. Nếu lựa chọn trả NotReady để chờ dependency, kiểm tra native có retry không. Trong nhánh `programChipWithNewMaster` đã trace, lỗi advertisers vẫn có đường tiếp tục opmode; không giả định retry tự động.

Native notifications có thể gọi election rồi ioctl ngược driver. Setter phải chạy đúng gate/workloop và giữ lifetime qua thao tác firmware có thể `commandSleep`/release gate. Không chờ condition mà completion cũng phải lấy lock đang giữ. Không gọi native postMessage dưới `sc_awdl_lock`, không giữ state/peer pointer qua wait mà không snapshot/revalidate.

Nếu firmware wait thả gate: khi quay lại, kiểm tra stopping/enabled nếu liên quan, interface generation, request generation và candidate peer vẫn phù hợp. Request mới hơn phải có cơ chế supersede request cũ; request cũ không được commit đè.

## 7. Diagnostics cần thêm

Tên property sau là **đề xuất**, chưa tồn tại:

```text
MTKAWDLAdvertisersRequests
MTKAWDLAdvertisersStatus
MTKAWDLAdvertisersStage
MTKAWDLAdvertisersRequestGeneration
MTKAWDLAdvertisersAppliedGeneration
MTKAWDLAdvertisersPeer / Root
MTKAWDLAdvertisersAWCounter / DownCounter / Presence
MTKAWDLAdvertisersFWAFRxTimestamp
MTKAWDLAdvertisersMatchedRXAgeUS
MTKAWDLAdvertisersClockMappingValid
```

Log raw 44 byte và decoded fields có rate limit, cùng build UUID/boot ID/interface generation, native sync role, root/parent trước-sau, matched RX timestamp, epoch/baseline/sequence identity và reason khi reject. Phân biệt stages `received`, `decoded`, `peer-matched`, `clock-resolved`, `applied`, `duplicate`, `rejected`. Không dùng counters/request received làm bằng chứng applied.

## 8. Test trước và sau build

### Decoder fixture

Đây là **fixture nhân tạo để kiểm tra offsets/endian**, không phải payload capture từ Apple và không chứng minh các giá trị raw là cấu hình hợp lệ:

```text
64 00 20 00 02 00 6e 00 00 00 10 00 10 00 c4 00 04 00 01 00
12 34 56 78 04 03 02 01 d4 c3 b2 a1
02 11 22 33 44 55 02 aa bb cc dd ee
```

Expected decode:

```text
length=44; awCounter=100; downCounter=32; syncContention=2
afPeriod=110; raw8=0; raw10=16; awPeriod=16; RSSI=-60
presence=4; raw18=1; timestamp=0x12345678
peerSelfMetric=0x01020304; rootMetric=0xa1b2c3d4
root=02:11:22:33:44:55; immediatePeer=02:aa:bb:cc:dd:ee
```

Test length 43/45 ở pure decoder; signed RSSI; timestamp endian và wrap; metric/MAC không đảo; counter wrap; raw/reserved unsupported có reason. Thêm fixture từ **native runtime thật** khi đã capture để xác minh semantic, không chỉ test struct against itself.

### State/application tests

- Peer thật khớp root/parent, timestamp correlation đúng: applied config tồn tại sau nhiều `elect()` ticks.
- Root giống nhưng immediatePeer khác: không áp dụng nhầm parent.
- Peer missing/expired, timestamp không match hoặc clock mapping thiếu: status đúng, không tạo fake peer/epoch.
- Duplicate: idempotent, không abort ROC hoặc tăng schedule generation vô ích.
- Same parent nhưng phase/sequence thay đổi: xác định thay đổi lớn/nhỏ và xử lý lịch phù hợp.
- SYNC_STATE/ELECTION_PARAMS/SYNC_PARAMS/presence/sequence tới theo ordering thật: không vô tình xóa lựa chọn vừa áp dụng.
- Request bị supersede trong MCU wait, reset/disable/sleep/recreate: không late commit hoặc dùng peer pointer cũ.
- Native callback reentry: không deadlock, bounded memory/logging, không ảnh hưởng lifecycle `en0`.

### Runtime nghiệm thu

Pin UUID kext đã load; lấy log đúng boot và khoảng thử. Native advertisers call phải tới setter, decode đúng, match RX thật và có `applied` evidence. Getter/native AW-start master/counter/clock phải nhất quán với applied snapshot và scheduler. Request/grant mới thuộc schedule generation mới, vẫn có matched ROC grant thực.

AW-start/end phải được kiểm tra riêng; advertisers thành công không cho phép bỏ qua sanity failure. MI enqueue phải tách khỏi TX completion/on-air. Chỉ kết luận AirDrop hoạt động sau discovery và chuyển file thực; không dùng việc `awdl0` tồn tại hoặc SyncEnabled=Yes thay thế phép thử này.

## 9. Evidence để mở trực tiếp

- [Advertisers producer](/Volumes/App/SimpleMtkWlan/build/awdl-abi-payloads-20261021.txt): `programChipWithNewMaster`, stack payload `rbp-0x80`, writes từ `0xffffff80021ec650` tới `0xffffff80021ec72c`, ioctl tại `0xffffff80021ec87d`.
- [Wrappers và Broadcom setter](/Volumes/App/SimpleMtkWlan/build/awdl-abi-annotated-20261021.txt): external length/null check, route nội bộ, copy 44 byte và command prefix.
- [Peer getters/parser](/Volumes/App/SimpleMtkWlan/build/awdl-abi-peer-fields-20261021.txt): period, down-counter, contention, presence và FW AF receive timestamp sources.
- [Election field evidence](/Volumes/App/SimpleMtkWlan/build/awdl-abi-election-20261021.txt): root/self metrics, MAC và field liên quan distance.
- [KC helper](/Volumes/App/SimpleMtkWlan/build/awdl_native_evidence.py): map VA/file offset, annotate symbols/strings; next-symbol bounds có thể gồm padding/data.
- [Hướng dẫn AW lifecycle tổng thể](/Volumes/App/SimpleMtkWlan/docs/AWDL-Claude-implementation-brief-20261021.md): AW-start 36 byte, AW-end 40 byte, generation/grant/lifecycle và clock dependencies.

## Yêu cầu bàn giao implementation

Claude cần bàn giao: ABI definition + độc lập decoder tests; setter và persistent native-selected-parent policy; RX timestamp correlation/mapping có bằng chứng; schedule/grant invalidation xử lý reentry; diagnostics thể hiện requested/applied; test results và UUID/path của `AirportMtkWlan.kext` nếu build.

Field hoặc clock semantic chưa xác minh phải được ghi rõ và giữ status thật. Không hoàn tất task bằng cách đổi unsupported thành success, tắt native sanity logs, ép master/counter, hoặc gửi event/grant giả.
