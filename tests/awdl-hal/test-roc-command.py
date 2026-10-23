#!/usr/bin/env python3
"""Execute production MCU headers/RX to check asynchronous ROC ACK ownership."""
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parents[2]
source = (Path(sys.argv[1]) if len(sys.argv) > 1 else
          root / 'SimpleMtkWlan/hal_mwx/MtkMwx.cpp').read_text()
def function(signature):
    start = source.index(signature)
    return source[start:source.index('\n}\n', start) + 3]

code = r'''
#include <cassert>
#include <cstdint>
#include <cstring>
#include <cstdio>
#include <cerrno>
#include <vector>
#include <algorithm>
#include <sys/time.h>
#include <AWDL/AwdlProtocol.hpp>
#define GENMASK(h,l) ((uint32_t(~0U)<<(l)) & (uint32_t(~0U)>>(31-(h))))
#define __packed __attribute__((packed))
#define __aligned(n) __attribute__((aligned(n)))
#define IEEE80211_ADDR_LEN 6
#define IEEE80211_NWID_LEN 32
#include "if_mwxreg.h"
#define mtod(m,t) ((t)((m)->bytes.data()+(m)->offset))
#define htole16(x) (x)
#define htole32(x) (x)
#define le16toh(x) (x)
#define le32toh(x) (x)
#define nitems(x) (sizeof(x)/sizeof((x)[0]))
#define KASSERT(x) assert(x)
#define MWX_DEV_LOG(...) ((void)0)
#define DEVNAME(sc) "test"
#define M_DONTWAIT 0
#define MSEC_TO_NSEC(x) ((x)*1000000ULL)
using caddr_t=char*;
struct mbuf {std::vector<uint8_t> bytes;size_t offset=0;};
unsigned live=0;mbuf*packet(size_t n){++live;return new mbuf{{std::vector<uint8_t>(n)}};}
void m_freem(mbuf*m){--live;delete m;}
size_t mbuf_pkthdr_len(mbuf*m){return m->bytes.size()-m->offset;}
size_t mbuf_len(mbuf*m){return mbuf_pkthdr_len(m);}
size_t m_leadingspace(mbuf*m){return m->offset;}
mbuf*MCLGETL(void*,int,size_t n){return packet(n);}
void mbuf_setlen(mbuf*m,size_t n){m->bytes.resize(n);}
void mbuf_pkthdr_setlen(mbuf*,size_t){}
int mbuf_copydata(mbuf*m,size_t at,size_t n,void*out){assert(at+n<=mbuf_len(m));memcpy(out,mtod(m,uint8_t*)+at,n);return 0;}
mbuf*m_prepend(mbuf*m,size_t n,int){assert(m->offset>=n);m->offset-=n;return m;}
mbuf*m_pullup(mbuf*m,size_t n){if(n>mbuf_len(m)){m_freem(m);return nullptr;}return m;}
void m_adj(mbuf*m,size_t n){assert(n<=mbuf_len(m));m->offset+=n;}
struct IOLock {bool held=false;};
void IOLockLock(IOLock*l){assert(!l->held);l->held=true;}
void IOLockUnlock(IOLock*l){assert(l->held);l->held=false;}
struct mwx_queue {uint32_t mq_regbase=0;bool mq_wakeme=false;};
struct mwx_softc {
 mwx_queue sc_txmcuq,sc_txfwdlq;unsigned sc_mcu_seq=0;
 struct Wait{uint32_t mcu_cmd=0,mcu_int=0;mbuf*mcu_m=nullptr;bool mcu_done=false;}sc_mcu_wait[16];
 uint64_t sc_mcu_events=0,sc_mcu_bad_seq=0;unsigned sc_last_mcu_eid=0;bool sc_resetting=false;
 IOLock*sc_awdl_lock=nullptr;uint64_t sc_awdl_roc_command_results=0,sc_awdl_roc_command_failed=0,
 sc_awdl_roc_command_malformed=0,sc_awdl_roc_command_result_us=0;uint32_t sc_awdl_roc_command_status=0;
 mtkawdl::Reservation sc_awdl_roc{};
};
std::vector<uint8_t> sent;unsigned enqueues=0,wakes=0,grantEvents=0,mwx_ebusy_sleeps=0;
int mwx_dma_tx_enqueue(mwx_softc*,mwx_queue*,mbuf*m){++enqueues;sent.assign(mtod(m,uint8_t*),mtod(m,uint8_t*)+mbuf_len(m));m_freem(m);return 0;}
int splnet(){return 0;}void splx(int){}int tsleep_nsec(void*,int,const char*,uint64_t){assert(false);return 0;}
struct Hal {void mwxWakeup(void*){++wakes;}};Hal hal;Hal*gMwxHal=&hal;
void wakeup(void*){++wakes;}
uint64_t mach_absolute_time(){return 123456000;}void absolutetime_to_nanoseconds(uint64_t t,uint64_t*out){*out=t;}
void mwx_awdl_roc_event(mwx_softc*,const uint8_t*,size_t,uint64_t){++grantEvents;}
void mt7921_mcu_scan_event(mwx_softc*,mbuf*){}
void mt7921_mcu_beacon_loss_event(mwx_softc*,mbuf*){}
void mt7921_mcu_low_power_event(mwx_softc*,mbuf*){}
void mt7921_mcu_tx_done_event(mwx_softc*,mbuf*){}
void mwx_reset(mwx_softc*){}
'''
if 'static bool mwx_awdl_roc_command_result(' in source:
    code += function('static bool mwx_awdl_roc_command_result(')
