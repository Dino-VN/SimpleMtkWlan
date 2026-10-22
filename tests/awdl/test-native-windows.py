#!/usr/bin/env python3
"""Run production AW events/scheduler against real-grant and callback scenarios."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
source = (root / 'AirportMtkWlan/AirportMtkAwdlInterface.cpp').read_text()
def function(signature):
    start = source.index(signature)
    return source[start:source.index('\n}\n', start) + 3]
code = r'''
#include <cassert>
#include <cstdint>
#include <cstring>
#include <cstdio>
#include <functional>
#include <vector>
#include <AWDL/AwdlTimeline.hpp>
using IOReturn=unsigned;
constexpr unsigned APPLE80211_VERSION=1,kIOReturnSuccess=0,kIOReturnNotReady=1,kIOReturnNoMemory=2,kIOReturnBadArgument=3,kIOReturnUnsupported=4,
 APPLE80211_C_FLAG_20MHZ=1,APPLE80211_C_FLAG_2GHZ=8,APPLE80211_C_FLAG_5GHZ=16,
 APPLE80211_M_AWDL_AVAILABILITY_WINDOW_START=41,
 APPLE80211_M_AWDL_AVAILABILITY_WINDOW_EXTENSIONS_END=43;
uint64_t clockUS=1000000;uint64_t awdlNow(){return clockUS;}
void bzero(void*p,size_t n){memset(p,0,n);}
struct apple80211_channel{uint32_t version,channel,flags;};
struct apple80211_awdl_sync_state{uint32_t version,state;uint8_t master[6],reserved[2];
 uint32_t flags;uint8_t mode_flags,reserved2[3];};
struct awdl_peer_advert_add{uint8_t bytes[44];};
struct Timer{unsigned us=0;void setTimeoutMS(unsigned n){us=n*1000;}
 void setTimeoutUS(unsigned n){us=n;}void cancelTimeout(){us=0;}};
struct Packet{std::vector<uint8_t> bytes;};using mbuf_t=Packet*;
void mbuf_freem(mbuf_t m){delete m;}void*mbuf_data(mbuf_t m){return m->bytes.data();}
struct Hal{
 bool on=true;mtkawdl::Reservation grant{};unsigned reserves=0,aborts=0,transmits=0;
 uint8_t requested=0,preparedChannel=0;unsigned prepares=0;
 uint32_t duration=0;std::function<void()> onReserve,onPrepare;
 IOReturn awdlPrepareChannel(unsigned c){++prepares;preparedChannel=c;if(onPrepare)onPrepare();return 0;}bool awdlIsEnabled(){return on;}bool awdlChannelAllowed(unsigned c){return c==6||c==44;}
 bool awdlGrantSnapshot(mtkawdl::Reservation &out){out=grant;return on;}
 bool awdlCanTransmit(unsigned c){return grant.canTransmit(c,clockUS);}
 void awdlAbort(){++aborts;grant.cancel();}
 IOReturn awdlReserve(unsigned c,unsigned ms){++reserves;requested=c;duration=ms;
  if(onReserve)onReserve();return 0;}
 IOReturn awdlPeer(const uint8_t*,bool){return 0;}
 IOReturn awdlTransmit(mbuf_t m,unsigned){++transmits;delete m;return 0;}
 void give(uint8_t token,uint8_t c,uint32_t ms){grant.request(token,c,clockUS);
  assert(grant.grant(token,c,ms,clockUS));}
};
struct Event{unsigned id;std::vector<uint8_t> bytes;};
struct AirportMtkAwdlInterface{
 Hal radio;Hal*hal=&radio;Timer t;Timer*timer=&t;
 bool enabled=true,stopping=false,trafficActive=false,trafficPeerInstalled=false;
 uint8_t trafficPeer[6]{},installedTrafficPeer[6]{};
 mtkawdl::DataPeers dataPeers;mtkawdl::State state;mtkawdl::Timeline awTimeline;mtkawdl::Window requestedWindow{};
 apple80211_awdl_sync_state syncState{};
 struct NativePeerSample{mtkawdl::Advertisement advertisement;uint8_t peer[6];uint64_t received;bool valid;};
 NativePeerSample nativePeerSamples[16]{};uint64_t advertisersRequests=0;
 uint8_t requestedChannel=0,grantedChannel=0;uint64_t requestDeadline=0;
 unsigned reserveDuration=0;IOReturn reserveStatus=0,actionStatus=0,miStatus=0;
 uint64_t dataTxSubmitted=0,dataTxFailed=0,dataTxExpired=0;IOReturn dataTxStatus=0;
 uint64_t serviceTicks=0,reserveAttempts=0,grantObservations=0,awStartNotifications=0,
 nextAction=0,actionSubmitted=0,actionFailed=0,miStart=0,miSubmitted=0,miFailed=0;
 struct{unsigned mode=3;}afMode;struct{unsigned synchronization_frame_period=440;}syncParams;
 uint8_t syncTemplate[2048]{},miTemplate[2048]{};size_t templateLength=0,miTemplateLength=0;
 uint16_t miCounter=0;bool miCounterValid=false;
 mbuf_t queue[64]{};uint64_t queueTime[64]{};unsigned queueCount=0,queueHead=0;
 std::vector<Event> events;std::function<void()> onStart,onEnd;
 void setProperty(const char*,uint64_t,unsigned){}void setProperty(const char*,bool){}
 void setProperty(const char*,const void*,unsigned){}void setProperty(const char*,const char*){}
 void publishScheduler(uint64_t){}
 mbuf_t makeFrame(const uint8_t*f,size_t n){return new Packet{{f,f+n}};}
 void postMessage(unsigned id,void*p,size_t n,bool){
  const auto*b=static_cast<const uint8_t*>(p);events.push_back({id,{b,b+n}});
  if(id==41&&onStart)onStart();if(id==43&&onEnd)onEnd();
 }
 void notifyAvailabilityWindowStart(uint8_t,uint64_t);
 void notifyAvailabilityWindowEnd(uint64_t);void serviceInGate();
 IOReturn setSync(bool value){enabled=value;return 0;}
 IOReturn setAWDL_SYNC_STATE(apple80211_awdl_sync_state*);
 IOReturn setAWDL_AWDL_ADVERTISERS(awdl_peer_advert_add*);
};
'''
for sig in ['void AirportMtkAwdlInterface::notifyAvailabilityWindowStart(',
            'void AirportMtkAwdlInterface::notifyAvailabilityWindowEnd(',
            'void AirportMtkAwdlInterface::serviceInGate(',
            'IOReturn AirportMtkAwdlInterface::setAWDL_SYNC_STATE(',
            'IOReturn AirportMtkAwdlInterface::setAWDL_AWDL_ADVERTISERS(']:
    code += function(sig)
code += r'''
const uint8_t local[]={2,1,2,3,4,5},peer[]={2,1,2,3,4,6};
void init(AirportMtkAwdlInterface&d){clockUS=1000000;d.state.init(local,clockUS);
 d.radio.give(1,6,70);}
int main(){
 // Wire offsets are checked independently, including BE timestamp rollover.
 AirportMtkAwdlInterface d;init(d);d.state.baseCounter=65532;
 clockUS+=1000;d.serviceInGate();assert(d.events.size()==1&&d.events[0].id==41);
 const auto&b=d.events[0].bytes;assert(b.size()==36);
 assert(mtkawdl::le32(b.data())==65532&&mtkawdl::le32(b.data()+4)==1);
 assert(!memcmp(b.data()+8,local,6)&&!memcmp(b.data()+14,local,6));
 assert(mtkawdl::be32(b.data()+20)==clockUS&&mtkawdl::le32(b.data()+28)==6);
 uint64_t end=d.awTimeline.radioEnd;clockUS=end+25000;d.serviceInGate();
 assert(d.events.size()==2&&d.events[1].id==43&&d.events[1].bytes.size()==40);
 assert(mtkawdl::be32(d.events[1].bytes.data()+4)==end);
 for(size_t i=0;i<40;++i)if(i<4||i>=8)assert(d.events[1].bytes[i]==0);
 d.notifyAvailabilityWindowEnd(clockUS);assert(d.events.size()==2);
 // Same-channel next EAW still starts and counter wraps from 65532 to zero.
 clockUS=1000000+4*mtkawdl::awUs+1000;d.radio.give(2,6,70);d.serviceInGate();
 assert(d.events.size()==3&&mtkawdl::le32(d.events.back().bytes.data())==0);
 // Firmware reset closes exactly once before clearing local lifecycle state.
 d.radio.on=false;d.serviceInGate();assert(d.events.size()==4&&!d.enabled&&!d.awTimeline.open);
 d.serviceInGate();assert(d.events.size()==4);
 // Grant shorter by a few ms is within native tolerance; 32ms isn't a 64TU AW.
 AirportMtkAwdlInterface shortD;init(shortD);shortD.radio.give(2,6,32);
 shortD.serviceInGate();assert(shortD.events.empty()&&shortD.awTimeline.shortGrants==1);
 shortD.radio.give(3,6,60);shortD.serviceInGate();assert(shortD.events.size()==1);
 clockUS=1060000;shortD.serviceInGate();assert(shortD.events.size()==2);
 // Regaining RF in the same counter after a tiny RX epoch correction cannot duplicate AW.
 shortD.state.epoch+=500;clockUS=1001000;shortD.radio.give(4,6,70);
 shortD.serviceInGate();assert(shortD.events.size()==2);
 // Revoke an open grant: pair end; never emit a second start for that EAW.
 AirportMtkAwdlInterface revoked;init(revoked);revoked.serviceInGate();
 revoked.radio.grant.cancel();clockUS+=2000;revoked.serviceInGate();
 assert(revoked.events.size()==2&&!revoked.awTimeline.open);
 revoked.radio.give(2,6,70);revoked.serviceInGate();assert(revoked.events.size()==2);
 // Native callback changes master with same channel. Reject stale RF after dispatch.
 AirportMtkAwdlInterface callback;init(callback);callback.afMode.mode=0;
 callback.onStart=[&]{memcpy(callback.state.sync,peer,6);};callback.serviceInGate();
 assert(callback.events.size()==2&&callback.radio.transmits==0);
 // Reentrant end must not dispatch duplicate ends.
 callback.onEnd=[&]{callback.notifyAvailabilityWindowEnd(clockUS);};
 callback.notifyAvailabilityWindowEnd(clockUS);assert(callback.events.size()==2);
 // Channel changes use ROC directly; no synchronous RLM wait at the edge.
 AirportMtkAwdlInterface prepare;init(prepare);prepare.radio.grant.cancel();
 prepare.state.sequence.channels[1]=prepare.state.ownSequence.channels[1]=44;
 prepare.radio.onPrepare=[&]{clockUS+=20000;};
 clockUS+=20000;prepare.serviceInGate();assert(prepare.radio.reserves==0&&prepare.radio.prepares==0);
 prepare.radio.onPrepare=nullptr;
 clockUS=1000000+4*mtkawdl::awUs-7000;prepare.serviceInGate();
 assert(prepare.radio.reserves==1&&prepare.radio.requested==44&&prepare.radio.duration>70);
 assert(prepare.events.empty());
 // Keep a pending future ROC while the current slot has no radio channel.
 AirportMtkAwdlInterface idle;init(idle);idle.radio.grant.cancel();
 idle.state.sequence.channels[0]=idle.state.ownSequence.channels[0]=0;
 idle.state.sequence.channels[1]=idle.state.ownSequence.channels[1]=44;
 clockUS=1000000+4*mtkawdl::awUs-7000;
 idle.radio.onReserve=[&]{idle.radio.grant.request(5,44,clockUS);};
 idle.serviceInGate();assert(idle.radio.reserves==1&&idle.requestedChannel==44);
 for(unsigned i=0;i<3;++i){clockUS+=1000;idle.serviceInGate();}
 assert(idle.radio.aborts==0&&idle.radio.reserves==1&&idle.radio.grant.pending);
 assert(idle.radio.grant.grant(5,44,70,clockUS));
 clockUS=1000000+4*mtkawdl::awUs;idle.serviceInGate();
 assert(idle.events.size()==1&&idle.events[0].id==41);
 // Run a real asynchronous reserve/grant cycle on consecutive boundaries.
 AirportMtkAwdlInterface continuous;init(continuous);
 continuous.state.sequence.channels[1]=continuous.state.ownSequence.channels[1]=44;
 uint8_t nextToken=10;uint64_t grantAt=0;
 continuous.radio.onReserve=[&]{continuous.radio.grant.request(++nextToken,continuous.radio.requested,clockUS);grantAt=clockUS+3000;};
 for(unsigned i=0;i<210;++i){
  if(continuous.radio.grant.pending&&clockUS>=grantAt)
   assert(continuous.radio.grant.grant(nextToken,continuous.radio.requested,continuous.radio.duration,clockUS));
  continuous.serviceInGate();clockUS+=1000;
 }
 assert(continuous.awTimeline.starts==4&&continuous.awTimeline.ends==3);
 assert(continuous.radio.reserves==2);
 // Long runs must emit every scheduled non-idle EAW, not just count pairs.
 // Simulate MCU grant latency, timer jitter, counter wrap and channel changes.
 for(unsigned latency:{3000,8000}) {
  AirportMtkAwdlInterface run;init(run);run.state.baseCounter=65532;
  for(unsigned i=0;i<run.state.sequence.count;++i)
   run.state.sequence.channels[i]=run.state.ownSequence.channels[i]=(i%3==1?44:6);
  uint8_t token=1;uint64_t due=0;
  run.radio.onReserve=[&]{run.radio.grant.request(++token,run.radio.requested,clockUS);due=clockUS+latency;};
  for(unsigned i=0;i<2700;++i){
   if(run.radio.grant.pending&&clockUS>=due)
    assert(run.radio.grant.grant(token,run.radio.requested,run.radio.duration,clockUS));
   run.serviceInGate();clockUS+=i%2 ? 1250 : 750;
  }
  assert(run.awTimeline.starts==42&&run.awTimeline.ends==41);
  unsigned starts=0,ends=0;uint32_t startTime=0;uint16_t previous=65528;
  for(const auto&event:run.events){
   if(event.id==41){assert(starts==ends);++starts;
    uint16_t counter=mtkawdl::le32(event.bytes.data());assert(counter==uint16_t(previous+4));previous=counter;
    startTime=mtkawdl::be32(event.bytes.data()+20);
   }else{assert(starts==ends+1);++ends;
    uint32_t duration=mtkawdl::be32(event.bytes.data()+4)-startTime;
    assert(duration/1024>=54&&duration/1024<=74);
   }
  }
  assert(run.radio.prepares==0&&run.radio.reserves<42);
 }
 // Long equal-channel runs retain grants at EAW boundaries and renew before
 // the firmware deadline; 1-second cap cannot produce a partial native AW.
 AirportMtkAwdlInterface same;init(same);uint8_t sameToken=1;uint64_t sameDue=0;
 same.radio.onReserve=[&]{same.radio.grant.request(++sameToken,6,clockUS);sameDue=clockUS+3000;};
 for(unsigned i=0;i<2200;++i){
  if(same.radio.grant.pending&&clockUS>=sameDue)
   assert(same.radio.grant.grant(sameToken,6,same.radio.duration,clockUS));
  same.serviceInGate();clockUS+=1000;
 }
 assert(same.awTimeline.starts==34&&same.awTimeline.ends==33&&same.radio.reserves==3);
 // Idle slots can request ahead. A real 20ms grant delay is covered by lead
 // time and must not cause repeated abort/replacement of a future grant.
 AirportMtkAwdlInterface lead;init(lead);lead.radio.grant.cancel();
 for(unsigned i=0;i<lead.state.sequence.count;++i)
  lead.state.sequence.channels[i]=lead.state.ownSequence.channels[i]=(i%2?44:0);
 uint8_t leadToken=1;uint64_t leadDue=0;
 lead.radio.onReserve=[&]{lead.radio.grant.request(++leadToken,44,clockUS);leadDue=clockUS+20000;};
 for(unsigned i=0;i<520;++i){
  if(lead.radio.grant.pending&&clockUS>=leadDue)
   assert(lead.radio.grant.grant(leadToken,44,lead.radio.duration,clockUS));
  lead.serviceInGate();clockUS+=1000;
 }
 assert(lead.awTimeline.starts==4&&lead.awTimeline.ends==3&&lead.radio.reserves==4);
 // A delayed grant response outlives the target EAW. Respect its actual
 // pending-response timeout rather than aborting it once every EAW.
 AirportMtkAwdlInterface slow;init(slow);slow.radio.grant.cancel();
 for(unsigned i=0;i<slow.state.sequence.count;++i)
  slow.state.sequence.channels[i]=slow.state.ownSequence.channels[i]=(i%2?44:0);
 slow.radio.onReserve=[&]{slow.radio.grant.request(7,44,clockUS);};
 clockUS=1000000+4*mtkawdl::awUs-24000;slow.serviceInGate();assert(slow.radio.reserves==1);
 clockUS=slow.requestedWindow.end+2000;slow.serviceInGate();
 assert(slow.radio.reserves==1&&slow.radio.aborts==0&&slow.radio.grant.pending);
 // Tahoe programs mode 1 with a remote synchronization MAC. Accept it, and
 // preserve a pending grant when native refreshes the identical role.
 AirportMtkAwdlInterface mode;init(mode);mode.state.nativeElectionManaged=true;
 apple80211_awdl_sync_state control{};control.version=1;control.state=1;
 memcpy(control.master,peer,6);control.mode_flags=0x20;
 assert(mode.setAWDL_SYNC_STATE(&control)==0);
 mode.radio.grant.request(7,6,clockUS);unsigned aborts=mode.radio.aborts;
 control.flags=65532;assert(mode.setAWDL_SYNC_STATE(&control)==0);
 assert(mode.radio.aborts==aborts&&mode.radio.grant.pending&&mode.syncState.flags==65532);
 // Repeating native advertisers must not compare the peer's different radio
 // sequence against ours and repeatedly tear down an otherwise valid grant.
 AirportMtkAwdlInterface selected;init(selected);selected.state.nativeElectionManaged=true;
 auto &sample=selected.nativePeerSamples[0];sample.valid=true;sample.received=clockUS;
 memcpy(sample.peer,peer,6);auto &ad=sample.advertisement;
 memcpy(ad.master,peer,6);memcpy(ad.sync,peer,6);ad.counter=4;ad.down=64;ad.period=16;
 ad.presence=4;ad.sequence=selected.state.ownSequence;ad.sequence.channels[0]=44;
 auto &cached=selected.state.peers[0];cached.used=true;cached.seen=clockUS;memcpy(cached.mac,peer,6);
 awdl_peer_advert_add advert{};mtkawdl::put16(advert.bytes,4);mtkawdl::put16(advert.bytes+2,64);
 mtkawdl::put16(advert.bytes+10,16);mtkawdl::put16(advert.bytes+12,16);advert.bytes[16]=4;
 mtkawdl::putBE32(advert.bytes+20,uint32_t(clockUS));
 memcpy(advert.bytes+32,peer,6);memcpy(advert.bytes+38,peer,6);
 assert(selected.setAWDL_AWDL_ADVERTISERS(&advert)==0);
 assert(selected.state.sequence.channels[0]==6&&selected.state.synchronized);
 selected.radio.grant.request(9,6,clockUS);aborts=selected.radio.aborts;
 assert(selected.setAWDL_AWDL_ADVERTISERS(&advert)==0);
 assert(selected.radio.aborts==aborts&&selected.radio.grant.pending);
 // MCU sleep replaces schedule while preserving the target channel: abort stale request.
 AirportMtkAwdlInterface changed;init(changed);changed.radio.grant.cancel();
 changed.radio.onReserve=[&]{changed.state.sequence.channels[4]=44;};changed.serviceInGate();
 assert(changed.radio.aborts==1&&changed.requestedChannel==0&&changed.events.empty());
 // No event from a pending/unmatched grant or a late boundary observation.
 AirportMtkAwdlInterface pending;init(pending);pending.radio.grant.request(3,6,clockUS);
 pending.serviceInGate();assert(pending.events.empty());
 pending.radio.give(3,6,70);clockUS+=9000;pending.serviceInGate();assert(pending.events.empty());
 // U32 host-clock wrap is carried in wire timestamps, independently of AW counter.
 AirportMtkAwdlInterface wrap;init(wrap);clockUS=(uint64_t(1)<<32)+1000000;
 wrap.state.init(local,clockUS);wrap.radio.give(8,6,70);wrap.serviceInGate();
 assert(mtkawdl::be32(wrap.events[0].bytes.data()+20)==1000000);
 clockUS=wrap.awTimeline.radioEnd;wrap.serviceInGate();
 assert(mtkawdl::be32(wrap.events[1].bytes.data()+4)==1065536);
 puts("PASS production AW start/end: ABI, matched grants, short dwell tolerance, delayed end, reset/revoke pairing, counter/clock wrap, duplicate suppression, reentrant callbacks and schedule revalidation/preparation.");
}
'''
with tempfile.TemporaryDirectory(prefix='mtk-native-windows-') as temp:
    cpp = Path(temp) / 'test.cpp'
    binary = Path(temp) / 'test'
    cpp.write_text(code)
    subprocess.run(['clang++','-std=c++14','-Wall','-Wextra','-Werror',
                    '-fsanitize=address,undefined','-I'+str(root/'include'),str(cpp),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)
