#!/usr/bin/env python3
"""Execute production TXWI builders to verify AWDL OFDM and native context."""
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
#include <sys/time.h>
#include <AWDL/AwdlProtocol.hpp>
#define GENMASK(h,l) ((uint32_t(~0U)<<(l)) & (uint32_t(~0U)>>(31-(h))))
#define __packed __attribute__((packed))
#define __aligned(n) __attribute__((aligned(n)))
#define IEEE80211_ADDR_LEN 6
#define IEEE80211_NWID_LEN 32
#include "if_mwxreg.h"
#define htole32(x) (x)
#define NBPFILTER 0
#define MWX_KNOB_DATA_RA 1
#define MWX_KNOB_TX_VO 2
#define IEEE80211_FC0_TYPE_MASK 0x0c
#define IEEE80211_FC0_TYPE_SHIFT 2
#define IEEE80211_FC0_TYPE_DATA 8
#define IEEE80211_FC0_TYPE_CTL 4
#define IEEE80211_FC0_TYPE_MGT 0
#define IEEE80211_FC0_SUBTYPE_MASK 0xf0
#define IEEE80211_FC0_SUBTYPE_SHIFT 4
#define IEEE80211_FC0_SUBTYPE_ACTION 0xd0
#define IEEE80211_FC1_PROTECTED 0x40
#define IEEE80211_CATEG_BA 3
#define IEEE80211_ACTION_ADDBA_REQ 0
#define IEEE80211_QOS_TID 15
#define IEEE80211_IS_MULTICAST(p) ((p)[0]&1)
#define mtod(m,t) ((t)(m)->bytes)
struct ieee80211_frame {uint8_t i_fc[2],duration[2],i_addr1[6],i_addr2[6],i_addr3[6],seq[2];};
struct ieee80211_frame_min {uint8_t bytes[10];};
struct ieee80211_node {};
struct mwx_node {ieee80211_node ni;uint16_t wcid;};
struct mwx_vif {mwx_node vif_mn;uint8_t omac_idx,wmm_idx,band_idx;};
struct ieee80211com {};
struct mwx_softc {ieee80211com sc_ic;mwx_vif sc_vif,sc_awdl_vif;mwx_node sc_awdl_peers[3];int sc_knobs;timeval sc_txs_last;};
struct mbuf {uint8_t bytes[100];size_t len;};
using u_int=unsigned;
size_t mbuf_len(mbuf*m){return m->len;}
size_t mbuf_pkthdr_len(mbuf*m){return m->len;}
bool ieee80211_has_qos(ieee80211_frame*f){return (f->i_fc[0]&0x8c)==0x88;}
unsigned ieee80211_get_hdrlen(ieee80211_frame*f){return ieee80211_has_qos(f)?26:24;}
unsigned ieee80211_get_qos(ieee80211_frame*f){return ((uint8_t*)f)[24];}
unsigned rateChecks=0;bool ratecheck(timeval*,const timeval*){++rateChecks;return true;}
uint32_t mt7921_mac_tx_rate_val(mwx_softc*){return 0;}
'''
start = source.index('const struct mwx_rate {')
code += source[start:source.index('\n};', start) + 3]
code += function('void\nmt7921_mac_write_txwi_80211(')
code += function('static inline uint8_t\nmt7921_lmac_mapping(')
code += function('void\nmt7921_mac_write_txwi(')
code += r'''
int main(){
 mwx_softc sc{};sc.sc_vif={{{},4},0,0,0};sc.sc_awdl_vif={{{},18},1,1,0};
 for(unsigned i=0;i<3;++i)sc.sc_awdl_peers[i].wcid=15+i;
 for(unsigned rateControl:{0U,1U})for(unsigned channel:{6U,44U,149U})
 for(unsigned multicast:{0U,1U})for(unsigned qos:{0U,1U}) {
  sc.sc_knobs=rateControl?MWX_KNOB_DATA_RA:0;
  mbuf m{};m.len=60;m.bytes[0]=qos?0x88:8;m.bytes[4]=multicast?1:2;
  mtkawdl::put16(m.bytes+22,0xffb0);m.bytes[24]=6;
  auto *node=multicast?&sc.sc_awdl_vif.vif_mn:&sc.sc_awdl_peers[1];
  mt76_txwi tx{};mt7921_mac_write_txwi(&sc,&m,&node->ni,&tx);
  (void)channel; // OFDM is valid on both bands; descriptor is identical.
  assert((tx.txwi[0]&MT_TXD0_TX_BYTES_MASK)==m.len+MT_TXD_SIZE);
  assert((tx.txwi[1]&MT_TXD1_WLAN_IDX_MASK)==node->wcid);
  assert((tx.txwi[1]&MT_TXD1_OWN_MAC_MASK)==(1U<<24));
  assert((tx.txwi[1]&MT_TXD1_HDR_FORMAT_MASK)==MT_HDR_FORMAT_802_11);
  assert((tx.txwi[2]&(MT_TXD2_FIX_RATE|MT_TXD2_HTC_VLD))==(MT_TXD2_FIX_RATE|MT_TXD2_HTC_VLD));
  assert(bool(tx.txwi[2]&MT_TXD2_MULTICAST)==bool(multicast));
  // 6 Mbps OFDM: mode 1, hardware rate index 11; never 1 Mbps CCK.
  assert(((tx.txwi[6]&MT_TXD6_TX_RATE_MASK)>>16)==((1U<<6)|11));
  assert(tx.txwi[6]&MT_TXD6_FIXED_BW);
  assert(!(tx.txwi[6]&MT_TXD6_BW));
  assert((tx.txwi[3]&(MT_TXD3_BA_DISABLE|MT_TXD3_SN_VALID))==(MT_TXD3_BA_DISABLE|MT_TXD3_SN_VALID));
  assert(((tx.txwi[3]&MT_TXD3_SEQ)>>16)==0xffb);
  assert(bool(tx.txwi[3]&MT_TXD3_NO_ACK)==bool(multicast));
  assert(!(tx.txwi[3]&MT_TXD3_PROTECT_FRAME));
  assert(!(tx.txwi[7]&MT_TXD7_HW_AMSDU));
  assert((tx.txwi[5]&MT_TXD5_PID)==(multicast?mtkawdl::txPidMulticast:mtkawdl::txPidUnicast));
  assert(tx.txwi[5]&MT_TXD5_TX_STATUS_HOST);assert(rateChecks==0);
  assert(((tx.txwi[0]&MT_TXD0_Q_IDX_MASK)>>25)==(qos?7U:5U));
 }
 // MT7921 has MT_DRV_HW_MGMT_TXQ. MT76 routes off-channel management
 // through MT_TXQ_PSD/ALTX rather than the discovery BSS's WMM queues.
 // Exercise both PSF/MIF subtypes and broadcast/unicast identities.
 for(unsigned mode:{0U,3U})for(unsigned multicast:{0U,1U}) {
  mbuf action{};action.len=60;action.bytes[0]=0xd0;
  action.bytes[4]=multicast?1:2;action.bytes[30]=mode;
  auto*node=multicast?&sc.sc_awdl_vif.vif_mn:&sc.sc_awdl_peers[1];
  mt76_txwi descriptor{};mt7921_mac_write_txwi(&sc,&action,&node->ni,&descriptor);
  assert(((descriptor.txwi[0]&MT_TXD0_Q_IDX_MASK)>>25)==MT_LMAC_ALTX0);
  assert((descriptor.txwi[0]&MT_TXD0_PKT_FMT)==MT_TX_TYPE_CT);
  assert((descriptor.txwi[1]&MT_TXD1_OWN_MAC_MASK)==(1U<<24));
  assert((descriptor.txwi[1]&MT_TXD1_WLAN_IDX_MASK)==node->wcid);
  assert(bool(descriptor.txwi[3]&MT_TXD3_NO_ACK)==bool(multicast));
  assert((descriptor.txwi[5]&MT_TXD5_PID)==mtkawdl::txPidAction);
  assert(descriptor.txwi[5]&MT_TXD5_TX_STATUS_HOST);assert(rateChecks==0);
 }
 // Infrastructure still uses its own context and configured RA behavior.
 sc.sc_knobs=MWX_KNOB_DATA_RA;mbuf m{};m.len=60;m.bytes[0]=8;m.bytes[4]=2;
 mt76_txwi tx{};mt7921_mac_write_txwi(&sc,&m,&sc.sc_vif.vif_mn.ni,&tx);
 assert(!(tx.txwi[2]&MT_TXD2_FIX_RATE));assert(!(tx.txwi[1]&MT_TXD1_OWN_MAC_MASK));
 assert((tx.txwi[1]&MT_TXD1_WLAN_IDX_MASK)==4);
 m.bytes[0]=0xd0;tx={};mt7921_mac_write_txwi(&sc,&m,&sc.sc_vif.vif_mn.ni,&tx);
 assert(((tx.txwi[0]&MT_TXD0_Q_IDX_MASK)>>25)==3);
 puts("PASS production TXWI: AWDL data keeps WMM/6Mbps/sequence/ACK; four PSF/MIF management cases use MT76 ROC ALTX; infrastructure RA and management queue preserved.");
}
'''
with tempfile.TemporaryDirectory(prefix='mtk-awdl-txwi-') as directory:
    path = Path(directory)
    (path / 'test.cpp').write_text(code)
    subprocess.run(['clang++', '-std=c++14', '-fsanitize=address,undefined',
                    '-I'+str(root/'include'), '-I'+str(root/'SimpleMtkWlan/hal_mwx'),
                    str(path/'test.cpp'), '-o', str(path/'test')], check=True)
    subprocess.run([str(path/'test')], check=True)
