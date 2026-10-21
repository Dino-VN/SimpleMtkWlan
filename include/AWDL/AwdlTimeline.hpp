// SPDX-License-Identifier: GPL-2.0-or-later
#ifndef MTK_AWDL_TIMELINE_HPP
#define MTK_AWDL_TIMELINE_HPP
#include <AWDL/AwdlProtocol.hpp>
namespace mtkawdl {
// Host observations use monotonic microseconds; AW counters are peer schedule
// coordinates and must never be used as a timestamp clock.
struct Window {
    uint64_t start, end;
    uint16_t counter;
    uint8_t channel, presence;
};
inline bool currentWindow(const State &s,uint64_t now,Window &out) {
    if(!validPresence(s.presence) || !validSequence(s.sequence)) return false;
    uint32_t length=unsigned(s.presence)*awUs, remaining=s.untilNext(now);
    if(!remaining || remaining>length || now<length-remaining) return false;
    out={now-(length-remaining),now+remaining,
         uint16_t(s.counter(now)-s.counter(now)%s.presence),s.channel(now),s.presence};
    return true;
}
struct Timeline {
    Window active={};
    bool open=false, emitted=false;
    uint64_t lastStart=0, lastWindowStart=0, starts=0, ends=0, late=0;
    uint16_t lastCounter=0;
    uint8_t sync[6]={}, root[6]={};
    // Open only at an observed EAW boundary with a real grant covering its
    // remainder. Eight ms bound host dispatch lateness inside native's 10ms
    // tolerance; timestamps still report observations, not a fabricated edge.
    bool begin(const Window &w,const Reservation &grant,uint64_t now,
               const uint8_t *parent,const uint8_t *master) {
        if(open || !w.channel || now<w.start || now>=w.end || now-w.start>8000 ||
           !grant.canTransmit(w.channel,now) || grant.deadline+2000<w.end ||
           grant.grantObservedAt>now) { ++late; return false; }
        if(emitted && lastWindowStart==w.start) return false;
        active=w; open=true; emitted=true; lastWindowStart=w.start;
        // Record observed start, never fabricate a grant at scheduled start.
        lastStart=now; lastCounter=w.counter; ++starts;
        memcpy(sync,parent,6); memcpy(root,master,6); return true;
    }
    bool due(uint64_t now) const { return open && now>=active.end; }
    void close() { if(open) { open=false; ++ends; } }
    void reset() { open=false; emitted=false; lastWindowStart=0; }
};
}
#endif
