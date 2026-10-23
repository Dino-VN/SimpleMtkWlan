from pathlib import Path
import re,subprocess
base=Path(__file__).resolve().parents[2]
source=(base/'SimpleMtkWlan/hal_mwx/MtkMwx.cpp').read_text()
wire=(base/'SimpleMtkWlan/hal_mwx/if_mwxreg.h').read_text()
a=source.index('int\nmt7921_mcu_set_associated_bss(');fn=source[a:source.index('\n}\n',a)+3]
struct=re.search(r'struct mt76_connac_bss_basic_tlv \{.*?\} __packed;',wire,re.S).group()
phy='\n'.join(re.findall(r'^#define\s+PHY_MODE_.*$',wire,re.M))
code=r'''
#include <cstdint>
#include <cstring>
#include <cassert>
#include <cerrno>
#include <vector>
#include <cstdio>
#define __packed __attribute__((packed))
#define IEEE80211_ADDR_LEN 6
#define ETHER_ADDR_LEN 6
#define IEEE80211_M_STA 1
#define IEEE80211_CHAN_ANYC ((ieee80211_channel*)-1)
#define IEEE80211_IS_CHAN_2GHZ(c) ((c)->ic_freq<3000)
#define UNI_BSS_INFO_BASIC 0
#define UNI_BSS_INFO_RLM 2
#define UNI_BSS_INFO_QBSS 15
#define IEEE80211_NODE_HT 1
#define IEEE80211_NODE_VHT 2
#define IEEE80211_NODE_QOS 4
#define IEEE80211_NODE_HE 8
#define IEEE80211_F_HEON 16
#define MWX_KNOB_NO_QBSS 0x400
#define EXT_BSSID_START 16
#define HW_BSSID_0 0
#define STA_TYPE_STA 1
#define NETWORK_INFRA 65536
#define PHY_TYPE_BIT_HR_DSSS 1
#define PHY_TYPE_BIT_ERP 2
#define PHY_TYPE_BIT_OFDM 8
#define MCU_UNI_CMD_BSS_INFO_UPDATE 0x20002
#define CMD_CBW_20MHZ 0
#define MWX_DEV_LOG(...) ((void)0)
#define htole16(x) (x)
#define htole32(x) (x)
struct ieee80211_channel { int ic_freq; int width; };
struct ieee80211_node { ieee80211_channel *ni_chan; uint8_t ni_bssid[6]; uint16_t ni_intval; uint8_t ni_dtimperiod; unsigned ni_flags=0; };
struct ieee80211com { int ic_opmode; ieee80211_node *ic_bss; unsigned ic_flags=0; };
struct mwx_vif { uint8_t idx,omac_idx,band_idx,wmm_idx; struct {uint16_t wcid;} vif_mn; };
struct mwx_softc { ieee80211com sc_ic; mwx_vif sc_vif; struct {uint8_t num_streams,antenna_mask;} sc_capa; unsigned sc_knobs=0;uint8_t sc_bss_bw=0,sc_bss_center=0,sc_bss_he=0; };
int ieee80211_mhz2ieee(int f,int) {return f==2484?14:f<3000?(f-2407)/5:(f-5000)/5;}
int mt7921_mcu_chan_bw(ieee80211_channel *c){return c->width;}
std::vector<std::vector<uint8_t>> sent;
int fail_at=0;
std::vector<int> he_updates;
int he_error=0;
int mt7921_mcu_set_bss_he(mwx_softc*,ieee80211_node*,int enable){he_updates.push_back(enable);return he_error;}
int mwx_send_assoc_status(mwx_softc*,int cmd,void *p,int n){assert(cmd==0x20002);auto b=(uint8_t*)p;sent.emplace_back(b,b+n);return int(sent.size())==fail_at?EIO:0;}
'''+phy+'\n'+struct+'\n'+fn+r'''
int main(){
 ieee80211_channel c{5745,0};ieee80211_node n{&c,{0xe8,0x45,0x8b,0x39,0xe0,0xa7},100,3};
 mwx_softc sc{{1,&n},{3,2,0,1,{19}},{2,3}};
 for(int freq:{2412,2437,2462,2484,5180,5745,5825}){
  c.ic_freq=freq;sent.clear();fail_at=0;assert(mt7921_mcu_set_associated_bss(&sc,1)==0);assert(sent.size()==2);
  std::vector<uint8_t> basic={3,0,0,0,0,0,32,0,1,2,2,0,1,0,1,0,0,1,0xe8,0x45,0x8b,0x39,0xe0,0xa7,19,0,100,0,3,1,19,0,8,0,0,0,15,0,8,0,0,0,0,0};
  bool two=freq<3000;if(two){basic[29]=6;basic[32]=3;}
  assert(sent[0]==basic);
  int ch=ieee80211_mhz2ieee(freq,0);
  std::vector<uint8_t> rlm={3,0,0,0,2,0,16,0,(uint8_t)ch,(uint8_t)ch,0,0,2,3,1,0,0,(uint8_t)(two?0:1),0,0};
  assert(sent[1]==rlm);
  sent.clear();assert(mt7921_mcu_set_associated_bss(&sc,0)==0);basic[16]=1;assert(sent.size()==1&&sent[0]==basic);
 }
 for(int fail:{1,2}){sent.clear();fail_at=fail;assert(mt7921_mcu_set_associated_bss(&sc,1)==EIO);assert(sent.size()==static_cast<size_t>(fail));}
 fail_at=0;sent.clear();sc.sc_ic.ic_bss=nullptr;assert(mt7921_mcu_set_associated_bss(&sc,1)==EINVAL);assert(sent.empty());
 sc.sc_ic.ic_bss=&n;n.ni_chan=nullptr;assert(mt7921_mcu_set_associated_bss(&sc,1)==EINVAL);assert(sent.empty());
 n.ni_chan=IEEE80211_CHAN_ANYC;assert(mt7921_mcu_set_associated_bss(&sc,1)==EINVAL);assert(sent.empty());
 // Current association records carry negotiated HT/VHT bandwidth instead
 // of rejecting every non-20-MHz channel. Validate their actual wire fields.
 n.ni_chan=&c;c.ic_freq=5180;n.ni_flags=IEEE80211_NODE_HT|IEEE80211_NODE_VHT|IEEE80211_NODE_QOS;
 sc.sc_bss_bw=2;sc.sc_bss_center=42;
 assert(!mt7921_mcu_set_associated_bss(&sc,1));assert(sent.size()==2);
 assert(sent[0][29]==0x31&&sent[0][40]==1);
 std::vector<uint8_t> wide={3,0,0,0,2,0,16,0,36,42,0,2,2,3,1,4,1,1,0,0};assert(sent[1]==wide);
 sent.clear();c.ic_freq=5220;assert(!mt7921_mcu_set_associated_bss(&sc,1));assert(sent[1][8]==44&&sent[1][16]==3);
 sent.clear();c.ic_freq=2437;assert(!mt7921_mcu_set_associated_bss(&sc,1));assert(sent[0][29]==0x0e);
 sent.clear();sc.sc_knobs=MWX_KNOB_NO_QBSS;assert(!mt7921_mcu_set_associated_bss(&sc,1));assert(sent[0].size()==36);
 sent.clear();sc.sc_ic.ic_opmode=2;assert(mt7921_mcu_set_associated_bss(&sc,1)==0);assert(sent.empty());
 // Main's HE BSS update must coexist with legacy/VHT associations and clear
 // the old color when the next AP has no HE. Firmware payload is tested by
 // the complete driver build; this test checks constructor dispatch/state.
 sc.sc_ic.ic_opmode=1;sc.sc_knobs=0;sc.sc_ic.ic_flags=IEEE80211_F_HEON;
 n.ni_flags|=IEEE80211_NODE_HE;
 for(int freq:{2437,5180}){
  c.ic_freq=freq;sent.clear();he_updates.clear();sc.sc_bss_he=0;
  assert(!mt7921_mcu_set_associated_bss(&sc,1));
  assert(sent.size()==2&&he_updates==std::vector<int>{1}&&sc.sc_bss_he);
  assert(sent[0][29]==(freq<3000?0x4e:0xb1));
 }
 n.ni_flags&=~IEEE80211_NODE_HE;sent.clear();he_updates.clear();
 assert(!mt7921_mcu_set_associated_bss(&sc,1));assert(he_updates==std::vector<int>{0}&&!sc.sc_bss_he);
 n.ni_flags|=IEEE80211_NODE_HE;he_error=EIO;sent.clear();he_updates.clear();
 assert(!mt7921_mcu_set_associated_bss(&sc,1));assert(!sc.sc_bss_he&&he_updates==std::vector<int>{1});
 puts("PASS: real BSS constructor, golden wire packets on 7 channels, QBSS/HT/VHT/bandwidth, disassociation, firmware failures and null guards");
}
'''
p=base/'tests/association/bss-context-test.cpp';p.write_text(code)
subprocess.run(['clang++','-std=c++14','-Wall','-Wextra','-fsanitize=address,undefined',str(p),'-o',str(base/'tests/association/bss-context-test')],check=True)
subprocess.run([str(base/'tests/association/bss-context-test')],check=True)
