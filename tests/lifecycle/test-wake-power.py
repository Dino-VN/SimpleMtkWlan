#!/usr/bin/env python3
"""Execute production PM callbacks, async HAL task and bounded wake fallback."""
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parents[2]
baseline = Path(sys.argv[1]) if len(sys.argv) > 1 else root
hal = (baseline/'SimpleMtkWlan/hal_mwx/MtkMwx.cpp').read_text()
controller = (baseline/'AirportMtkWlan/AirportMtkWlan.cpp').read_text()

def function(source, signature):
    start = source.index(signature)
    return source[start:source.index('\n}\n', start)+3]

code = r'''
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <functional>
#include <map>
#include <string>
#define AIRPORT 1
#define IFF_UP 1
#define IFF_RUNNING 2
#define MWX_DEV_LOG(...) ((void)0)
#define XYLog(...) ((void)0)
#define IOLog(...) ((void)0)
#define OSSynchronizeIO() ((void)0)
#define OSDynamicCast(t,p) (p)
#define MSEC_TO_NSEC(n) ((n)*1000000ULL)
using IOReturn=int;using SInt32=int32_t;
const int kIOReturnSuccess=0,kIOReturnIOError=1,kIOReturnNotAttached=2,kIOReturnTimeout=3;
const unsigned kPowerStateOff=0,kPowerStateOn=1;
struct ifnet{unsigned if_flags=IFF_UP|IFF_RUNNING;};
struct mwx_softc{
 struct{ifnet ic_if;}sc_ic;bool sc_detaching=false;
 volatile SInt32 sc_power_req=0,sc_power_done=0;int sc_power_result=0;
 int sc_nswq=0,sc_reset_task=0,sc_reset_to=0;
};
unsigned starts=0,stops=0,reloads=0,canceled=0;int initError=0;
bool reloadSuccess=true;std::function<void()>onSleep;
void mwx_stop(ifnet*p){++stops;p->if_flags&=~IFF_RUNNING;}
int mwx_init(ifnet*p){++starts;if(!initError)p->if_flags|=IFF_RUNNING;return initError;}
void mwx_fullreset_task(mwx_softc*s){++reloads;if(reloadSuccess)s->sc_ic.ic_if.if_flags|=IFF_RUNNING;}
void task_del(int,int*){++canceled;}void timeout_del(int*){++canceled;}
class MtkMwx{public:mwx_softc*com;unsigned sleeps=0;
 IOReturn waitPowerTransition();
 void mwxSleepNsec(void*,int,const char*,uint64_t ns){assert(ns==10000000);++sleeps;if(onSleep)onSleep();}
};
class Policy {public:unsigned acks=0;std::function<void()>onAck;
 void acknowledgeSetPowerState(){++acks;if(onAck)onAck();}
};
class AirportMtkWlan {public:
 unsigned pmPowerState=1,power_state=1;void*bsdInterface=(void*)1;
 MtkMwx*fHalService;Policy*pmPolicyMaker;
 std::map<std::string,uint64_t>properties;unsigned enables=0,disables=0;
 void setProperty(const char*k,uint64_t v,int){properties[k]=v;}
 IOReturn enableAdapter(void*){++enables;auto*s=fHalService->com;
  if(!(s->sc_ic.ic_if.if_flags&IFF_UP)){s->sc_ic.ic_if.if_flags|=IFF_UP;++s->sc_power_req;}
  return 0;
 }
 void disableAdapter(void*){++disables;auto*s=fHalService->com;
  if(s->sc_ic.ic_if.if_flags&IFF_UP){s->sc_ic.ic_if.if_flags&=~IFF_UP;++s->sc_power_req;}
 }
 void setPowerStateOff();void setPowerStateOn();
};
'''
code += function(hal, 'void\nmwx_power_task(')
if 'IOReturn\nMtkMwx::waitPowerTransition(' in hal:
    code += function(hal, 'IOReturn\nMtkMwx::waitPowerTransition(')
