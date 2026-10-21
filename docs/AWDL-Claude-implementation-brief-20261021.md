# Hướng dẫn cho Claude: sửa native AWDL sync trên Tahoe

Ngày kiểm tra: 2026-10-21. Mục tiêu trước mắt là làm native AW lifecycle, clock và scheduler nhất quán; sau đó kiểm tra discovery/transfer AirDrop. Tài liệu này là kết quả kiểm tra source và binary, không phải thông báo đã sửa/build/test thành công.

## 1. Những gì đã xác nhận và phạm vi kết luận

Log V14 người dùng gửi cho thấy RX, peer parsing, ROC grant và MI submission đã có hoạt động; lỗi payload rỗng đã hết. Nhưng `SyncEnabled=Yes`, `ROCGrants>0`, `MISubmitted>0` không chứng minh native timeline đúng hoặc MI đã phát trên sóng.

Có ba lỗi cụ thể cần xử lý cùng nhau:

1. AW-start record trong source hiện tại không khớp ABI native.
2. Source chỉ gửi AW-start, chưa có AW-end; native giữ trạng thái cửa sổ đang mở và báo start kế tiếp là “Back to Back start events”.
3. Scheduler gắn notification với thay đổi `grantedChannel`, thay vì định danh cửa sổ theo lịch native và grant thực tế. Chống trùng theo `counter/presence` mới thêm chưa giải quyết điều kiện ngoài này.

Setter `AWDL_AWDL_ADVERTISERS` còn trả unsupported: native đã chọn parent/master nhưng driver chưa áp dụng yêu cầu đó. Đây là một phần còn thiếu để đồng bộ native với host; chưa chứng minh nó là nguyên nhân duy nhất của toàn bộ lỗi AirDrop.

### Binary dùng làm bằng chứng

- KC: `/System/Library/KernelCollections/BootKernelExtensions.kc`
- SHA-256: `21d6da1c4c3e7b72dddf5144da8a4c4b48e294249a16018a5006b61bb2155ccc`
- IO80211Family UUID: `4184F404-9547-3499-A311-C1920829EA25`
- AppleBCMWLANCoreMac UUID: `D09C7323-1C09-36E3-B8C1-B58E52F48537`

Địa chỉ bên dưới là VA tĩnh của binary này, chưa cộng kernel slide. Nếu đổi macOS/KC phải xác minh lại. REA/Hopper bị chặn Automation/Apple Events; helper inspect-macho của REA lỗi assertion. Các kết luận ABI ở đây lấy từ symbol và Capstone disassembly offline, không phải decompilation thành công của REA.

### Source đã đọc

- `AirportMtkWlan/AirportMtkAwdlInterface.cpp`: `notifyAvailabilityWindowStart` khoảng dòng 506, `serviceInGate` khoảng 559, notification gate khoảng 620.
- `AirportMtkWlan/AirportMtkAwdlInterface.hpp`: advertisers setter khoảng dòng 95.
- `include/AWDL/AwdlProtocol.hpp`: clock/counter khoảng 176, election khoảng 220, `Reservation` khoảng 450.
- `SimpleMtkWlan/hal_mwx/MtkMwx.cpp`: matched ROC event khoảng 3761.

SHA-256 source lúc kiểm tra (Claude có thể đang sửa tiếp nên hãy đọc lại trước khi áp dụng):

```text
079dc10da531f1c432375a60f309b198e8d5a70be94acff8ba8fbbb6af0935f7  AirportMtkAwdlInterface.cpp
10f77e0909c4c3021689b2df7ffef8cf9d6284d5f1ff5d4e9c5a1522cd3f4ef0  AirportMtkAwdlInterface.hpp
67de7d55a2c9ede2b5eb496f699b35ea02cfea5af93782b4e1c21a258507caff  AwdlProtocol.hpp
21ba92b574900f072f3241a8c1b2e94f57ae3b4511d4fa5bd5cf185a9e120262  MtkMwx.cpp
```

## 2. Sửa AW-start ABI trước

Native Broadcom producer `handleAvailabilityWindowStart` tại `0xffffff8001718756` gửi **event 41, 36 byte**. Native dispatcher `IO80211AWDLPeerManager::reportDataPathEvents` tại `0xffffff80021dd8f4` nhận cùng record. Event 42 là extension record 8 byte; event 43 là AW-end 40 byte.

Record AW-start xác nhận từ producer và consumer:

| Offset | Byte | Nội dung |
|---|---:|---|
| +0 | 4 | AW counter, producer zero-extend từ u16 |
| +4 | 4 | Native role enum |
| +8 | 6 | Immediate sync-master MAC |
| +14 | 6 | Top/root-master MAC |
| +20 | 4 | FW AW-start timestamp tính bằng microsecond, encoded big-endian |
| +24 | 12 | `apple80211_channel`: version, channel number, flags |

Native `monitorTimeline` tại `0xffffff80021e11ca` đọc AW counter, so MAC tại +8/+14 và byte-swap timestamp +20. `logAWStart` tại `0xffffff80021e1b42` cũng byte-swap +20.

Struct nên có dạng sau; field names biểu diễn ý nghĩa đã tìm thấy, không phải original Apple header:

```cpp
struct __attribute__((packed)) NativeAwStart {
    uint32_t awCounter;
    uint32_t nativeRole;
    uint8_t syncMaster[6];
    uint8_t topMaster[6];
    uint32_t fwStartUsBE;
    apple80211_channel channel;
};
static_assert(sizeof(apple80211_channel) == 12);
static_assert(sizeof(NativeAwStart) == 36);
static_assert(offsetof(NativeAwStart, awCounter) == 0);
static_assert(offsetof(NativeAwStart, nativeRole) == 4);
static_assert(offsetof(NativeAwStart, syncMaster) == 8);
static_assert(offsetof(NativeAwStart, topMaster) == 14);
static_assert(offsetof(NativeAwStart, fwStartUsBE) == 20);
static_assert(offsetof(NativeAwStart, channel) == 24);
```

Source hiện tại mới đổi thành:

```cpp
uint32_t role;
uint8_t syncMaster[6]; uint16_t counter;
uint8_t topMaster[6]; uint16_t presence;
uint32_t awStartUsec; uint16_t sequence;
apple80211_channel channel;
```

Struct packed này là **38 byte**, với role +0, sync MAC +4, counter +10, top MAC +12, presence +18, time +20, sequence +24 và channel +26. Nó sai cả size lẫn offset. Native đọc role=0 như AW counter; đọc hỗn hợp MAC/counter như role và sync-master; đọc sequence lẫn phần đầu descriptor như channel. Việc native hết `no param` chỉ cho biết pointer không null, không xác nhận layout.

V14 cũ có size 36 nhưng cũng nhét counter/presence/phase vào các vùng MAC và `masterCounter` vào timestamp. Cần thay bằng đúng record, không tiếp tục thêm field để đủ số byte.

Native producer chuyển firmware role 0→2, 1→3, 2→1. Chưa xác nhận các enum này tương ứng trực tiếp với `state.syncRole` của MTK. Claude cần trace `AWDL_SYNC_STATE`/opmode và consumer để lập mapping rõ ràng; không hard-code role=0 hoặc sao chép firmware enum Broadcom sang MTK.

`awCounter` phải là counter trong snapshot của cửa sổ đã xác minh; không dùng chỉ số EAW đã chia presence làm payload counter. Sync/top MAC phải khớp parent/master mà native và driver đã thống nhất.

## 3. Bổ sung AW-end và lifecycle có cặp

Bằng chứng trực tiếp:

- `sanityCheckAWStart` tại `0xffffff80021e21de`, instruction `0xffffff80021e22e5` test bit 1 ở state +0x4280.
- Nếu bit đang set, branch log **“AWDL SANITY FAILURE: Back to Back start events”** tại `0xffffff80021e22fb`.
- Sau đó `0xffffff80021e231b` set trạng thái này thành 1.
- AW-end event 43 đi vào `0xffffff80021de439`, tới `0xffffff80021def0e` clear byte state +0x4280 về 0 trong nhánh hoạt động bình thường.

Vì vậy hai start có counter khác nhau vẫn báo Back to Back nếu thiếu end giữa chúng. Giảm start trùng không thay thế AW-end. Không sửa bộ nhớ private +0x4280; các offset này chỉ dùng giải thích consumer.

Broadcom `handleAvailabilityWindowEnd` tại `0xffffff80017184b6` gửi **43, 40 byte**. Bố cục producer đã xác nhận:

| Offset | Byte | Nguồn / mức xác minh |
|---|---:|---|
| +0 | 4 | Zero-extend firmware byte +0xc; ý nghĩa enum còn cần xác minh |
| +4 | 4 | Timestamp kết thúc microsecond, big-endian; `logAWEnd` byte-swap tại `0xffffff80021e4d51` |
| +8 | 1 | Firmware byte +0x11, còn cần xác minh nghĩa |
| +9 | 3 | Padding được zero-init |
| +12 | 4 | Firmware +0x12; consumer lưu làm bcn count trong log |
| +16 | 24 | Optional statistics block; producer để zero nếu không có record hỗ trợ |

