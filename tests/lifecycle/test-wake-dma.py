#!/usr/bin/env python3
"""Run production DMA recovery/initialization with lost firmware ring state.

Register and allocation mocks check sequencing, buffer ownership and failure
containment; they do not establish hardware wake or AirDrop interoperability.
"""
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
#include <cstdio>
#include <cstring>
#include <cerrno>
#include <map>
#include <vector>
#include <sys/queue.h>
#define GENMASK(h,l) ((uint32_t(~0U)<<(l)) & (uint32_t(~0U)>>(31-(h))))
#define __packed __attribute__((packed))
#define __aligned(n) __attribute__((aligned(n)))
#define IEEE80211_ADDR_LEN 6
#define IEEE80211_NWID_LEN 32
#include "if_mwxreg.h"
#define htole32(x) (x)
#define KASSERT(x) assert(x)
#define MWX_DEV_LOG(...) ((void)0)
#define DPRINTF(...) ((void)0)
#define DEVNAME(sc) "test"
#define IFF_UP 1
#define IFF_RUNNING 2
#define IEEE80211_M_MONITOR 5
#define IEEE80211_S_RUN 4
#define BUS_DMASYNC_PREWRITE 1
#define BUS_DMASYNC_POSTWRITE 2
#define BUS_DMASYNC_POSTREAD 4
struct IOLock {bool held=false;};
IOLock lock;IOLock*mwx_txq_lock=&lock;
void IOLockLock(IOLock*l){assert(!l->held);l->held=true;}
void IOLockUnlock(IOLock*l){assert(l->held);l->held=false;}
struct OSObject{};using IOReturn=int;
struct WorkLoop {bool held=false;unsigned closed=0,opened=0;
 int runAction(int(*fn)(OSObject*,void*,void*,void*,void*),OSObject*target,void*arg){
  assert(!held&&!lock.held);held=true;++closed;int rv=fn(target,arg,nullptr,nullptr,nullptr);
  assert(held&&!lock.held);held=false;++opened;return rv;
 }
};
struct Intr:OSObject {WorkLoop*workloop;Intr(WorkLoop*w):workloop(w){}};using pci_intr_handle_t=Intr*;
struct Map {size_t dm_mapsize=128;unsigned dm_nsegs=1;
 struct{uint64_t ds_addr=0x1000;}dm_segs[1];bool loaded=true;
};
struct mbuf {bool freed=false;};unsigned frees=0,unloads=0;
void m_freem(mbuf*m){assert(!m->freed);m->freed=true;++frees;}
void bus_dmamap_sync(int,Map*,int,size_t,int){}
void bus_dmamap_unload(int,Map*m){assert(m->loaded);m->loaded=false;++unloads;}
struct mwx_txwi {mt76_txwi*mt_desc;mbuf*mt_mbuf;Map*mt_map;
 unsigned mt_idx;int mt_busy;LIST_ENTRY(mwx_txwi)mt_entry;
};
struct mwx_queue_data {mbuf*md_mbuf;mwx_txwi*md_txwi;Map*md_map;};
struct mwx_queue {uint32_t mq_regbase;unsigned mq_count=2,mq_cons=1,mq_prod=1;
 mwx_desc*mq_desc;mwx_queue_data*mq_data;Map*mq_map;
};
struct ifnet {void*if_softc;unsigned if_flags=IFF_UP;int if_snd=0;};
struct Node {void*ni_chan;};struct mwx_node{unsigned wcid=19;};
struct ieee80211com {ifnet ic_if;unsigned ic_state=0,ic_opmode=1;
 Node*ic_bss;void*ic_ibss_chan;
};
struct mwx_softc {ieee80211com sc_ic;bool sc_fw_loaded=true;
 struct {mwx_node vif_mn;}sc_vif;uint32_t sc_intr_mask=0x1234,sc_rxfilter=0;
 int sc_dmat=0,sc_dma_stall_logged=0,sc_dma_to=0;IOLock*sc_awdl_lock=nullptr;
 bool sc_awdl_stopping=true;void*sc_ih;
 mwx_queue sc_txq,sc_txmcuq,sc_txfwdlq,sc_rxq,sc_rxmcuq,sc_rxfwdlq;
 struct {unsigned mt_count=0,mt_inuse=0;mwx_txwi*mt_data;
 LIST_HEAD(,mwx_txwi)mt_freelist;}sc_txwi;
};
std::map<uint32_t,uint32_t>regs;bool busy=false,ownFail=false;
int fillFail=0;unsigned fills=0,resets=0,commands=0;
uint32_t mwx_read(mwx_softc*,uint32_t r){return regs[r];}
void mwx_write(mwx_softc*,uint32_t r,uint32_t v){regs[r]=v;}
void mwx_set(mwx_softc*s,uint32_t r,uint32_t m){mwx_write(s,r,regs[r]|m);}
void mwx_clear(mwx_softc*s,uint32_t r,uint32_t m){mwx_write(s,r,regs[r]&~m);}
void mwx_barrier(mwx_softc*){}void delay(unsigned){}
int mwx_poll(mwx_softc*,uint32_t r,uint32_t,uint32_t,unsigned){
 return r==MT_CONN_ON_LPCTL?(ownFail?EIO:0):(busy?ETIMEDOUT:0);
}
int mwx_wfsys_reset(mwx_softc*){++resets;return 0;}
int mwx_queue_fill(mwx_softc*s,mwx_queue*q){
 ++fills;if(fillFail==int(fills))return ENOMEM;
 q->mq_prod=q->mq_count-1;mwx_write(s,q->mq_regbase+MT_DMA_CPU_IDX,q->mq_prod);
 return 0;
}
void ifq_clr_oactive(int*){}void timeout_add_sec(int*,int){}
int mwx_preinit(mwx_softc*){return 0;}
int command(mwx_softc*s){
 assert(!lock.held&&!static_cast<Intr*>(s->sc_ih)->workloop->held);
 assert(regs[MT_WFDMA_DUMMY_CR]&MT_WFDMA_NEED_REINIT);
 assert(regs[MT_WFDMA0_HOST_INT_ENA]==s->sc_intr_mask);
 assert((regs[MT_WFDMA0_GLO_CFG]&(MT_WFDMA0_GLO_CFG_TX_DMA_EN|MT_WFDMA0_GLO_CFG_RX_DMA_EN))==
 (MT_WFDMA0_GLO_CFG_TX_DMA_EN|MT_WFDMA0_GLO_CFG_RX_DMA_EN));
 ++commands;return 0;
}
int mwx_mcu_set_deep_sleep(mwx_softc*s,int){return command(s);}
int mt7921_mcu_set_mac_enable(mwx_softc*s,int,int){return command(s);}
int mt7921_mcu_set_channel_domain(mwx_softc*s){return command(s);}
int mt7921_mcu_set_rate_txpower(mwx_softc*s){return command(s);}
void mt7921_mac_reset_counters(mwx_softc*){}
void mwx_mac_wtbl_update(mwx_softc*,unsigned){}
int mt7921_mcu_uni_add_dev(mwx_softc*s,void*,void*,int){return command(s);}
int mt7921_mcu_set_tx(mwx_softc*s,void*){return command(s);}
int mt7921_mcu_set_chan_info(mwx_softc*s,int){return command(s);}
int mt7921_set_channel(mwx_softc*s){return command(s);}
int mt7921_mcu_set_sniffer(mwx_softc*s,int){return command(s);}
int mt7921_mcu_set_beacon_filter(mwx_softc*s,int){return command(s);}
void ieee80211_new_state(ieee80211com*,int,int){}
void ieee80211_begin_scan(ifnet*){}
'''
for sig in ('void\nmwx_txwi_put(', 'void\nmwx_queue_reset(',
            'int\nmwx_dma_disable(', 'void\nmwx_dma_enable(',
            'int\nmwx_dma_reset(', 'int\nmwx_mcu_drv_pmctrl('):
    code += function(sig)
if 'static int\nmwx_dma_reinit_cond(' in source:
    if 'static IOReturn\nmwx_dma_reinit_gated(' in source:
        code += function('static IOReturn\nmwx_dma_reinit_gated(')
    code += function('static int\nmwx_dma_reinit_cond(')
else:
    code += 'int mwx_dma_reinit_cond(mwx_softc*) {return 0;}\n'
code += function('static int\nmwx_init_running(')
code += r'''
struct Fixture {
 WorkLoop loop;Intr intr{&loop};mwx_softc sc{};Map maps[7],bufferMaps[6],tokenMaps[2];
 mwx_desc desc[6][2]{};mwx_queue_data entries[6][2]{};
 mbuf packets[8]{};mt76_txwi txp[2]{};mwx_txwi tokens[2]{};
 Fixture(){
  regs.clear();frees=unloads=fills=resets=commands=0;busy=ownFail=false;fillFail=0;
  sc.sc_ih=&intr;sc.sc_ic.ic_if.if_softc=&sc;
  mwx_queue*qs[]={&sc.sc_txq,&sc.sc_txmcuq,&sc.sc_txfwdlq,&sc.sc_rxq,&sc.sc_rxmcuq,&sc.sc_rxfwdlq};
  for(unsigned i=0;i<6;i++){
   *qs[i]={0x10000+i*0x100,2,1,1,desc[i],entries[i],&maps[i]};
   entries[i][0]={&packets[i],&tokens[0],&bufferMaps[i]};
  }
  sc.sc_txwi.mt_count=2;sc.sc_txwi.mt_inuse=2;sc.sc_txwi.mt_data=tokens;
  LIST_INIT(&sc.sc_txwi.mt_freelist);
  for(unsigned i=0;i<2;i++)tokens[i]={&txp[i],&packets[6+i],&tokenMaps[i],MT_PACKET_ID_FIRST+i,1,{}};
 }
 void retained(){regs[MT_WFDMA_DUMMY_CR]=MT_WFDMA_NEED_REINIT;
  regs[MT_WFDMA0_GLO_CFG]=MT_WFDMA0_GLO_CFG_TX_DMA_EN|MT_WFDMA0_GLO_CFG_RX_DMA_EN;
  regs[MT_WFDMA0_HOST_INT_ENA]=sc.sc_intr_mask;}
};
int main(){
 // Exact failure state: ownership available, marker/interrupts/DMA gone,
 // software ring indices and buffer/token ownership still from before sleep.
 for(unsigned cycle=0;cycle<100;cycle++){
  Fixture f;assert(!mwx_init_running(&f.sc.sc_ic.ic_if));
  assert(commands>0&&fills==3&&resets==0&&frees==8&&unloads==8);
  assert(f.loop.closed==1&&f.loop.opened==1&&!lock.held&&!f.loop.held);
  assert(f.sc.sc_txwi.mt_inuse==0);
  for(auto&t:f.tokens)assert(!t.mt_busy&&!t.mt_mbuf);
  for(auto&pair:f.entries)assert(!pair[0].md_txwi&&!pair[0].md_mbuf);
  assert(f.sc.sc_ic.ic_if.if_flags&IFF_RUNNING);
  assert(!mwx_dma_reinit_cond(&f.sc)&&fills==3&&f.loop.closed==1);
 }
 // No destructive reset when firmware retained its rings.
 {Fixture f;f.retained();assert(!mwx_init_running(&f.sc.sc_ic.ic_if));
  assert(!fills&&!frees&&!unloads&&!f.loop.closed&&f.tokens[0].mt_busy);}
 // Driver ownership failure must stop before MCU commands or DMA recovery.
 {Fixture f;ownFail=true;assert(mwx_init_running(&f.sc.sc_ic.ic_if)==EIO);
  assert(!commands&&!fills&&!frees&&!f.loop.closed);}
 // DMA busy / RX allocation failures propagate and leave interrupts masked.
 for(int failure=0;failure<=3;failure++){
  Fixture f;busy=failure==0;fillFail=failure;
  assert(mwx_init_running(&f.sc.sc_ic.ic_if)==(failure?ENOMEM:ETIMEDOUT));
  assert(!commands&&!regs[MT_WFDMA0_HOST_INT_ENA]&&!regs[MT_PCIE_MAC_INT_ENABLE]);
  assert(!(f.sc.sc_ic.ic_if.if_flags&IFF_RUNNING)&&!f.loop.held&&!lock.held);
  assert(f.sc.sc_txwi.mt_inuse==unsigned(failure?0:2));
 }
 // Partial attach / active interface cannot reset unallocated or live rings.
 {Fixture f;f.sc.sc_rxq.mq_map=nullptr;assert(mwx_dma_reinit_cond(&f.sc)==ENXIO);
  assert(!fills&&!frees&&!f.loop.closed);}
 {Fixture f;f.sc.sc_ic.ic_if.if_flags|=IFF_RUNNING;assert(mwx_dma_reinit_cond(&f.sc)==EBUSY);
  assert(!fills&&!frees&&!f.loop.closed);}
 // Firmware reload also retires TXP tokens before reusing reset DMA rings.
 {Fixture f;assert(!mwx_dma_reset(&f.sc,1));assert(resets==1&&fills==3);
  assert(f.sc.sc_txwi.mt_inuse==0&&frees==8&&unloads==8);}
 puts("PASS production wake DMA/init: 100 lost-context recoveries, retained rings, ownership/busy/allocation errors, gate ordering, stale ring pointers and exact token/buffer reclamation.");
}
'''
with tempfile.TemporaryDirectory(prefix='mtk-wake-dma-') as tmp:
    cpp = Path(tmp)/'test.cpp'
    cpp.write_text(code)
    exe = cpp.with_suffix('')
    subprocess.run(['clang++', '-std=c++14', '-fsanitize=address,undefined',
                    '-fno-omit-frame-pointer', '-I'+str(root/'SimpleMtkWlan/hal_mwx'),
                    str(cpp), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
