"""Execute actual HAL builders with mocked firmware waits, including teardown injection."""
from pathlib import Path
import re, subprocess, tempfile
root=Path(__file__).resolve().parents[2]
s=(root/'SimpleMtkWlan/hal_mwx/MtkMwx.cpp').read_text()
w=(root/'SimpleMtkWlan/hal_mwx/if_mwxreg.h').read_text()
def function(signature):
    a=s.index(signature); return s[a:s.index('\n}\n',a)+3]
helpers=s[s.index('class MwxAwdlCall {'):s.index('void MtkMwx::awdlSetReceiver')]
structs='\n'.join(re.search(r'struct '+name+r' \{.*?\} __packed;',w,re.S).group() for name in ['sta_req_hdr','sta_rec_basic','sta_rec_wtbl','wtbl_generic','wtbl_rx','wtbl_hdr_trans'])
code=r'''
#include <cassert>
#include <cstdint>
#include <cstring>
#include <cstdio>
#include <cerrno>
#include <vector>
#include <functional>
#include <AWDL/AwdlProtocol.hpp>
#define __packed __attribute__((packed))
#define htole16(x) (x)
#define htole32(x) (x)
#define IEEE80211_ADDR_LEN 6
#define IEEE80211_IS_CHAN_2GHZ(c) ((c)->ic_freq<3000)
#define IEEE80211_IS_CHAN_5GHZ(c) ((c)->ic_freq>=5000)
#define isset(a,i) ((a)[(i)/8] & (1U<<((i)%8)))
#define IFF_RUNNING 1
#define IEEE80211_S_SCAN 1
#define IEEE80211_F_BGSCAN 2
#define MWX_FLAG_SCANNING 16
#define MWX_FLAG_BGSCAN 32
#define IEEE80211_CHAN_PASSIVE 4
#define IEEE80211_CHAN_DFS 8
#define MSEC_TO_NSEC(n) ((n)*1000000ULL)
#define MT_WF_RFCR_DROP_OTHER_BSS 1
#define MT_WF_RFCR_DROP_A3_BSSID 2
#define MT_WF_RFCR_DROP_A2_BSSID 4
#define MT_WF_RFCR_DROP_OTHER_UC 8
#define MT_WF_RFCR_DROP_MCAST 16
#define MT_WF_RFCR_DROP_MCAST_FILTERED 32
#define MT_WF_RFCR(n) (n)
#define MT_RXD4_NORMAL_PAYLOAD_FORMAT 3
#define mtod(m,t) ((t)((m)->bytes+(m)->offset))
#define UNI_BSS_INFO_RLM 2
#define CMD_CBW_20MHZ 0
#define MCU_UNI_CMD_BSS_INFO_UPDATE 0x20002
#define MCU_UNI_CMD_STA_REC_UPDATE 0x20003
#define MWX_WTBL_STA 15
#define MWX_WTBL_RESERVED 19
#define STA_REC_BASIC 0
#define STA_REC_WTBL 13
#define WTBL_RESET_AND_SET 1
#define WTBL_GENERIC 0
#define WTBL_RX 1
#define WTBL_HDR_TRANS 6
#define STA_TYPE_ADHOC 4
#define STA_TYPE_STA 1
#define NETWORK_P2P (1U<<17)
#define STA_TYPE_BC 32
#define NETWORK_IBSS (1U<<18)
#define NETWORK_INFRA (1U<<16)
#define CONN_STATE_PORT_SECURE 2
#define CONN_STATE_DISCONNECT 0
#define MWX_DEV_LOG(...) ((void)0)
#define MBUF_DONTWAIT 0
using IOReturn=int;
enum { kIOReturnSuccess=0,kIOReturnNotReady=1,kIOReturnBadArgument=2,kIOReturnBusy=3,kIOReturnNoMemory=4,kIOReturnIOError=5,kIOReturnAborted=6,kIOReturnNoResources=7,kIOReturnNotFound=8 };
struct IOLock { bool locked=false; };
void IOLockLock(IOLock *p){assert(!p->locked);p->locked=true;}
void IOLockUnlock(IOLock *p){assert(p->locked);p->locked=false;}
struct ieee80211_channel {uint16_t ic_freq=0;uint32_t ic_flags=0;};
struct ieee80211_node {uint8_t ni_macaddr[6];ieee80211_channel*ni_chan;};
struct mwx_node {ieee80211_node ni;uint16_t wcid,flags;};
struct mwx_vif {mwx_node vif_mn;uint8_t idx,omac_idx,band_idx,wmm_idx,scan_seq_num;};
struct mwx_softc {
 struct {struct {int if_flags;}ic_if;int ic_state,ic_flags;bool ic_wcl_mac_reconfig;ieee80211_channel ic_channels[256];uint8_t ic_chan_active[32],ic_chan_avail[32];}sc_ic;
 mwx_vif sc_awdl_vif; mwx_node sc_awdl_peers[3];bool sc_awdl_peer_used[3],sc_awdl_station_pending[4];
 mtkawdl::Reservation sc_awdl_roc;uint8_t sc_awdl_address[6];
 uint64_t sc_awdl_roc_submitted=0,sc_awdl_roc_send_failed=0,sc_awdl_roc_scan_blocked=0,sc_awdl_roc_busy_blocked=0;
 uint64_t sc_awdl_roc_events=0,sc_awdl_roc_grants=0,sc_awdl_roc_rejected=0,
 sc_awdl_roc_grant_delay_us=0,sc_awdl_roc_max_grant_delay_us=0;
 uint64_t sc_awdl_roc_timeouts=0;
 uint64_t sc_awdl_roc_reasons[static_cast<unsigned>(mtkawdl::RocResult::Count)]{};
 mtkawdl::RocGrant sc_awdl_roc_last_event{};mtkawdl::RocResult sc_awdl_roc_last_result{};
 uint64_t sc_awdl_roc_last_event_us=0,sc_awdl_roc_last_response_us=0;
 uint64_t sc_awdl_tx_submitted=0,sc_awdl_tx_bad_frame=0,sc_awdl_tx_no_grant=0,sc_awdl_tx_busy=0,
 sc_awdl_tx_no_peer=0,sc_awdl_tx_backpressure=0,sc_awdl_tx_copy_failed=0,sc_awdl_tx_dma_failed=0;
 int sc_awdl_tx_errno=0;
 bool sc_awdl_enabled,sc_awdl_configured,sc_awdl_filter_active;uint32_t sc_awdl_filter;
 uint32_t sc_flags=0;int sc_scan_task=0;
 IOLock*sc_awdl_lock;uint32_t sc_awdl_epoch;bool sc_awdl_busy,sc_awdl_stopping;unsigned sc_awdl_calls;
 uint8_t sc_awdl_channel;uint64_t sc_awdl_token_used[256];
 bool sc_detaching,sc_resetting;struct {uint8_t num_streams,antenna_mask;}sc_capa;
};
static bool mwx_awdl_current(mwx_softc*,uint32_t);
static void mwx_awdl_quiesce(mwx_softc*,bool drainCalls=true);
struct mbuf { uint8_t bytes[256]{};size_t len=0,offset=0,packetLen=0; };
size_t mbuf_len(mbuf*m){return m->len;}
size_t mbuf_pkthdr_len(mbuf*m){return m->packetLen;}
void*mbuf_data(mbuf*m){return m->bytes+m->offset;}
int txLive=0,txCalls=0,txResult=0;bool txFull=false,copyFailure=false;
ieee80211_node*txNode=nullptr;std::vector<uint8_t> lastTx;
void mbuf_freem(mbuf*m){--txLive;delete m;}
void m_adj(mbuf*m,size_t n){assert(n<=m->len);m->offset+=n;m->len-=n;}
using mbuf_t=mbuf*;
int mbuf_dup(mbuf*m,int,mbuf_t*out){if(copyFailure)return ENOMEM;*out=new mbuf(*m);++txLive;return 0;}
bool mwx_tx_full(mwx_softc*){return txFull;}
int mwx_tx(mwx_softc*,mbuf*m,ieee80211_node*n){
 ++txCalls;txNode=n;lastTx.assign((uint8_t*)mbuf_data(m),(uint8_t*)mbuf_data(m)+m->len);
 mbuf_freem(m);return txResult;
}
std::vector<std::vector<uint8_t>> wire;
std::vector<int> commands;
std::function<void(mwx_softc*)> on_wait;
std::function<void()> on_sleep;
bool model=false,owned[19]{};uint32_t reply_status=0;
int calls=0,fail_at=0,fw_status=0;bool alloc_fail=false;uint64_t clock_us=100000;
uint64_t mwx_awdl_now(){return clock_us;}
int tsleep_nsec(void*,int,const char*,uint64_t){assert(on_sleep);on_sleep();return 0;}
int capture(mwx_softc*sc,int cmd,const void*p,size_t n){assert(!sc->sc_awdl_lock->locked);const auto*b=(const uint8_t*)p;wire.emplace_back(b,b+n);commands.push_back(cmd);++calls;
 reply_status=0;
 if(model&&cmd==MCU_UNI_CMD_STA_REC_UPDATE&&!fw_status&&fail_at!=calls) {
  unsigned wcid=b[1];assert(wcid>=15&&wcid<=18);
  const uint8_t *basic=b+8;unsigned state=basic[8];
  if(state) {if(owned[wcid])reply_status=0x10003;else owned[wcid]=true;}
  else owned[wcid]=false;
 }
 if(on_wait)on_wait(sc);return fail_at==calls?EIO:0;}
int mwx_send_assoc_status(mwx_softc*sc,int cmd,void*p,size_t n){int rv=capture(sc,cmd,p,n);return rv?rv:(fw_status?EIO:0);}
int mwx_mcu_send_msg(mwx_softc*sc,int cmd,void*p,size_t n,void*){return capture(sc,cmd,p,n);}
uint32_t reg=0;
uint32_t mwx_read(mwx_softc*,int){return reg;}
uint32_t mwx_rmw(mwx_softc*,int,uint32_t value,uint32_t mask){return reg=(reg&~mask)|value;}
void mwx_clear(mwx_softc*,int,uint32_t mask){reg&=~mask;}
void mwx_mac_wtbl_update(mwx_softc*,uint16_t){}
int mt7921_mcu_uni_add_dev(mwx_softc*sc,mwx_vif*,mwx_node*,int){uint8_t p[1]={};return capture(sc,0x20001,p,1);}
int mt7921_mcu_set_tx(mwx_softc*sc,mwx_vif*){uint8_t p[1]={};return capture(sc,0x11,p,1);}
mbuf*mwx_alloc_sta_req_tlv(size_t n){if(alloc_fail)return nullptr;auto*m=new mbuf;m->len=n;return m;}
void*mwx_append_tlv(mbuf*m,uint16_t*count,int tag,int len){assert(m->len+len<=sizeof(m->bytes));uint8_t*p=m->bytes+m->len;mtkawdl::put16(p,tag);mtkawdl::put16(p+2,len);m->len+=len;++*count;return p;}
mbuf*mwx_fill_sta_req_hdr(mbuf*,mwx_vif*,uint8_t,uint16_t,uint16_t);
int mwx_mcu_send_mbuf(mwx_softc*sc,int cmd,mbuf*m,int*seq){*seq=9;int rv=capture(sc,cmd,m->bytes,m->len);delete m;return rv;}
int mwx_mcu_wait_resp_int(mwx_softc*sc,int,int,uint32_t*status){assert(!sc->sc_awdl_lock->locked);if(on_wait)on_wait(sc);*status=fw_status?fw_status:reply_status;return 0;}
int scan_cancel_status=0,scan_cancels=0,scan_tasks=0,systq=0;
int mt7921_mcu_hw_scan_cancel(mwx_softc*){++scan_cancels;return scan_cancel_status;}
void task_add(int,int*){++scan_tasks;}
class MtkMwx {public:mwx_softc *com;MtkMwx *mwxController(){return this;}void setProperty(const char*,const char*){}void setProperty(const char*,uint64_t,unsigned){}bool awdlInterfaceReady();bool awdlChannelAllowed(uint8_t);void awdlAbort();IOReturn awdlPrepareChannel(uint8_t);IOReturn awdlEnable(const uint8_t*,bool);IOReturn awdlReserve(uint8_t,uint32_t);bool awdlCanTransmit(uint8_t);IOReturn awdlPeer(const uint8_t*,bool);IOReturn awdlTransmit(mbuf_t,uint8_t);IOReturn awdlTryTransmit(mbuf_t*,uint8_t);};
'''+structs+r'''
mbuf*mwx_fill_sta_req_hdr(mbuf*m,mwx_vif*v,uint8_t omac,uint16_t wcid,uint16_t count){auto*p=(sta_req_hdr*)m->bytes;p->bss_idx=v->idx;p->wlan_idx_lo=wcid;p->wlan_idx_hi=wcid>>8;p->tlv_num=count;p->is_tlv_append=1;p->muar_idx=omac;return m;}
'''+helpers+'\n'+function('static void mwx_awdl_roc_event(')+'\n'+function('static void mwx_awdl_strip_deaggregate(')+'\n'+function('bool MtkMwx::awdlInterfaceReady(')+'\n'+function('bool MtkMwx::awdlChannelAllowed(')+'\n'+function('static void mwx_awdl_abort(')+'\n'+function('void MtkMwx::awdlAbort(')+'\n'+function('static int mwx_awdl_remove_station(')+'\n'+function('static int mwx_awdl_remove_context(mwx_softc')+'\n'+function('IOReturn MtkMwx::awdlEnable(')+'\n'+function('IOReturn MtkMwx::awdlPrepareChannel(')+'\n'+function('IOReturn MtkMwx::awdlReserve(')+'\n'+function('bool MtkMwx::awdlCanTransmit(')+'\n'+function('IOReturn MtkMwx::awdlPeer(')+'\n'+function('IOReturn MtkMwx::awdlTransmit(')+'\n'+function('IOReturn MtkMwx::awdlTryTransmit(')+r'''
IOLock lock;
mwx_softc make(){mwx_softc sc{};sc.sc_awdl_lock=&lock;sc.sc_ic.ic_if.if_flags=1;sc.sc_capa={2,3};sc.sc_awdl_vif.idx=sc.sc_awdl_vif.omac_idx=1;sc.sc_awdl_vif.vif_mn.wcid=18;sc.sc_awdl_enabled=true;
 for(int ch:{6,44,149}){sc.sc_ic.ic_channels[ch].ic_freq=ch<=14?2407+ch*5:5000+ch*5;sc.sc_ic.ic_channels[ch].ic_flags=1;sc.sc_ic.ic_chan_active[ch/8]|=1U<<(ch%8);sc.sc_ic.ic_chan_avail[ch/8]|=1U<<(ch%8);}return sc;}
void reset(){wire.clear();commands.clear();calls=fail_at=fw_status=0;model=false;memset(owned,0,sizeof(owned));reply_status=0;alloc_fail=false;on_wait=nullptr;on_sleep=nullptr;lock.locked=false;clock_us=100000;scan_cancel_status=scan_cancels=scan_tasks=0;}
int main(){
 // Registration readiness is independent of AP state and secondary BSS
 // activation/command ownership, but rejects early boot/power/reset/detach.
 reset();auto readiness=make();MtkMwx readyHal{&readiness};
 for(int state=0;state<=4;++state){
  readiness.sc_ic.ic_state=state;readiness.sc_awdl_enabled=false;
  readiness.sc_awdl_busy=true;
  assert(readyHal.awdlInterfaceReady()&&!lock.locked&&commands.empty());
 }
 for(bool *blocked:{&readiness.sc_detaching,&readiness.sc_resetting,
                    &readiness.sc_awdl_stopping,&readiness.sc_ic.ic_wcl_mac_reconfig}){
  *blocked=true;assert(!readyHal.awdlInterfaceReady()&&!lock.locked);*blocked=false;
 }
 readiness.sc_ic.ic_if.if_flags=0;assert(!readyHal.awdlInterfaceReady());
 readiness.sc_ic.ic_if.if_flags=IFF_RUNNING;assert(readyHal.awdlInterfaceReady());
 readiness.sc_awdl_lock=nullptr;assert(!readyHal.awdlInterfaceReady());
 readyHal.com=nullptr;assert(!readyHal.awdlInterfaceReady());

 // Production HAL padding removal is RXD4- and AWDL-specific.
 mbuf rx{};uint8_t*hdr=rx.bytes;hdr[0]=0x88;hdr[24]=0x80;
 memcpy(hdr+10,"\x02\x01\x02\x03\x04\x06",6);memcpy(hdr+16,mtkawdl::bssid,6);
 rx.len=98;auto raw=rx;mwx_awdl_strip_deaggregate(&rx,0);assert(rx.offset==0);
 mwx_awdl_strip_deaggregate(&rx,3);assert(rx.offset==2&&rx.len==96);
 assert(!memcmp(mtod(&rx,uint8_t*),raw.bytes,26));
 rx=raw;rx.bytes[16]^=1;mwx_awdl_strip_deaggregate(&rx,3);assert(rx.offset==0);
 rx=raw;rx.len=50;mwx_awdl_strip_deaggregate(&rx,3);assert(rx.offset==0);

 // Actual RX grant handler: exact Linux struct offsets and bounded framing,
 // late responses, every rejection reason and unchanged state on rejection.
 reset();auto events=make();
 std::vector<uint8_t> event(24);mtkawdl::put16(event.data()+6,20);
 event[8]=1;event[9]=7;event[11]=44;event[17]=1;mtkawdl::put32(event.data()+20,300);
 auto reject=[&](const std::vector<uint8_t>&bytes,mtkawdl::RocResult reason,uint64_t at){
  auto before=events.sc_awdl_roc;auto count=events.sc_awdl_roc_rejected;
  mwx_awdl_roc_event(&events,bytes.data(),bytes.size(),at);
  assert(events.sc_awdl_roc_last_result==reason&&events.sc_awdl_roc_rejected==count+1);
  assert(!memcmp(&before,&events.sc_awdl_roc,sizeof(before)));
  assert(events.sc_awdl_roc_reasons[static_cast<unsigned>(reason)]);
 };
 events.sc_awdl_roc.request(7,44,clock_us);
 for(unsigned size=0;size<24;++size){auto truncated=event;truncated.resize(size);
  reject(truncated,size==4?mtkawdl::RocResult::NoGrant:mtkawdl::RocResult::Malformed,clock_us+1000);}
 for(unsigned len:{0,3,19,21,65535}){auto bad=event;mtkawdl::put16(bad.data()+6,len);
  reject(bad,mtkawdl::RocResult::Malformed,clock_us+1000);}
 auto bad=event;bad[4]=3;reject(bad,mtkawdl::RocResult::NoGrant,clock_us+1000);
 bad=event;bad[8]=0;reject(bad,mtkawdl::RocResult::WrongBss,clock_us+1000);
 bad=event;bad[10]=2;reject(bad,mtkawdl::RocResult::FirmwareStatus,clock_us+1000);
 bad=event;bad[17]=0;reject(bad,mtkawdl::RocResult::WrongType,clock_us+1000);
 bad=event;bad[9]=6;reject(bad,mtkawdl::RocResult::Token,clock_us+1000);
 bad=event;bad[11]=6;reject(bad,mtkawdl::RocResult::Channel,clock_us+1000);
 for(unsigned ms:{0,1101}){bad=event;mtkawdl::put32(bad.data()+20,ms);reject(bad,mtkawdl::RocResult::Duration,clock_us+1000);}
 events.sc_awdl_enabled=false;reject(event,mtkawdl::RocResult::Disabled,clock_us+1000);events.sc_awdl_enabled=true;
 for(bool*flag:{&events.sc_awdl_stopping,&events.sc_resetting,&events.sc_detaching}){
  *flag=true;reject(event,mtkawdl::RocResult::Disabled,clock_us+1000);*flag=false;}
 reject(event,mtkawdl::RocResult::Late,clock_us-1);
 reject(event,mtkawdl::RocResult::Late,clock_us+mtkawdl::rocResponseTimeoutUs);
 auto duplicate=event;duplicate.insert(duplicate.end(),event.begin()+4,event.end());
 reject(duplicate,mtkawdl::RocResult::Malformed,clock_us+1000);
 bad=event;bad.push_back(1);reject(bad,mtkawdl::RocResult::Malformed,clock_us+1000);
 // Unknown bounded TLV before the grant is allowed. Arrival 504ms after
 // submission matches the observed slow HAL scale and used to be rejected.
 std::vector<uint8_t> extended(event.begin(),event.begin()+4);
 extended.insert(extended.end(),{9,0,4,0});extended.insert(extended.end(),event.begin()+4,event.end());
 mwx_awdl_roc_event(&events,extended.data(),extended.size(),clock_us+504334);
 assert(events.sc_awdl_roc_last_result==mtkawdl::RocResult::Accepted&&events.sc_awdl_roc_grants==1);
 assert(events.sc_awdl_roc_grant_delay_us==504334&&events.sc_awdl_roc_max_grant_delay_us==504334);
 assert(events.sc_awdl_roc.deadline==clock_us+504334+300000);
 reject(event,mtkawdl::RocResult::NotPending,clock_us+504335);
 // Cancel/reissue never lets an old token become the new grant.
 events.sc_awdl_roc.cancel();events.sc_awdl_roc.request(8,44,clock_us+600000);
 reject(event,mtkawdl::RocResult::Token,clock_us+600001);
 uint64_t total=0;for(auto count:events.sc_awdl_roc_reasons)total+=count;
 assert(total==events.sc_awdl_roc_events&&total==events.sc_awdl_roc_grants+events.sc_awdl_roc_rejected);
 uint8_t addr[6]={2,1,2,3,4,5};
 reset();auto sc=make();MtkMwx hal{&sc};
 assert(hal.awdlPrepareChannel(6)==0&&commands.size()==1&&commands[0]==MCU_UNI_CMD_BSS_INFO_UPDATE&&!sc.sc_awdl_roc.pending);
 auto preparedCalls=commands.size();assert(hal.awdlPrepareChannel(6)==0&&commands.size()==preparedCalls);
 assert(hal.awdlPrepareChannel(0)==kIOReturnBadArgument);
 sc.sc_awdl_roc.request(7,6,clock_us);assert(hal.awdlPrepareChannel(44)==kIOReturnBusy&&commands.size()==preparedCalls);
 assert(sc.sc_awdl_roc.grant(7,6,70,clock_us));assert(hal.awdlPrepareChannel(44)==kIOReturnBusy);
 clock_us+=70001;assert(hal.awdlPrepareChannel(44)==0&&sc.sc_awdl_channel==44);
 reset();sc=make();fail_at=1;assert(hal.awdlPrepareChannel(6)==kIOReturnIOError&&!sc.sc_awdl_channel);
 reset();sc=make();on_wait=[](mwx_softc*s){++s->sc_awdl_epoch;s->sc_awdl_stopping=true;};assert(hal.awdlPrepareChannel(6)==kIOReturnAborted&&!sc.sc_awdl_channel);
 reset();sc=make();
 assert(!hal.awdlChannelAllowed(0)&&!hal.awdlChannelAllowed(166)&&hal.awdlChannelAllowed(6));
 sc.sc_ic.ic_chan_active[0]=0;assert(!hal.awdlChannelAllowed(6));sc=make();sc.sc_ic.ic_chan_avail[0]=0;assert(!hal.awdlChannelAllowed(6));sc=make();sc.sc_ic.ic_channels[6].ic_flags|=IEEE80211_CHAN_PASSIVE;assert(!hal.awdlChannelAllowed(6));sc=make();
 // RLM must configure the secondary BSS before the exact ROC acquire packet.
 for(int ch:{6,44,149}){
  reset();sc=make();assert(hal.awdlReserve(ch,300)==0);
  assert(commands.size()==2&&commands[0]==MCU_UNI_CMD_BSS_INFO_UPDATE&&commands[1]==0x00020027);
  const auto&rlm=wire[0];assert(rlm.size()==20&&rlm[0]==1&&rlm[8]==ch&&rlm[9]==ch&&rlm[17]==(ch<=14?0:1));
  assert(sc.sc_awdl_channel==ch);
  const auto&roc=wire[1];
  assert(roc.size()==28&&roc[8]==1&&roc[10]==ch&&roc[12]==(ch<=14?1:2));
  assert(roc[14]==ch&&roc[17]==ch&&roc[19]==1&&mtkawdl::le32(roc.data()+20)==300);
  assert(!hal.awdlCanTransmit(ch));
  assert(!sc.sc_awdl_roc.grant(sc.sc_awdl_roc.token+1,ch,300,clock_us));
  assert(sc.sc_awdl_roc.grant(sc.sc_awdl_roc.token,ch,300,clock_us));
  assert(hal.awdlCanTransmit(ch));clock_us+=300001;assert(!hal.awdlCanTransmit(ch));
 }
 // Initial RLM stays stable: temporary switches use the exact ROC channel
 // without a synchronous BSS wait at the next AW boundary.
 reset();sc=make();sc.sc_awdl_channel=6;
 assert(hal.awdlReserve(6,70)==0&&commands.size()==1&&commands[0]==0x20027);
 assert(sc.sc_awdl_roc.grant(sc.sc_awdl_roc.token,6,70,clock_us));
 commands.clear();wire.clear();assert(hal.awdlReserve(44,70)==0);
 assert(commands.size()==2&&commands[0]==0x20027&&wire[0].size()==16);
 assert(commands[1]==0x20027&&wire[1].size()==28&&wire[1][10]==44);
 assert(sc.sc_awdl_channel==6&&!hal.awdlCanTransmit(44));
 // A slow RLM response callback cannot run during subsequent ROC switches.
 // After the raw matching event, TX uses the granted channel, not base RLM.
 on_wait=[](mwx_softc*){if(commands.back()==MCU_UNI_CMD_BSS_INFO_UPDATE)clock_us+=504334;};
 uint64_t switchingAt=clock_us;
 assert(hal.awdlReserve(149,70)==0&&clock_us==switchingAt&&commands.back()==0x20027);
 std::vector<uint8_t> switched(24);mtkawdl::put16(switched.data()+6,20);
 switched[8]=1;switched[9]=sc.sc_awdl_roc.token;switched[11]=149;switched[17]=1;
 mtkawdl::put32(switched.data()+20,70);clock_us+=3000;
 mwx_awdl_roc_event(&sc,switched.data(),switched.size(),clock_us);
 assert(hal.awdlCanTransmit(149)&&!hal.awdlCanTransmit(6)&&sc.sc_awdl_channel==6);
 // Failed/stale RLM must not request ROC or publish a configured channel.
 reset();sc=make();fw_status=7;
 assert(hal.awdlReserve(44,70)==kIOReturnIOError&&commands.size()==1&&!sc.sc_awdl_channel&&!sc.sc_awdl_roc.pending);
 reset();sc=make();on_wait=[](mwx_softc*s){clock_us+=45000;++s->sc_awdl_epoch;s->sc_awdl_stopping=true;};
 assert(hal.awdlReserve(44,70)==kIOReturnAborted&&commands.size()==1&&!sc.sc_awdl_channel&&!sc.sc_awdl_roc.pending);
 // The request timeout starts after the synchronous RLM response.
 reset();sc=make();on_wait=[](mwx_softc*){if(commands.back()==MCU_UNI_CMD_BSS_INFO_UPDATE)clock_us+=45000;};
 assert(hal.awdlReserve(44,70)==0&&sc.sc_awdl_roc.requestedAt==145000&&sc.sc_awdl_roc.deadline==145000+mtkawdl::rocResponseTimeoutUs);
 // An unanswered request expires once. Deadline and pending grant stay
 // distinct from physical dwell; aborting an already cleared token is idle.
 clock_us=sc.sc_awdl_roc.deadline;hal.awdlAbort();assert(sc.sc_awdl_roc_timeouts==1&&!sc.sc_awdl_roc.pending);
 hal.awdlAbort();assert(sc.sc_awdl_roc_timeouts==1);
 reset();sc=make();assert(hal.awdlReserve(6,mtkawdl::maxRocMs)==0);
 assert(mtkawdl::le32(wire.back().data()+20)==1100);
 assert(!sc.sc_awdl_roc.grant(sc.sc_awdl_roc.token,6,1101,clock_us));
 assert(sc.sc_awdl_roc.grant(sc.sc_awdl_roc.token,6,1100,clock_us));

 reset();sc=make();assert(hal.awdlReserve(6,0)==kIOReturnBadArgument&&commands.empty());assert(hal.awdlReserve(6,mtkawdl::maxRocMs+1)==kIOReturnBadArgument);sc.sc_ic.ic_state=IEEE80211_S_SCAN;assert(hal.awdlReserve(6,30)==kIOReturnNotReady&&sc.sc_awdl_roc_scan_blocked==1&&sc.sc_awdl_roc_submitted==0);
 assert(scan_cancels==1&&scan_tasks==1);
 sc.sc_ic.ic_state=0;sc.sc_flags=MWX_FLAG_SCANNING|MWX_FLAG_BGSCAN;
 scan_cancel_status=5;assert(hal.awdlReserve(6,70)==kIOReturnNotReady&&sc.sc_flags);
 scan_cancel_status=0;assert(hal.awdlReserve(6,70)==kIOReturnNotReady&&!sc.sc_flags);
 sc.sc_awdl_busy=true;assert(hal.awdlReserve(6,30)==kIOReturnNotReady&&sc.sc_awdl_roc_busy_blocked==1&&commands.empty());sc.sc_awdl_busy=false;
 assert(hal.awdlReserve(6,30)==0&&sc.sc_awdl_roc_submitted==1);
 sc.sc_awdl_busy=true;memcpy(sc.sc_awdl_address,addr,6);auto before=commands.size();assert(hal.awdlEnable(addr,true)==0&&commands.size()==before);uint8_t other[6]={2,8,7,6,5,4};assert(hal.awdlEnable(other,true)==kIOReturnBusy);sc.sc_awdl_busy=false;
 reset();sc=make();fail_at=1;assert(hal.awdlReserve(6,30)==kIOReturnIOError&&commands.size()==1&&!sc.sc_awdl_roc.pending);
 reset();sc=make();on_wait=[](mwx_softc*s){++s->sc_awdl_epoch;s->sc_awdl_stopping=true;};assert(hal.awdlReserve(6,30)==kIOReturnAborted&&commands.size()==1&&!sc.sc_awdl_roc.pending&&!sc.sc_awdl_busy);
 reset();sc=make();sc.sc_awdl_channel=6;for(int i=1;i<256;i++)sc.sc_awdl_token_used[i]=clock_us;assert(hal.awdlReserve(6,30)==kIOReturnBusy&&commands.empty());clock_us+=mtkawdl::rocTokenQuarantineUs+1;assert(hal.awdlReserve(6,30)==0);
 reset();sc=make();assert(hal.awdlPeer(addr,true)==0);assert(sc.sc_awdl_peers[0].wcid==15&&sc.sc_awdl_peer_used[0]);auto&peer=wire[0];assert(peer.size()==80&&peer[1]==15&&peer[5]==1);assert(mtkawdl::le32(peer.data()+12)==(STA_TYPE_STA|NETWORK_P2P));assert(mtkawdl::le16(peer.data()+30)==52);assert(peer[78]==1);assert(!memcmp(peer.data()+20,addr,6));
 auto*alias=sc.sc_awdl_peers[0].ni.ni_macaddr;assert(hal.awdlPeer(alias,false)==0&&!sc.sc_awdl_peer_used[0]);assert(!memcmp(wire.back().data()+20,addr,6));uint8_t zero[6]={};assert(!memcmp(sc.sc_awdl_peers[0].ni.ni_macaddr,zero,6));
 for(int i=0;i<3;i++){addr[5]=i;assert(hal.awdlPeer(addr,true)==0&&sc.sc_awdl_peers[i].wcid==15+i);}addr[5]=4;assert(hal.awdlPeer(addr,true)==kIOReturnNoResources);
 reset();sc=make();fw_status=7;assert(hal.awdlPeer(addr,true)==kIOReturnIOError&&!sc.sc_awdl_peer_used[0]);fw_status=0;on_wait=[](mwx_softc*s){++s->sc_awdl_epoch;s->sc_awdl_stopping=true;};assert(hal.awdlPeer(addr,true)==kIOReturnAborted&&!sc.sc_awdl_peer_used[0]&&!sc.sc_awdl_busy);
 reset();sc=make();sc.sc_awdl_busy=true;on_sleep=[&]{assert(sc.sc_awdl_stopping&&!sc.sc_awdl_enabled);sc.sc_awdl_busy=false;};mwx_awdl_quiesce(&sc);assert(sc.sc_awdl_stopping&&!sc.sc_awdl_busy&&!sc.sc_awdl_enabled);
 reset();sc=make();sc.sc_awdl_calls=1;on_sleep=[&]{assert(sc.sc_awdl_stopping);sc.sc_awdl_calls=0;};mwx_awdl_quiesce(&sc);assert(!sc.sc_awdl_calls);
 reset();sc=make();sc.sc_awdl_configured=true;sc.sc_awdl_filter_active=true;sc.sc_awdl_filter=0x15;reg=0x80000000;assert(hal.awdlEnable(nullptr,false)==0&&reg==0x80000015&&!sc.sc_awdl_configured&&!sc.sc_awdl_stopping);
 for(int fail=1;fail<=3;fail++){reset();sc=make();sc.sc_awdl_enabled=false;fail_at=fail;assert(hal.awdlEnable(addr,true)==kIOReturnIOError&&!sc.sc_awdl_enabled&&!sc.sc_awdl_busy);}
 reset();sc=make();sc.sc_awdl_enabled=false;reg=0xdeadbeef;assert(hal.awdlEnable(addr,true)==0&&sc.sc_awdl_enabled&&sc.sc_awdl_filter_active);assert(sc.sc_awdl_vif.vif_mn.wcid==18&&sc.sc_awdl_vif.idx==1);auto basic=(const sta_rec_basic*)(wire[1].data()+sizeof(sta_req_hdr));assert(basic->conn_type==(STA_TYPE_BC|NETWORK_INFRA));reg|=0x40000000;assert(hal.awdlEnable(nullptr,false)==0&&reg==0xdeadbeef);
 // Model firmware ownership across BSS deletion; reject duplicate NEW
 // station records as observed on V9, until an explicit disconnect arrives.
 reset();sc=make();sc.sc_awdl_enabled=false;model=true;
 assert(hal.awdlEnable(addr,true)==0);assert(sc.sc_awdl_station_pending[3]);
 assert(hal.awdlPeer(addr,true)==0);assert(sc.sc_awdl_station_pending[0]);
 wire.clear();commands.clear();assert(hal.awdlEnable(nullptr,false)==0);
 assert(commands.size()==3&&commands[0]==0x20003&&commands[1]==0x20003&&commands[2]==0x20001);
 for(unsigned i=0;i<2;++i){auto b=(const sta_rec_basic*)(wire[i].data()+sizeof(sta_req_hdr));assert(b->conn_state==0&&b->extra_info==EXTRA_INFO_VER);}
 assert(!sc.sc_awdl_station_pending[0]&&!sc.sc_awdl_station_pending[3]);
 assert(hal.awdlEnable(addr,true)==0);
 // Failed deletion retains the context and station for a later retry.
 fw_status=0x10003;assert(hal.awdlEnable(nullptr,false)==kIOReturnIOError);
 assert(sc.sc_awdl_configured&&sc.sc_awdl_station_pending[3]&&!sc.sc_awdl_enabled);
 fw_status=0;assert(hal.awdlEnable(addr,true)==0&&sc.sc_awdl_station_pending[3]);
 assert(hal.awdlEnable(nullptr,false)==0);
 // Epoch changes while a station disconnect is waiting: retain ownership
 // and never remove the BSS from the stale operation.
 reset();sc=make();sc.sc_awdl_configured=true;sc.sc_awdl_station_pending[3]=true;
 on_wait=[](mwx_softc*s){++s->sc_awdl_epoch;};
 assert(hal.awdlEnable(nullptr,false)==kIOReturnAborted);
 assert(sc.sc_awdl_configured&&sc.sc_awdl_station_pending[3]&&commands.size()==1);
 // Queue submission retains the original on every transient path. The raw
 // consuming TX primitive may free an attempted DMA packet even on failure.
 reset();sc=make();memcpy(sc.sc_awdl_address,addr,6);
 auto packet=[&](bool multicast){auto*m=new mbuf;++txLive;m->len=m->packetLen=56;
  memcpy(m->bytes+10,addr,6);memcpy(m->bytes+16,mtkawdl::bssid,6);
  memcpy(m->bytes+4,addr,6);m->bytes[4]=multicast?1:2;m->bytes[55]=91;return m;};
 auto grant=[&]{sc.sc_awdl_roc.request(11,6,clock_us);assert(sc.sc_awdl_roc.grant(11,6,70,clock_us));};
 mbuf_t queued=packet(true),original=queued;
 assert(hal.awdlTryTransmit(&queued,6)==kIOReturnNotReady&&queued==original&&txLive==1&&txCalls==0);
 assert(sc.sc_awdl_tx_no_grant==1);grant();
 sc.sc_awdl_busy=true;assert(hal.awdlTryTransmit(&queued,6)==kIOReturnNotReady&&queued==original);sc.sc_awdl_busy=false;
 assert(sc.sc_awdl_tx_busy==1&&!sc.sc_awdl_calls);
 txFull=true;assert(hal.awdlTryTransmit(&queued,6)==kIOReturnNoResources&&queued==original&&txCalls==0);txFull=false;
 assert(sc.sc_awdl_tx_backpressure==1);
 copyFailure=true;assert(hal.awdlTryTransmit(&queued,6)==kIOReturnNoMemory&&queued==original&&txLive==1);copyFailure=false;
 assert(sc.sc_awdl_tx_copy_failed==1);
 for(int err:{ENOBUFS,EFBIG,EBUSY}){
  txResult=err;assert(hal.awdlTryTransmit(&queued,6)==kIOReturnNoResources&&queued==original&&txLive==1);
  assert(queued->bytes[55]==91&&sc.sc_awdl_tx_errno==err&&!sc.sc_awdl_busy&&!sc.sc_awdl_calls);
 }
 assert(sc.sc_awdl_tx_dma_failed==3);
 txResult=0;assert(hal.awdlTryTransmit(&queued,6)==0&&!queued&&txLive==0);
 assert(txNode==&sc.sc_awdl_vif.vif_mn.ni&&lastTx.back()==91&&sc.sc_awdl_tx_submitted==1);
 queued=packet(false);original=queued;int callsBefore=txCalls;
 assert(hal.awdlTryTransmit(&queued,6)==kIOReturnNotFound&&queued==original&&txCalls==callsBefore&&sc.sc_awdl_tx_no_peer==1);
 sc.sc_awdl_peer_used[1]=true;memcpy(sc.sc_awdl_peers[1].ni.ni_macaddr,queued->bytes+4,6);
 assert(hal.awdlTryTransmit(&queued,6)==0&&!queued&&!txLive&&txNode==&sc.sc_awdl_peers[1].ni);
 queued=packet(true);queued->packetLen=55;
 assert(hal.awdlTryTransmit(&queued,6)==kIOReturnBadArgument&&!queued&&!txLive&&sc.sc_awdl_tx_bad_frame==1);
 queued=packet(true);queued->bytes[10]^=4;
 assert(hal.awdlTryTransmit(&queued,6)==kIOReturnBadArgument&&!queued&&!txLive&&sc.sc_awdl_tx_bad_frame==2);
 // Management remains always consumed, including blocked/invalid requests.
 sc.sc_awdl_roc.cancel();assert(hal.awdlTransmit(packet(true),6)==kIOReturnNotReady&&!txLive);
 sc.sc_awdl_stopping=true;assert(hal.awdlTransmit(packet(true),6)==kIOReturnNotReady&&!txLive);
 assert(hal.awdlTryTransmit(nullptr,6)==kIOReturnBadArgument);
 puts("PASS actual HAL AWDL builders and TX: regulatory/ROC/WTBL, grant/token/teardown, retained data on no-grant/busy/peer/ring/copy/DMA failure, exact packet ownership, broadcast/unicast node selection and consumed management API.");
}
'''
with tempfile.TemporaryDirectory(prefix='mtk-awdl-hal-') as tmp:
 p=Path(tmp)/'test.cpp';p.write_text(code)
 subprocess.run(['clang++','-std=c++14','-Wall','-Wextra','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I'+str(root/'include'),str(p),'-o',str(Path(tmp)/'test')],check=True)
 subprocess.run([str(Path(tmp)/'test')],check=True)