code += function('int\nmwx_mcu_send_mbuf(')
code += function('void\nmwx_mcu_rx_event(')
code += r'''
void result(mwx_softc&sc,uint8_t cid,unsigned status,unsigned seq,size_t body=8,unsigned option=MCU_UNI_CMD_EVENT,unsigned eid=MCU_UNI_EVENT_RESULT){
 auto*m=packet(MT7921_MCU_RXD_SIZE+sizeof(mwx_mcu_rxd)+body);
 auto*r=reinterpret_cast<mwx_mcu_rxd*>(m->bytes.data()+MT7921_MCU_RXD_SIZE);
 r->len=sizeof(*r)+body;r->eid=eid;r->seq=seq;r->option=option;
 auto*p=reinterpret_cast<uint8_t*>(r+1);if(body)p[0]=cid;if(body>=8)mtkawdl::put32(p+4,status);
 mwx_mcu_rx_event(&sc,m);
}
int main(){
 IOLock lock;mwx_softc sc;sc.sc_awdl_lock=&lock;
 // Complete DMA command header, not a mocked HAL payload: ROC async SET
 // must carry the same ACK/UNI/SET option 7 as Linux's connac2 builder.
 for(bool waits:{false,true})for(unsigned tag:{0,1}) {
  auto*m=packet(tag?16:28);mtkawdl::put16(m->bytes.data()+4,tag);int seq=0;
  assert(!mwx_mcu_send_mbuf(&sc,0x20027,m,waits?&seq:nullptr));
  auto*t=reinterpret_cast<const mwx_uni_txd*>(sent.data());
  assert(t->option==7&&t->cid==0x27&&t->pkt_type==MCU_PKT_ID&&t->s2d_index==0);
  assert(t->len==sent.size()-32&&t->seq&&t->seq<16);
  assert(mtkawdl::le16(sent.data()+sizeof(*t)+4)==tag);
 }
 // Other existing asynchronous commands preserve their header options.
 assert(!mwx_mcu_send_mbuf(&sc,MCU_UNI_CMD_BSS_INFO_UPDATE,packet(4),nullptr));
 assert(reinterpret_cast<const mwx_uni_txd*>(sent.data())->option==6);
 // A later synchronous BSS command owns the same four-bit sequence as an
 // old ROC ACK. CID routing must preserve its waiter and free every ROC ACK.
 int seq=0;assert(!mwx_mcu_send_mbuf(&sc,MCU_UNI_CMD_BSS_INFO_UPDATE,packet(4),&seq));
 sc.sc_awdl_roc.request(42,6,100000);
 auto radio=sc.sc_awdl_roc;unsigned owned=live;
 for(unsigned status:{0,0x10003}) {
  result(sc,0x27,status,seq);
  assert(!sc.sc_mcu_wait[seq].mcu_done&&sc.sc_mcu_wait[seq].mcu_m==nullptr&&wakes==0);
  assert(live==owned&&sc.sc_awdl_roc.pending&&sc.sc_awdl_roc.token==radio.token&&sc.sc_awdl_roc.deadline==radio.deadline);
 }
 assert(sc.sc_awdl_roc_command_results==2&&sc.sc_awdl_roc_command_failed==1);
 assert(sc.sc_awdl_roc_command_status==0x10003&&sc.sc_awdl_roc_command_result_us==123456);
 result(sc,0x27,0,seq,1);assert(sc.sc_awdl_roc_command_malformed==1&&live==owned);
 // Unsolicited grants still go only to the grant decoder.
 result(sc,0x27,0,seq,24,MCU_UNI_CMD_UNSOLICITED_EVENT,MCU_UNI_EVENT_ROC);
 assert(grantEvents==1&&sc.sc_awdl_roc_command_results==2&&live==owned);
 // The matching BSS result still completes its synchronous waiter.
 result(sc,2,0x55,seq);assert(sc.sc_mcu_wait[seq].mcu_done&&wakes==1);
 assert(sc.sc_mcu_wait[seq].mcu_int==0x55&&live==owned+1);
 m_freem(sc.sc_mcu_wait[seq].mcu_m);sc.sc_mcu_wait[seq].mcu_m=nullptr;
 // No initialized AWDL lock: consume ROC result without touching teardown.
 sc.sc_awdl_lock=nullptr;result(sc,0x27,0,seq);assert(live==0);
 puts("PASS production ROC DMA header + RX: Linux async ACK options, CID waiter isolation, ACK/grant separation, malformed results and packet ownership.");
}
'''
with tempfile.TemporaryDirectory(prefix='mtk-roc-command-') as tmp:
    cpp = Path(tmp) / 'test.cpp'
    binary = Path(tmp) / 'test'
    cpp.write_text(code)
    subprocess.run(['clang++', '-std=c++14', '-Wall', '-Wextra',
                    '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                    '-I'+str(root/'include'), '-I'+str(root/'SimpleMtkWlan/hal_mwx'),
                    str(cpp), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