Không đoán enum +0/+8, không khai version stats=1 khi không có thống kê thật. Cần trace thêm mandatory fields trước khi gửi. Không gửi null payload để chỉ clear cờ: native có riêng lỗi `AWDL_AVAILABILITY_WINDOW_EXTENSIONS_END no param`.

Thiết kế state machine cho mỗi **cửa sổ native hợp lệ**:

```text
Idle -> AwaitGrant -> Open -> Closed
                \-> Missed/Cancelled
```

- Start một lần khi cửa sổ đã có quyền radio thực, đúng channel và đúng lịch.
- End một lần khi phần hoạt động kết thúc; phải xác minh boundary kết thúc và chính sách khi bị preempt/abort/reset.
- Cửa sổ mới không được gửi start khi cửa sổ cũ còn Open mà chưa có close hợp lệ.
- Nếu radio bị thu hồi rồi cấp lại trong cùng cửa sổ, cần policy rõ ràng: không tự phát thêm cặp start/end để giả thành cửa sổ mới. Dùng extension chỉ khi ABI và ngữ nghĩa extension đã xác minh.
- Không bù start/end cho thời gian đã bỏ lỡ mà chưa từng có radio grant.
- Khi disable/reset/scan/sleep/recreate, đóng hoặc reset lifecycle theo API native thích hợp, tránh giữ notification state cũ.

AW cơ sở là 16 TU = 16.384 ms. Presence 4 tạo EAW 64 TU = 65.536 ms. **Không mặc định native cần một start mỗi 16 ms hoặc mỗi ROC grant.** Trace `sanityCheckAWStart`, presence và channel sequence native để xác định chính xác cửa sổ nào cần notification. Nhánh kiểm tra skipped có tính cả sequence slots và presence, không chỉ so hai counter liền nhau.

## 4. Tách định danh lịch khỏi channel và grant

Source hiện tại:

```cpp
uint16_t currentAw = state.counter(now) / state.presence;
if (grantedChannel != channel) {
    if (!awStartCounterValid || awStartCounter != currentAw)
        notifyAvailabilityWindowStart(channel, now);
}
```

Các vấn đề:

- Hai cửa sổ liên tiếp cùng channel và grant còn hiệu lực: điều kiện ngoài false, mất notification mới.
- Grant hết hoặc được cấp lại: thay đổi `grantedChannel` không xác định bắt đầu AW.
- Đổi master/epoch/sequence hoặc presence: cùng counter chia presence có thể đại diện lịch khác.
- Counter u16 wrap và ROC token u8 reuse: chỉ so counter/token không đủ chống event cũ.
- MCU wait có thể thả gate và tiêu tốn dwell; recheck channel thôi chưa phát hiện generation đổi nhưng channel vẫn giữ nguyên.

Cần snapshot nhất quán gồm:

```text
interface generation
schedule generation, immediate/root master, presence, sequence identity
AW counter + phase, native window/slot identity, scheduled start/end
ROC request generation + token + channel
matched grant receipt time + usable start/end + cancellation state
native start/end emitted state
```

`Reservation` hiện chỉ lưu token/channel/deadline và bool; grant timestamp không được giữ. Trong matched ROC event ở `MtkMwx.cpp`, lưu receipt timestamp và generation, rồi cung cấp immutable grant snapshot qua HAL. Nếu firmware không cung cấp RF-start timestamp, ghi rõ receipt time là quan sát phía host và xác minh độ trễ/mapping; không đổi tên nó thành firmware TSF.

Khi dùng token u8, generation nội bộ không tự làm firmware echo generation. Phải quản lý token reuse, cancel/drain và event cũ để không match nhầm sau wrap/reset.

Scheduler phải xét giao giữa cửa sổ lịch với grant thực. Revalidate snapshot/generation sau mọi thao tác MCU có thể release gate. Grant muộn ngoài cửa sổ phải bị loại hoặc xử lý như missed theo chính sách đã xác minh. Không tạo grant giả, không đánh dấu success khi MCU chỉ nhận command mà chưa có matched event.

Không gọi native `postMessage` trong `sc_awdl_lock` ở RX firmware callback. Chụp snapshot dưới lock, nhả lock, giao cho workloop/interface lifecycle thích hợp. Native notification có thể chạy election và quay lại driver ioctl: kiểm tra reentrancy, retain/lifetime, bounded queues và lock order để không tái gây deadlock/kernel panic.