else:
    code += 'IOReturn MtkMwx::waitPowerTransition(){return 0;}\n'
for signature in ('void AirportMtkWlan::setPowerStateOff()',
                  'void AirportMtkWlan::setPowerStateOn()'):
    code += function(controller, signature)
code += r'''
struct Fixture {
 mwx_softc sc;MtkMwx hal{&sc};Policy policy;AirportMtkWlan ctl;
 Fixture(){starts=stops=reloads=canceled=0;initError=0;reloadSuccess=true;
  ctl.fHalService=&hal;ctl.pmPolicyMaker=&policy;
  onSleep=[this]{mwx_power_task(&sc);};
 }
};
int main(){
 // Real PM callbacks must stop before sleep ACK, restart before wake ACK
 // and preserve Wi-Fi user's power preference across repeated cycles.
 for(unsigned cycle=0;cycle<100;cycle++){
  Fixture f;f.policy.onAck=[&]{assert(f.sc.sc_power_done==f.sc.sc_power_req);
   assert(bool(f.sc.sc_ic.ic_if.if_flags&IFF_RUNNING)==bool(f.ctl.pmPowerState));};
  f.ctl.setPowerStateOff();assert(f.policy.acks==1&&f.ctl.disables==1&&stops==1);
  assert(f.ctl.properties["MTKSleepStopStatus"]==0&&f.ctl.power_state==1);
  f.ctl.setPowerStateOn();assert(f.policy.acks==2&&f.ctl.enables==1&&starts==1&&!reloads);
  assert(f.ctl.properties["MTKWakeStartStatus"]==0&&f.sc.sc_ic.ic_if.if_flags==(IFF_UP|IFF_RUNNING));
  mwx_power_task(&f.sc);assert(stops==1&&starts==1); // duplicate task
 }
 // Failed normal wake gets one reload; a duplicate task cannot reload again.
 for(bool success:{false,true}){
  Fixture f;f.sc.sc_ic.ic_if.if_flags=0;f.sc.sc_power_done=f.sc.sc_power_req;
  initError=EIO;reloadSuccess=success;f.ctl.setPowerStateOn();
  assert(starts==1&&reloads==1&&canceled==2);
  assert(f.ctl.properties["MTKWakeStartStatus"]==unsigned(success?0:kIOReturnIOError));
  assert(bool(f.sc.sc_ic.ic_if.if_flags&IFF_UP)==success);
  mwx_power_task(&f.sc);assert(starts==1&&reloads==1);
 }
 // Wi-Fi deliberately off stays off at wake.
 {Fixture f;f.ctl.power_state=0;f.sc.sc_ic.ic_if.if_flags=0;
  f.ctl.setPowerStateOn();assert(!f.ctl.enables&&!starts&&!reloads&&f.policy.acks==1);}
 // A pending task cannot block PM forever and the timeout stays visible.
 {Fixture f;onSleep=[]{};f.ctl.setPowerStateOff();
  assert(f.hal.sleeps==400&&f.policy.acks==1);
  assert(f.ctl.properties["MTKSleepStopStatus"]==kIOReturnTimeout);}
 // Teardown prevents work or firmware reload; waiter reports detachment.
 {Fixture f;f.sc.sc_detaching=true;++f.sc.sc_power_req;
  mwx_power_task(&f.sc);assert(!starts&&!stops&&!reloads);
  assert(f.hal.waitPowerTransition()==kIOReturnNotAttached);}
 puts("PASS production sleep/wake PM: 100 cycles, completed-task ACK ordering, preference retention, one reload, duplicate isolation, failure reporting, timeout and detach.");
}
'''
with tempfile.TemporaryDirectory(prefix='mtk-wake-power-') as tmp:
    cpp = Path(tmp)/'test.cpp'
    cpp.write_text(code)
    exe = cpp.with_suffix('')
    subprocess.run(['clang++', '-std=c++14', '-include', 'cerrno',
                    '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                    str(cpp), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
