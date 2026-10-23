#!/usr/bin/env python3
"""Execute production TXS/MCU dispatch: ACKs, failures and WCID isolation."""
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
#include <initializer_list>
#include <AWDL/AwdlProtocol.hpp>
#define __packed __attribute__((packed))
#define le32toh(x) (x)
#define MWX_DEV_LOG(...) ((void)0)
#define MT_PACKET_ID_FIRST 3
#define IEEE80211_S_RUN 4
#define MT_TX_RATE_MODE_MASK (15U<<6)
#define MT_TX_RATE_MODE_SHIFT 6
#define MT_TX_RATE_IDX_MASK 63
#define MT_TX_RATE_NSS_MASK (3U<<10)
#define MT_TX_RATE_NSS_SHIFT 10
#define MT_TX_RATE_STBC (1U<<12)
#define MT_PHY_TYPE_HT 2
#define MT_PHY_TYPE_HT_GF 3
#define MT_PHY_TYPE_VHT 4
struct ieee80211_node { unsigned ni_txmcs=0,ni_vht_ss=0; };
struct mwx_node { ieee80211_node ni; uint16_t wcid; };
struct ieee80211com { ieee80211_node *ic_bss=nullptr; unsigned ic_state=0; };
struct mwx_softc { mtkawdl::TxStatusCounters sc_awdl_tx_status; ieee80211com sc_ic; unsigned sc_txs_count=0; };
struct mbuf {uint8_t bytes[96]{};size_t len=0;};
size_t mbuf_len(mbuf*m){return m->len;}
#define mtod(m,t) reinterpret_cast<t>((m)->bytes)
void mt7921_mac_add_txs(mwx_softc*,const uint32_t*);
'''
code += function('void\nmt7921_mac_add_txs(')
code += function('void\nmt7921_mcu_tx_done_event(')
code += r'''
int main(){
 mwx_softc sc{};mwx_node ap{};ap.wcid=4;
 sc.sc_ic.ic_bss=&ap.ni;sc.sc_ic.ic_state=4;
 uint32_t words[8]{};
 auto status=[&](unsigned wcid,unsigned pid,unsigned error,unsigned format=0){
  memset(words,0,sizeof(words));words[0]=(MT_PHY_TYPE_VHT<<6)|7|(1U<<10)|error|(format<<23);
  words[1]=0xabcU<<20;words[2]=wcid<<16;words[3]=pid<<24;
  mt7921_mac_add_txs(&sc,words);
 };
 // AWDL unicast status must never change the infrastructure link's rate.
 status(15,mtkawdl::txPidUnicast,0);
 assert(sc.sc_awdl_tx_status.dataAcked==1&&ap.ni.ni_txmcs==0&&sc.sc_txs_count==0);
 for(unsigned error:{1U<<16,1U<<17,1U<<18}) status(16,mtkawdl::txPidUnicast,error);
 assert(sc.sc_awdl_tx_status.dataFailed==3&&sc.sc_awdl_tx_status.dataAcked==1);
 status(18,mtkawdl::txPidMulticast,0);status(18,mtkawdl::txPidMulticast,1U<<18);
 status(18,mtkawdl::txPidAction,0);status(18,mtkawdl::txPidAction,1U<<18);
 assert(sc.sc_awdl_tx_status.multicastCompleted==1&&sc.sc_awdl_tx_status.multicastFailed==1);
 assert(sc.sc_awdl_tx_status.actionCompleted==1&&sc.sc_awdl_tx_status.actionFailed==1);
 assert(sc.sc_awdl_tx_status.lastSequence==0xabc&&sc.sc_awdl_tx_status.lastWcid==18);
 status(15,mtkawdl::txPidUnicast,0,2);status(15,mtkawdl::txPidUnicast,0,3);
 status(15,3,0);assert(sc.sc_awdl_tx_status.dataAcked==1&&sc.sc_txs_count==0);
 status(5,3,0);assert(sc.sc_txs_count==0); // A different infrastructure WCID.
 status(4,3,0);assert(sc.sc_txs_count==1&&ap.ni.ni_txmcs==7&&ap.ni.ni_vht_ss==2);
 status(4,3,0,2);assert(sc.sc_txs_count==1);
 // Firmware TX results still count when no infrastructure BSS is running.
 sc.sc_ic.ic_bss=nullptr;sc.sc_ic.ic_state=0;
 status(17,mtkawdl::txPidUnicast,0,1);assert(sc.sc_awdl_tx_status.dataAcked==2);
 // The MCU event contains seven packed TXS words. Copy safely before dispatch.
 mbuf event;memcpy(event.bytes+28,words,28);
 for(size_t len=0;len<88;++len){event.len=len;mt7921_mcu_tx_done_event(&sc,&event);}
 assert(sc.sc_awdl_tx_status.dataAcked==2);
 event.len=88;mt7921_mcu_tx_done_event(&sc,&event);
 assert(sc.sc_awdl_tx_status.dataAcked==3);
 for(size_t len=0;len<32;++len)assert(!sc.sc_awdl_tx_status.observe(event.bytes,len));
 puts("PASS production TX status: unicast ACK/error, multicast/action completion, packed MCU event, short records, PPDU filtering and infrastructure WCID isolation.");
}
'''
with tempfile.TemporaryDirectory(prefix='mtk-awdl-txs-') as directory:
    path = Path(directory)
    (path/'test.cpp').write_text(code)
    subprocess.run(['clang++', '-std=c++14', '-fsanitize=address,undefined',
                    '-I'+str(root/'include'), str(path/'test.cpp'),
                    '-o', str(path/'test')], check=True)
    subprocess.run([str(path/'test')], check=True)