Generation phải đổi khi lịch thực sự bị thay: master/sequence/presence/clock discontinuity hoặc interface reset. Không tăng vô điều kiện mỗi tick `state.elect`, nếu không mọi request đều stale.

## 5. Clock phải thống nhất giữa RX, advertisers và AW events

`fwStartUsBE` là timestamp, không phải election `masterCounter`, AW count hay elapsed kể từ một epoch peer có thể đổi.

Source đang lấy `(now-state.epoch)` rồi cast u32, chưa encode big-endian. Ngay cả sửa byte order vẫn chưa chứng minh đúng clock domain.

Cần xác minh:

1. Native metadata RX nhận AF timestamp ở offset nào và có endian/đơn vị nào. Source đang zero-init metadata 72 byte và mới điền MAC/channel/RSSI; xem native RX reader để biết thời gian còn thiếu.
2. `AWDL_ADVERTISERS` +20 chứa native peer's FW AF receive timestamp.
3. AW-start +20 và AW-end +4 phải dùng cùng timeline/mapping với RX timestamp.
4. Timestamp phải gắn với transition/grant thực đã ghi nhận, không lấy lúc timer tới muộn rồi coi là AW boundary chính xác.
5. U32 microsecond wrap khoảng 71.6 phút; dùng modular signed delta trong miền so sánh hợp lệ. Clock adoption/master switch phải phân biệt với wrap và báo resync rõ ràng.

Có thể dùng host monotonic time nếu thiết kế mapping nhất quán và native consumer chấp nhận; hiện chưa đủ bằng chứng để gọi host `mach_absolute_time` là firmware TSF. Sau khi làm timeline đúng mới đánh giá missed/skipped và latency.

## 6. Implement AWDL_ADVERTISERS theo native producer

Setter `.hpp:95` còn unsupported. `programChipWithNewMaster` tại `0xffffff80021ec4b6` tạo record **44 byte** và gọi ioctl **229**. External wrapper tại `0xffffff8002289eb1` yêu cầu payload 44 byte không null. Broadcom setter tại `0xffffff800171c932` copy đủ 44 byte vào firmware command. Native record không phải sync TLV trên sóng.

Các offsets đã khôi phục; tên còn có mức chắc chắn khác nhau:

| Offset | Byte | Nội dung / nguồn |
|---|---:|---|
| +0 | 2 | AW counter, peer state +0x6a |
| +2 | 2 | Down counter, +0x2f6 |
| +4 | 2 | Tx delay/contention, low16 +0x2f0 |
| +6 | 2 | AF period, +0x2fc |
| +8 | 2 | +0x304 từ sync TLV +0x10; nghĩa cụ thể cần xác minh |
| +10 | 2 | Constant 16 trong nhánh producer này; peer +0x300 phải bằng 16 |
| +12 | 2 | AW period, +0x2fa |
| +14 | 1 | RSSI signed |
| +15 | 1 | Zero |
| +16 | 1 | Presence, low byte +0x2ec |
| +17 | 1 | Zero |
| +18 | 1 | Low byte +0x23f; liên quan election distance, cần xác minh ngữ nghĩa |
| +19 | 1 | Zero |
| +20 | 4 | FW AF receive timestamp, encoded big-endian |
| +24 | 4 | Self metric, +0x247 |
| +28 | 4 | Root metric, +0x243 |
| +32 | 6 | Top/root-master MAC, +0x22f |
| +38 | 6 | Immediate parent/peer MAC, peer base +0x58 |

Ưu tiên xử lý setter như yêu cầu đồng bộ tới parent native đã chọn. Copy record trong thời gian pointer hợp lệ, validate period/presence/MAC, tìm peer/RX timestamp cùng clock domain; áp dụng master/epoch/sequence nhất quán với native sync state và channel-sequence ioctl. Tăng schedule generation khi thay đổi thật, invalidation request/grant cũ có kiểm soát.

Field chưa rõ giữ opaque để nghiên cứu thêm; không tự đặt tên rồi viết công thức điều khiển clock. Đừng giả định cần thêm `APPLE80211_VERSION` ở đầu: producer bắt đầu bằng AW counter u16. Đừng copy nguyên record sang lệnh MTK chưa có ABI tương ứng. Return status thật nếu không đủ peer/clock/firmware state để áp dụng.

Native có đường tiếp tục opmode dù advertisers lỗi; chưa thể kết luận mọi opmode failure do advertisers. Log hai status riêng.

