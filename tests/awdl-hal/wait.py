"""Exercise the real HAL sleep/wakeup routing without macOS kernel scheduling."""
from pathlib import Path
import subprocess,tempfile
root=Path(__file__).resolve().parents[2]
s=(root/'SimpleMtkWlan/hal_mwx/MtkMwx.cpp').read_text()
def fn(signature):
 a=s.index(signature);return s[a:s.index('\n}\n',a)+3]
code=r'''
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cerrno>
#include <algorithm>
using IOReturn=int;using AbsoluteTime=uint64_t;
#define MIN(a,b) std::min<uint64_t>(a,b)
#define kNanosecondScale 1
#define THREAD_UNINT 0
#define THREAD_AWAKENED 0
int fallback_sleeps=0,ordinary_wakes=0;
struct MtkHalService{int tsleep_nsec(void*,int,const char*,uint64_t){++fallback_sleeps;return 17;}};
void clock_interval_to_deadline(uint32_t n,int,uint64_t*p){*p=n;}
struct WorkLoop{bool gated=false;bool inGate(){return gated;}};
struct CommandGate{int sleeps=0,wakes=0,result=0;uint64_t last=0;
 int commandSleep(void*,uint64_t n,int){++sleeps;last=n;return result;}
 void commandWakeup(void*,bool one){assert(!one);++wakes;}};
struct MtkMwx:MtkHalService{WorkLoop*loop;CommandGate*gate;
 WorkLoop*getMainWorkLoop(){return loop;}CommandGate*getMainCommandGate(){return gate;}
 void wakeupOn(void*){++ordinary_wakes;}
 int mwxSleepNsec(void*,int,const char*,uint64_t);void mwxWakeup(void*);
};
'''+fn('int\nMtkMwx::mwxSleepNsec(')+'\n'+fn('void\nMtkMwx::mwxWakeup(')+r'''
int main(){WorkLoop w;CommandGate g;MtkMwx h;h.loop=&w;h.gate=&g;
 assert(h.mwxSleepNsec(&h,0,"test",10000000)==17&&fallback_sleeps==1&&g.sleeps==0);
 w.gated=true;assert(h.mwxSleepNsec(&h,0,"test",10000000)==0&&g.sleeps==1&&g.last==10000000);
 g.result=1;assert(h.mwxSleepNsec(&h,0,"test",10000000)==EWOULDBLOCK);
 assert(h.mwxSleepNsec(&h,0,"test",UINT64_MAX)==EWOULDBLOCK&&g.last==UINT32_MAX);
 h.mwxWakeup(&h);assert(ordinary_wakes==1&&g.wakes==1);
 h.gate=nullptr;h.mwxWakeup(&h);assert(ordinary_wakes==2&&g.wakes==1);
 puts("PASS actual HAL wait routing: gate release for native MCU waits, ordinary mutex waits, deadline clamp, both wake mechanisms. Mocks do not prove kernel scheduling.");}
'''
with tempfile.TemporaryDirectory(prefix='mtk-awdl-wait-') as d:
 p=Path(d)/'test.cpp';p.write_text(code)
 subprocess.run(['clang++','-std=c++14','-Wall','-Wextra','-fsanitize=address,undefined',str(p),'-o',str(Path(d)/'test')],check=True)
 subprocess.run([str(Path(d)/'test')],check=True)
