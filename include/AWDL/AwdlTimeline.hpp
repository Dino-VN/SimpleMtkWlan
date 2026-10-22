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
constexpr uint32_t rocLeadUs=25000;
// ROC carries its channel configuration. Plan ahead without waiting for a
// BSS/RLM command at each edge, and keep one grant for adjacent equal channels.
struct RadioPlan { Window window; uint64_t requestAt; uint32_t durationMs; };
inline bool planRadio(const State &s,uint64_t now,RadioPlan &out) {
    Window target={};
    if(!currentWindow(s,now,target)) return false;
    if(!target.channel || now-target.start>8000) {
        for(unsigned i=0;i<s.sequence.count;++i) {
            if(!currentWindow(s,target.end,target)) return false;
            if(target.channel) break;
        }
    }
    if(!target.channel) return false;
    uint64_t at=target.start>rocLeadUs ? target.start-rocLeadUs : 0;
    if(at<now) at=now;
    uint64_t end=target.end;
    for(unsigned i=1;i<s.sequence.count;++i) {
        Window next={};
        if(!currentWindow(s,end,next) || next.channel!=target.channel) break;
        end=next.end;
        if(end-at>=uint64_t(maxRocMs)*1000) break;
    }
    uint64_t duration=(end-at+4000+999)/1000;
    if(duration>maxRocMs) duration=maxRocMs;
    out={target,at,static_cast<uint32_t>(duration)}; return true;
}
inline bool grantCoversWindow(const Window &w,const Reservation &grant,uint64_t now) {
    uint64_t at=now>w.start ? now : w.start;
    uint64_t end=grant.deadline<w.end ? grant.deadline : w.end;
    return w.channel && grant.canTransmit(w.channel,at) && end>at &&
        end-at+10*1024>=unsigned(w.presence)*awUs;
}
struct Timeline {
    Window active={};
    bool open=false, emitted=false;
    uint64_t radioEnd=0;
    uint8_t role=1, token=0;
    uint64_t grantObservedAt=0;
    uint64_t lastStart=0, lastWindowStart=0, starts=0, ends=0, late=0, shortGrants=0;
    uint16_t lastCounter=0;
    uint8_t sync[6]={}, root[6]={};
    uint8_t lastSync[6]={}, lastRoot[6]={};
    uint8_t lastPresence=0;
    // Report an actual grant near the EAW edge. A firmware grant may be
    // shorter than the requested dwell: track its real end instead of hiding
    // the whole AW or promising radio availability until the scheduled end.
    bool begin(const Window &w,const Reservation &grant,uint64_t now,
               const uint8_t *parent,const uint8_t *master,uint8_t nativeRole=1) {
        if(open || !w.channel || now<w.start || now>=w.end || now-w.start>8000 ||
           !grant.canTransmit(w.channel,now) || !grant.grantObservedAt ||
           grant.grantObservedAt>now) { ++late; return false; }
        uint64_t end=grant.deadline<w.end ? grant.deadline : w.end;
        // Native sanityCheckAWEnd allows +/-10 TU, not an arbitrary partial
        // dwell. Never announce a 32ms grant as a complete 64TU native AW.
        if(end-now+10*1024<unsigned(w.presence)*awUs) { ++shortGrants; return false; }
        // RX clock corrections can move an edge by a fraction of a TU.
        // Identify the last notified window by counter/presence/master too;
        // its timestamp alone must not permit a second start for that AW.
        uint64_t edgeDelta=w.start>=lastWindowStart ? w.start-lastWindowStart : lastWindowStart-w.start;
        if(emitted && lastCounter==w.counter && lastPresence==w.presence &&
           !memcmp(lastSync,parent,6) && !memcmp(lastRoot,master,6) &&
           edgeDelta<unsigned(w.presence)*awUs) return false;
        active=w; open=true; emitted=true; lastWindowStart=w.start;
        radioEnd=end;
        role=nativeRole; token=grant.token; grantObservedAt=grant.grantObservedAt;
        lastStart=now; lastCounter=w.counter; lastPresence=w.presence; ++starts;
        memcpy(sync,parent,6); memcpy(root,master,6);
        memcpy(lastSync,parent,6); memcpy(lastRoot,master,6); return true;
    }
    bool due(uint64_t now) const { return open && now>=radioEnd; }
    void close() { if(open) { open=false; ++ends; } }
    void reset() { open=false; emitted=false; lastWindowStart=radioEnd=0; }
};
}
#endif
