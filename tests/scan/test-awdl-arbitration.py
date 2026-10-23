#!/usr/bin/env python3
"""Exercise production scan wrappers and stale firmware completion handling."""
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parents[2]
source = (Path(sys.argv[1]) if len(sys.argv)>1 else root/'SimpleMtkWlan/hal_mwx/MtkMwx.cpp').read_text()

def function(signature):
    start = source.index(signature)
    return source[start:source.index('\n}\n', start)+3]

code = r'''
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <initializer_list>
#define MWX_DEV_LOG(...) ((void)0)
#define DEVNAME(sc) "test"
#define MWX_FLAG_SCANNING 1
#define MWX_FLAG_BGSCAN 2
#define IFF_DEBUG 4
#define IFM_MODE(x) 0
#define IFM_AUTO 0
#define IEEE80211_MODE_AUTO 0
#define IEEE80211_S_SCAN 1
#define LINK_STATE_DOWN 0
#define MT76_HW_SCAN_DONE_MAX_CHANNEL_NUM 4
#define le32toh(x) (x)
const char *ieee80211_state_name[]={"INIT","SCAN","AUTH","ASSOC","RUN"};
struct ifnet {unsigned if_flags=0;const char*if_xname="test";};
struct ieee80211com {void*ic_softc=nullptr;unsigned ic_state=0;void*ic_bss=nullptr;ifnet ic_if;};
struct mwx_softc {ieee80211com sc_ic;unsigned sc_flags=0,sc_scan_seq_num=7;
 bool sc_awdl_scan_suspended=false;
 unsigned sc_scan_requests=0,sc_scan_done_count=0,sc_scan_last_ieee80211_nodes=0;
 int sc_scan_to=0,sc_scan_task=0;};
struct mt76_connac_hw_scan_done {uint8_t seq_num;unsigned beacon_probe_num[4],mdrdy_count[4];};
struct mbuf {mt76_connac_hw_scan_done event{};size_t len=sizeof(event);};
#define mtod(m,t) reinterpret_cast<t>(&(m)->event)
size_t mbuf_len(mbuf*m){return m->len;}
unsigned cancels=0,tasks=0,watchdogs=0;int systq=0;bool defer=false;
int mt7921_mcu_hw_scan(mwx_softc*s,int){s->sc_awdl_scan_suspended=defer;if(!defer)s->sc_flags|=MWX_FLAG_SCANNING;return 0;}
int mt7921_mcu_hw_scan_cancel(mwx_softc*s){++cancels;s->sc_flags=0;return 0;}
void timeout_add_sec(int*,int){++watchdogs;}void timeout_del(int*){}
void task_add(int,int*){++tasks;}
void ieee80211_setmode(ieee80211com*,int){}
void ieee80211_set_link_state(ieee80211com*,int){}
void ieee80211_node_cleanup(ieee80211com*,void*){}
int mwx_count_nodes(ieee80211com*){return 3;}
'''
for signature in ['int\nmwx_scan(', 'int\nmwx_bgscan(',
                  'void\nmt7921_mcu_scan_event(']:
    code += function(signature)
code += r'''
int main(){
 mwx_softc sc;sc.sc_ic.ic_softc=&sc;defer=true;
 for(unsigned i=0;i<100;++i){assert(!mwx_scan(&sc));assert(!mwx_bgscan(&sc.sc_ic));}
 assert(sc.sc_awdl_scan_suspended&&!sc.sc_flags&&!sc.sc_scan_requests&&!watchdogs&&!cancels);
 // Canceled/stale events cannot end/restart a scan while AWDL is active.
 mbuf event;event.event.seq_num=7;
 mt7921_mcu_scan_event(&sc,&event);assert(!sc.sc_scan_done_count&&!tasks&&!cancels);
 defer=false;assert(!mwx_scan(&sc));assert(sc.sc_scan_requests==1&&watchdogs==1);
 assert(sc.sc_flags&MWX_FLAG_SCANNING);
 event.event.seq_num=6;mt7921_mcu_scan_event(&sc,&event);
 assert(!sc.sc_scan_done_count&&!tasks&&!cancels&&(sc.sc_flags&MWX_FLAG_SCANNING));
 event.event.seq_num=7;
 for(size_t n=0;n<sizeof(event.event);++n){event.len=n;mt7921_mcu_scan_event(&sc,&event);}
 assert(!sc.sc_scan_done_count&&!tasks&&!cancels);
 event.len=sizeof(event.event);mt7921_mcu_scan_event(&sc,&event);
 assert(sc.sc_scan_done_count==1&&tasks==1&&cancels==1&&!sc.sc_flags);
 mt7921_mcu_scan_event(&sc,&event);assert(sc.sc_scan_done_count==1&&tasks==1);
 puts("PASS scan arbitration: suspended foreground/background wrappers, resume, short/stale/duplicate firmware completion and active sequence completion.");
}
'''
with tempfile.TemporaryDirectory(prefix='mtk-scan-awdl-') as directory:
    path = Path(directory)
    (path/'test.cpp').write_text(code)
    subprocess.run(['clang++','-std=c++14','-fsanitize=address,undefined',
                    str(path/'test.cpp'),'-o',str(path/'test')],check=True)
    subprocess.run([str(path/'test')],check=True)
