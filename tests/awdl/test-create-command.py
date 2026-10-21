#!/usr/bin/env python3
"""Exercise the extracted production manual-creation dispatch without a kernel."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
source = (root / "AirportMtkWlan/AirportMtkWlan.cpp").read_text()
start = source.index("IOReturn AirportMtkWlan::requestAwdlCreation()")
end = source.index("IO80211VirtualInterface *AirportMtkWlan::createVirtualInterface", start)
production = source[start:end]
stubs = r'''
#include <cassert>
#include <cstdio>
using IOReturn = unsigned int;
constexpr IOReturn kIOReturnSuccess=0, kIOReturnNotReady=1;
constexpr IOReturn kIOReturnUnsupported=2, kIOReturnBusy=3;
constexpr IOReturn initializationFailure=4;
constexpr int IEEE80211_S_RUN=4;
struct OSObject { virtual ~OSObject()=default; };
#define OSDynamicCast(type, object) dynamic_cast<type *>(object)
struct IC { int ic_state=IEEE80211_S_RUN; };
struct Hal { IC ic; IC *get80211Controller() { return &ic; } };
using Action=IOReturn (*)(OSObject *,void *,void *,void *,void *);
struct Gate {
    OSObject *owner; bool inside=false; unsigned calls=0;
    IOReturn runAction(Action action) {
        assert(!inside); inside=true; ++calls;
        auto status=action(owner,nullptr,nullptr,nullptr,nullptr);
        inside=false; return status;
    }
};
struct AirportMtkWlan:OSObject {
    Hal hal; Hal *fHalService=&hal;
    Gate gate{this}; Gate *_fCommandGate=&gate;
    bool inactive=false, awdlExperimental=true, awdlCreating=false, awdlStopping=false;
    bool created=false, fail=false; void *awdlInterface=nullptr;
    unsigned creations=0, retains=0, releases=0;
    IOReturn awdlCreateStatus=kIOReturnNotReady;
    bool isInactive() const { return inactive; }
    void retain() { ++retains; }
    void release() { ++releases; }
    void setProperty(const char *,const char *) {}
    void recordAwdlCreation(const char *,IOReturn value) { awdlCreateStatus=value; }
    bool createAwdlInterface() {
        assert(gate.inside); // Allocation must occur under the controller gate.
        if(created) return true;
        ++creations;
        if(fail) { awdlCreateStatus=initializationFailure; return false; }
        awdlInterface=this; return created=true;
    }
    IOReturn requestAwdlCreation();
    static IOReturn createAwdlGated(OSObject *,void *,void *,void *,void *);
};
'''
tests = r'''
int main() {
    AirportMtkWlan c;
    c.inactive=true;
    assert(c.requestAwdlCreation()==kIOReturnNotReady);
    assert(c.gate.calls==0 && c.retains==0);
    c.inactive=false; c._fCommandGate=nullptr;
    assert(c.requestAwdlCreation()==kIOReturnNotReady);
    c._fCommandGate=&c.gate;
    c.awdlExperimental=false;
    assert(c.requestAwdlCreation()==kIOReturnUnsupported);
    c.awdlExperimental=true; c.awdlCreating=true;
    assert(c.requestAwdlCreation()==kIOReturnBusy);
    c.awdlCreating=false; c.awdlStopping=true;
    assert(c.requestAwdlCreation()==kIOReturnBusy);
    c.awdlStopping=false; c.fHalService=nullptr;
    assert(c.requestAwdlCreation()==kIOReturnNotReady);
    c.fHalService=&c.hal;
    for(int state=0;state<IEEE80211_S_RUN;++state) {
        c.hal.ic.ic_state=state;
        assert(c.requestAwdlCreation()==kIOReturnNotReady);
        assert(c.hal.ic.ic_state==state); // A rejected request cannot reconnect/reset Wi-Fi.
    }
    assert(c.creations==0);
    c.hal.ic.ic_state=IEEE80211_S_RUN; c.fail=true;
    assert(c.requestAwdlCreation()==initializationFailure);
    assert(c.creations==1 && !c.created);
    c.fail=false;
    assert(c.requestAwdlCreation()==kIOReturnSuccess);
    assert(c.requestAwdlCreation()==kIOReturnSuccess);
    c.hal.ic.ic_state=0; assert(c.requestAwdlCreation()==kIOReturnSuccess);
    assert(c.creations==2); // Success can be requested again without a duplicate allocation.
    assert(c.retains==c.releases && !c.gate.inside);
    OSObject other;
    assert(AirportMtkWlan::createAwdlGated(&other,nullptr,nullptr,nullptr,nullptr)==kIOReturnNotReady);
    puts("PASS manual AWDL: gated dispatch, disabled/busy/offline rejection, failure propagation, retry/idempotency, balanced lifetime.");
}
'''
with tempfile.TemporaryDirectory(prefix="mtk-awdl-command-") as temp:
    path = Path(temp) / "test.cpp"
    binary = Path(temp) / "test"
    path.write_text(stubs + production + tests)
    subprocess.run(["clang++", "-std=c++14", "-Wall", "-Wextra",
                    "-fsanitize=address,undefined", str(path), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True, timeout=10)