## 7. Thứ tự triển khai và cách nghiệm thu

1. Pin source snapshot và kext UUID; sửa AW-start record/offsets/endian. Thêm asserts và test decode bằng fixture độc lập từ native layout.
2. Xác minh AW-end mandatory fields, triển khai paired lifecycle + snapshot/generation/grant correlation. Kiểm tra reentrancy của native event dispatch.
3. Khôi phục RX timestamp/mapping và advertisers để native/host cùng master, clock, presence, sequence.
4. Kiểm tra timeline nhiều cửa sổ rồi mới debug MI/on-air và discovery/data transfer.

Test logic có ý nghĩa: nhiều grant cùng cửa sổ; hai cửa sổ cùng channel; grant muộn/stale; MCU wait qua boundary; mất grant/preempt; channel zero; master/presence/sequence change; AW counter và ROC token wrap; sleep/wake/reset/recreate. Fixture phải giải mã payload được post, không chỉ kiểm tra comment hoặc tên field trong source.

Log theo mỗi transition, có rate limit:

```text
buildUUID bootID interfaceGen scheduleGen windowID awCounter
presence channel syncMAC rootMAC role
scheduledStart scheduledEnd observedGrantTime usableGrantEnd
requestGen token status eventResult
startPosted endPosted rawPayloadHex close/missReason
MIEnqueue MICompletion nativeRxTimestamp
```

Native start/end phải có cặp và khớp cửa sổ thực. Không còn Back to Back, malformed channel/master/time; skipped hợp lệ phải giải thích bằng scan/preempt/resync có timestamp, không che log hoặc bù event giả.

`MTKAWDLLastAWStartChannel=36` và `MTKAWDLHostChannel=0` ở hai snapshot khác nhau không tự chứng minh offset channel sai. Với V14 +24 đã đúng; source mới +26 sai là kết luận riêng từ struct. Kênh 36 có thể xuất hiện trong peer/native sequence; phải đối chiếu cùng generation/time/slot trước khi loại kênh này.

ROC submission phải có matched firmware grant. MI submission phải được tách khỏi TX completion và capture/ACK thực. Sau khi native timeline sạch, nếu iPhone vẫn không thấy Mac, kiểm tra MI trên sóng, native peer visibility và mDNS `_airdrop._tcp` qua awdl0. Tiếp theo kiểm tra TXWI rate, WCID/MAC/ACK, unicast gating trên MT7921. Chỉ báo AirDrop thành công sau discovery lặp lại và chuyển file thực hai chiều.

Build phải là `AirportMtkWlan.kext` với target Tahoe/AIRPORT_WCL, dùng Xcode DEVELOPER_DIR như môi trường đã thiết lập. Không suy ra loaded binary từ source vừa sửa: kiểm tra UUID bản load sau boot và lấy log đúng khoảng thử nghiệm; không trộn các dòng `no param` của bản trước với V14/V15.

## 8. Bằng chứng để Claude mở trực tiếp

- `build/awdl-abi-aw-lifecycle-20261021.txt`: annotated Broadcom start/end producer và native logAWEnd; có VA, file offsets, strings.
- `build/awdl-abi-sanity-20261021.txt`: Back to Back và Skipped checks.
- `build/awdl-abi-annotated-20261021.txt`: dispatcher, clear +0x4280, AW-end log/sanity call; advertisers wrappers.
- `build/awdl-abi-payloads-20261021.txt`: programChipWithNewMaster tạo advertisers record và monitorTimeline.
- `build/awdl-abi-peer-fields-20261021.txt`, `build/awdl-abi-election-20261021.txt`: peer sync/election field sources/getters.
- `build/awdl-abi-evidence-20261021.json`: binary identities và jump table 41/42/43.
- `build/awdl_native_evidence.py`: helper đọc KC, map VA/file offset và annotate symbols/strings. Next-symbol bounds có thể gồm padding; không decode arbitrary address giữa instruction.
- `build/awdl-v14-review-native-20261021.log`, `build/awdl-v14-review-boot-20261021.log`: phân biệt log trước và sau payload update.

Tài liệu `docs/AWDL-reference-review-20261021.md` là nghiên cứu GitHub trước khi disassembly: event 42 ở header reference là declaration cũ và snapshot source trong tài liệu đó đã cũ. Dùng bằng chứng binary bên trên cho ABI Tahoe này. OWL vẫn hữu ích cho on-air sync/election/rate/ACK, không cung cấp trực tiếp ABI Apple native.
