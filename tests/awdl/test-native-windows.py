#!/usr/bin/env python3
"""Run production AW events/scheduler against real-grant and callback scenarios."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[2]
source = (root / 'AirportMtkWlan/AirportMtkAwdlInterface.cpp').read_text()
ioctl = (root / 'include/Airport/apple80211_ioctl.h').read_text()
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
constexpr unsigned APPLE80211_VERSION=1,kIOReturnSuccess=0,kIOReturnNotReady=1,kIOReturnNoMemory=2,kIOReturnBadArgument=3,kIOReturnUnsupported=4,kIOReturnNotFound=5,
 APPLE80211_C_FLAG_20MHZ=1,APPLE80211_C_FLAG_2GHZ=8,APPLE80211_C_FLAG_5GHZ=16,
 APPLE80211_M_AWDL_AVAILABILITY_WINDOW_START=41,
 APPLE80211_M_AWDL_AVAILABILITY_WINDOW_EXTENSIONS_END=43;
uint64_t clockUS=1000000;uint64_t awdlNow(){return clockUS;}
void bzero(void*p,size_t n){memset(p,0,n);}
struct apple80211_channel{uint32_t version,channel,flags;};
#define __IO80211_TARGET __MAC_26_0
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
 uint32_t duration=0;std::function<void()> onReserve,onPrepare;std::function<void(bool)> onPeer;
 IOReturn awdlPrepareChannel(unsigned c){++prepares;preparedChannel=c;if(onPrepare)onPrepare();return 0;}bool awdlIsEnabled(){return on;}bool awdlChannelAllowed(unsigned c){return c==6||c==44;}
 bool awdlGrantSnapshot(mtkawdl::Reservation &out){out=grant;return on;}
 bool awdlCanTransmit(unsigned c){return grant.canTransmit(c,clockUS);}
 void awdlAbort(){++aborts;grant.cancel();}
 IOReturn awdlReserve(unsigned c,unsigned ms){++reserves;requested=c;duration=ms;
  if(onReserve)onReserve();return 0;}
 IOReturn peerDeleteResult=0;
 IOReturn awdlPeer(const uint8_t*,bool add){if(onPeer)onPeer(add);return add?0:peerDeleteResult;}
 IOReturn awdlTransmit(mbuf_t m,unsigned){++transmits;delete m;return 0;}
 IOReturn awdlTryTransmit(mbuf_t *m,unsigned c){auto result=awdlTransmit(*m,c);*m=nullptr;return result;}
 void give(uint8_t token,uint8_t c,uint32_t ms){grant.request(token,c,clockUS);
  assert(grant.grant(token,c,ms,clockUS));}
};
struct Event{unsigned id;std::vector<uint8_t> bytes;};
struct AirportMtkAwdlInterface{
 Hal radio;Hal*hal=&radio;Timer t;Timer*timer=&t;
 bool enabled=true,stopping=false,trafficActive=false,trafficPeerInstalled=false;
 uint8_t trafficPeer[6]{},installedTrafficPeer[6]{};
 uint8_t discoveryTxPeers[3][6]{};
 mtkawdl::DataPeers dataPeers;mtkawdl::State state;mtkawdl::Timeline awTimeline;mtkawdl::Window requestedWindow{};
 apple80211_awdl_sync_state syncState{};
 struct NativePeerSample{mtkawdl::Advertisement advertisement;uint8_t peer[6];uint64_t received;bool valid;};
 NativePeerSample nativePeerSamples[16]{};uint64_t advertisersRequests=0;
 uint8_t requestedChannel=0,grantedChannel=0;uint64_t requestDeadline=0;
 unsigned reserveDuration=0;IOReturn reserveStatus=0,actionStatus=0,miStatus=0;
 uint64_t dataTxSubmitted=0,dataTxFailed=0,dataTxExpired=0,dataTxDeferred=0;IOReturn dataTxStatus=0;
 uint64_t serviceTicks=0,reserveAttempts=0,grantObservations=0,awStartNotifications=0,
 nextAction=0,actionSubmitted=0,actionFailed=0,miStart=0,miSubmitted=0,miFailed=0;
 uint64_t reserveWaitUS=0,reserveMaxWaitUS=0,reserveInvalidations=0;uint32_t reserveInvalidReason=0;
 uint32_t reserveLeadUS=mtkawdl::rocLeadUs;uint64_t grantLatencyObservedAt=0;
 struct{unsigned mode=3;}afMode;apple80211_awdl_sync_params syncParams{1,16,16,16,440,0};
 apple80211_awdl_sync_channel_sequence channelSequence{};
 apple80211_awdl_presence_mode presence{};
 apple80211_awdl_election_params electionId{};unsigned secondaryMasterChannel=0;
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
 IOReturn setAWDL_SYNC_PARAMS(apple80211_awdl_sync_params*);
 IOReturn setAWDL_PRESENCE_MODE(apple80211_awdl_presence_mode*);
 IOReturn setAWDL_SYNCHRONIZATION_CHANNEL_SEQUENCE(apple80211_awdl_sync_channel_sequence*);
 IOReturn setAWDL_SECONDARY_MASTER_CHANNEL(apple80211_awdl_secondary_master_channel*);
 IOReturn setAWDL_MASTER_CHANNEL(apple80211_awdl_master_channel*);
 IOReturn setAWDL_ELECTION_PARAMS(apple80211_awdl_election_params*);
};
'''
structs=[]
for name in ['apple80211_awdl_sync_params','apple80211_awdl_sync_channel_sequence',
             'apple80211_awdl_presence_mode','apple80211_awdl_election_params',
             'apple80211_awdl_secondary_master_channel','apple80211_awdl_master_channel']:
    start=ioctl.index('struct '+name+' {')
    structs.append(ioctl[start:ioctl.index('} __attribute__((packed));',start)+len('} __attribute__((packed));')])
code=code.replace('struct awdl_peer_advert_add', '\n'.join(structs)+'\nstruct awdl_peer_advert_add')
for sig in ['void AirportMtkAwdlInterface::notifyAvailabilityWindowStart(',
            'void AirportMtkAwdlInterface::notifyAvailabilityWindowEnd(',
            'void AirportMtkAwdlInterface::serviceInGate(',
            'IOReturn AirportMtkAwdlInterface::setAWDL_SYNC_STATE(',
            'IOReturn AirportMtkAwdlInterface::setAWDL_SYNC_PARAMS(',
            'IOReturn AirportMtkAwdlInterface::setAWDL_PRESENCE_MODE(',
            'IOReturn AirportMtkAwdlInterface::setAWDL_SYNCHRONIZATION_CHANNEL_SEQUENCE(',
            'IOReturn AirportMtkAwdlInterface::setAWDL_MASTER_CHANNEL(',
            'IOReturn AirportMtkAwdlInterface::setAWDL_SECONDARY_MASTER_CHANNEL(',
            'IOReturn AirportMtkAwdlInterface::setAWDL_ELECTION_PARAMS(',
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

 // RX phase corrections do not revoke the matching firmware grant. Keep the
 // announced AW pinned even if the corrected schedule points into idle/next.
 AirportMtkAwdlInterface phase;init(phase);
 phase.state.sequence.channels[1]=phase.state.ownSequence.channels[1]=0;
 phase.serviceInGate();uint64_t pinnedEnd=phase.awTimeline.radioEnd;
 clockUS+=12000;phase.state.epoch-=60000;phase.serviceInGate();
 assert(phase.awTimeline.open&&phase.events.size()==1&&phase.radio.aborts==0);
 clockUS=pinnedEnd;phase.serviceInGate();
 assert(phase.events.size()==2&&mtkawdl::be32(phase.events[1].bytes.data()+4)==pinnedEnd);
 // Sequence replacement is administrative: pinning must not hide it, even
 // when the current channel and presence happen to be unchanged.
 AirportMtkAwdlInterface sequenceChange;init(sequenceChange);sequenceChange.serviceInGate();
 clockUS+=12000;sequenceChange.state.sequence.channels[5]=44;sequenceChange.serviceInGate();
 assert(sequenceChange.events.size()==2&&!sequenceChange.awTimeline.open&&sequenceChange.radio.aborts==1);
 AirportMtkAwdlInterface sequenceCallback;init(sequenceCallback);sequenceCallback.afMode.mode=0;
 sequenceCallback.onStart=[&]{sequenceCallback.state.sequence.channels[5]=44;};
 sequenceCallback.serviceInGate();assert(sequenceCallback.events.size()==2&&sequenceCallback.radio.transmits==0);
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
 // Scheduler submits one reservation; HAL owns its BSS/ROC transaction.
 AirportMtkAwdlInterface prepare;init(prepare);prepare.radio.grant.cancel();
 prepare.state.sequence.channels[1]=prepare.state.ownSequence.channels[1]=44;
 prepare.radio.onPrepare=[&]{clockUS+=20000;};
 clockUS+=10000;prepare.serviceInGate();assert(prepare.radio.reserves==0&&prepare.radio.prepares==0);
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
 // the firmware deadline; bounded ROC cannot produce a partial native AW.
 AirportMtkAwdlInterface same;init(same);uint8_t sameToken=1;uint64_t sameDue=0;
 same.radio.onReserve=[&]{same.radio.grant.request(++sameToken,6,clockUS);sameDue=clockUS+3000;};
 for(unsigned i=0;i<2200;++i){
  if(same.radio.grant.pending&&clockUS>=sameDue)
   assert(same.radio.grant.grant(sameToken,6,same.radio.duration,clockUS));
  same.serviceInGate();clockUS+=1000;
 }
 assert(same.awTimeline.starts==34&&same.awTimeline.ends==33&&same.radio.reserves<=3);
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

 // The sparse native schedule needs enough lead for off-channel arbitration.
 // Model 45ms grants: requests issued 25ms before an edge miss every active
 // off-channel start while immediate home-channel grants conceal the problem.
 AirportMtkAwdlInterface sparse;init(sparse);sparse.radio.grant.cancel();
 const uint8_t sparseChannels[16]={6,0,44,0,0,0,0,0,6,0,44,0,0,0,0,0};
 memcpy(sparse.state.sequence.channels,sparseChannels,16);
 sparse.state.ownSequence=sparse.state.sequence;
 uint8_t sparseToken=1;uint64_t sparseDue=0;
 sparse.radio.onReserve=[&]{sparse.radio.grant.request(++sparseToken,sparse.radio.requested,clockUS);sparseDue=clockUS+(sparse.radio.requested==44?45000:3000);};
 clockUS+=70000;uint64_t sparseEnd=clockUS+2*16*4*mtkawdl::awUs;
 while(clockUS<sparseEnd){
  if(sparse.radio.grant.pending&&clockUS>=sparseDue)
   assert(sparse.radio.grant.grant(sparseToken,sparse.radio.requested,sparse.radio.duration,clockUS));
  sparse.serviceInGate();clockUS+=sparse.t.us+250;
 }
 unsigned sparseOffChannel=0;
 for(const auto&e:sparse.events)if(e.id==41&&mtkawdl::le32(e.bytes.data()+28)==44)++sparseOffChannel;
 fprintf(stderr,"sparse offchannel=%u starts=%llu reserves=%u\n",sparseOffChannel,(unsigned long long)sparse.awTimeline.starts,sparse.radio.reserves);
 assert(sparseOffChannel==4);
 // A delayed grant response outlives the target EAW. Respect its actual
 // pending-response timeout rather than aborting it once every EAW.
 AirportMtkAwdlInterface slow;init(slow);slow.radio.grant.cancel();
 for(unsigned i=0;i<slow.state.sequence.count;++i)
  slow.state.sequence.channels[i]=slow.state.ownSequence.channels[i]=(i%2?44:0);
 slow.radio.onReserve=[&]{slow.radio.grant.request(7,44,clockUS);};
 clockUS=1000000+4*mtkawdl::awUs-24000;slow.serviceInGate();assert(slow.radio.reserves==1);
 clockUS=slow.requestedWindow.end+2000;slow.serviceInGate();
 assert(slow.radio.reserves==1&&slow.radio.aborts==0&&slow.radio.grant.pending);
 // A 200ms response must retain its token beyond the missed target. Use
 // real partial RF time, then announce only the next fully covered EAW.
 clockUS=slow.radio.grant.requestedAt+200000;
 slow.serviceInGate();assert(slow.radio.reserves==1&&slow.radio.aborts==0);
 assert(slow.radio.grant.grant(7,44,300,clockUS));
 slow.serviceInGate();assert(slow.events.empty());
 clockUS=1000000+16*mtkawdl::awUs+1000;slow.serviceInGate(); // idle
 assert(slow.radio.aborts==0&&slow.radio.grant.granted&&slow.events.empty());
 clockUS=1000000+20*mtkawdl::awUs;slow.serviceInGate();
 assert(slow.events.size()==1&&mtkawdl::le32(slow.events[0].bytes.data())==20);
 clockUS=slow.awTimeline.radioEnd;slow.serviceInGate();
 assert(slow.events.size()==2&&slow.events[1].id==43);
 // RLM can return after the originally planned EAW. The just-submitted
 // pending ROC still describes the same channel/schedule; do not cancel it.
 AirportMtkAwdlInterface delayedRlm;init(delayedRlm);delayedRlm.radio.grant.cancel();
 for(unsigned i=0;i<16;++i)
  delayedRlm.state.sequence.channels[i]=delayedRlm.state.ownSequence.channels[i]=(i%2?44:0);
 delayedRlm.radio.onReserve=[&]{clockUS+=200000;delayedRlm.radio.grant.request(9,44,clockUS);};
 clockUS=1000000+4*mtkawdl::awUs-24000;delayedRlm.serviceInGate();
 assert(delayedRlm.reserveWaitUS==200000&&delayedRlm.reserveInvalidations==0&&
        delayedRlm.radio.aborts==0&&delayedRlm.radio.grant.pending&&delayedRlm.requestedChannel==44);
 // Native follower loses its selected peer, while unrelated valid RX keeps
 // arriving. Keep the selected clock in holdover and the real granted AWs
 // progressing; fresh advertisements must not silently select another tree.
 AirportMtkAwdlInterface holdover;init(holdover);
 holdover.state.baseCounter=65532;
 holdover.state.nativeElectionManaged=true;holdover.state.selectNativeParent(peer);
 auto &lost=holdover.state.peers[0];lost.used=true;lost.seen=lost.epoch=clockUS;
 lost.baseCounter=65532;
 memcpy(lost.mac,peer,6);memcpy(lost.advertisement.master,peer,6);
 holdover.state.elect(clockUS);assert(holdover.state.setSyncRole(2,peer));
 holdover.state.elect(clockUS);holdover.serviceInGate();
 uint64_t holdoverOrigin=clockUS,holdoverStop=clockUS+5000000,dueHoldover=0;
 uint8_t holdoverToken=1;
 holdover.radio.onReserve=[&]{holdover.radio.grant.request(++holdoverToken,6,clockUS);dueHoldover=clockUS+3000;};
 while(clockUS<holdoverStop) {
  auto &unrelated=holdover.state.peers[1];unrelated.used=true;unrelated.seen=clockUS;
  const uint8_t other[]={2,1,2,3,4,7};memcpy(unrelated.mac,other,6);
  memcpy(unrelated.advertisement.master,other,6);
  if(holdover.radio.grant.pending&&clockUS>=dueHoldover)
   assert(holdover.radio.grant.grant(holdoverToken,6,holdover.radio.duration,clockUS));
  holdover.serviceInGate();clockUS+=holdover.t.us+250;
 }
 assert(clockUS-holdoverOrigin>mtkawdl::peerLifetimeUs&&!lost.used);
 assert(holdover.awTimeline.starts>=76&&holdover.state.channel(clockUS)==6);
 assert(!memcmp(holdover.state.sync,peer,6)&&holdover.state.nativeClockHoldover);
 assert(!holdover.state.synchronized&&holdover.state.nativeHoldoverTransitions==1);
 unsigned holdStarts=0,holdEnds=0;uint16_t previousHold=65528;
 uint32_t lastHoldStart=0,holdStart=0;
 for(const auto &e:holdover.events) {
  if(e.id==41) {
   assert(holdStarts==holdEnds);uint16_t c=mtkawdl::le32(e.bytes.data());
   assert(c==uint16_t(previousHold+4));previousHold=c;
   holdStart=mtkawdl::be32(e.bytes.data()+20);
   if(holdStarts) {int64_t gap=int64_t(uint32_t(holdStart-lastHoldStart))-4*int64_t(mtkawdl::awUs);
    assert(gap>=-5*1024&&gap<=5*1024);}
   assert(!memcmp(e.bytes.data()+8,peer,6));lastHoldStart=holdStart;++holdStarts;
  } else {assert(holdStarts==holdEnds+1);++holdEnds;
   uint32_t dwell=mtkawdl::be32(e.bytes.data()+4)-holdStart;
   assert(dwell/1024>=54&&dwell/1024<=74);}
 }
 // Holdover still advertises the real counter and selected tree, and sends
 // multicast only under the live grant. It does not recreate expired peers.
 uint8_t holdFrame[512];mtkawdl::Advertisement holdWire{};
 size_t holdSize=mtkawdl::buildAction(holdover.state,holdFrame,sizeof(holdFrame),clockUS);
 assert(mtkawdl::parseAction(holdFrame,holdSize,holdWire));
 assert(holdWire.counter==holdover.state.counter(clockUS)&&!memcmp(holdWire.master,peer,6));
 holdSize=mtkawdl::refreshAction(holdover.state,holdFrame,holdSize,clockUS);
 assert(mtkawdl::parseAction(holdFrame,holdSize,holdWire)&&holdWire.counter==holdover.state.counter(clockUS));
 uint8_t holdData[24]{};holdData[4]=1;
 holdover.queue[0]=holdover.makeFrame(holdData,sizeof(holdData));
 holdover.queueHead=0;holdover.queueTime[0]=clockUS;holdover.queueCount=1;
 assert(holdover.radio.awdlCanTransmit(6));holdover.serviceInGate();
 assert(!holdover.queueCount&&holdover.dataTxSubmitted==1&&!lost.used);
 // The selected source returns with a small phase offset. Resume bounded
 // tracking without adopting a new AW counter after the holdover.
 lost.used=true;lost.seen=clockUS;lost.epoch=holdoverOrigin-100;
 lost.baseCounter=65532;
 uint64_t returnEdge=holdover.awTimeline.radioEnd;
 uint16_t holdCounter=holdover.state.counter(returnEdge);
 clockUS=returnEdge;holdover.serviceInGate();
 assert(!holdover.state.nativeClockHoldover&&holdover.state.counter(clockUS)==holdCounter);
 assert(holdover.state.clockCorrections==1);
 // A different missing native parent cannot inherit the old holdover.
 mtkawdl::State missingParent=holdover.state;missingParent.discardControls();
 const uint8_t missingMac[]={2,1,2,3,4,8};missingParent.selectNativeParent(missingMac);
 missingParent.elect(clockUS);assert(!missingParent.radioScheduleReady()&&!missingParent.channel(clockUS));
 assert(!mtkawdl::buildAction(missingParent,holdFrame,sizeof(holdFrame),clockUS));
 // Observing a new parent with an incompatible counter does not validate
 // its clock or grant permission to enter holdover when that peer expires.
 auto &incompatible=missingParent.peers[2];incompatible.used=true;incompatible.seen=clockUS;
 incompatible.epoch=clockUS;incompatible.baseCounter=10000;
 memcpy(incompatible.mac,missingMac,6);memcpy(incompatible.advertisement.master,missingMac,6);
 missingParent.elect(clockUS);assert(missingParent.clockRejected&&!missingParent.nativeClockValidated);
 missingParent.elect(clockUS+mtkawdl::peerLifetimeUs+1);
 assert(!missingParent.nativeClockHoldover&&!missingParent.radioScheduleReady());
 // Non-election master wins even if a previously selected peer is live.
 mtkawdl::State ownMaster=holdover.state;ownMaster.discardControls();
 assert(ownMaster.setSyncRole(3,local));ownMaster.elect(clockUS);
 assert(!ownMaster.nativeClockHoldover&&!ownMaster.synchronized&&!memcmp(ownMaster.master,local,6));
 // Before ever acquiring the selected clock, follower stays quiet despite
 // an otherwise valid RF grant. Holdover never invents initial sync.
 AirportMtkAwdlInterface neverSelected;init(neverSelected);
 neverSelected.state.nativeElectionManaged=true;
 assert(neverSelected.state.setSyncRole(2,peer));neverSelected.serviceInGate();
 assert(!neverSelected.state.nativeClockHoldover&&neverSelected.events.empty()&&neverSelected.radio.transmits==0);

 // Compare the measured RLM+grant path with ROC-only temporary switching.
 // Exact observed channel groups, ~15ms RLM and 13.424ms ROC response.
 unsigned coverage[2]{};
 for(unsigned scenario=0;scenario<2;++scenario) {
  AirportMtkAwdlInterface grouped;init(grouped);
  const uint8_t groups[16]={6,6,6,6,44,44,44,44,6,6,6,6,44,44,44,44};
  memcpy(grouped.state.sequence.channels,groups,16);grouped.state.ownSequence=grouped.state.sequence;
  grouped.radio.give(1,6,273);uint64_t groupDue=0,stop=clockUS+4000000;uint8_t token=1;
  grouped.radio.onReserve=[&]{if(scenario==0)clockUS+=15019;
   grouped.radio.grant.request(++token,grouped.radio.requested,clockUS);groupDue=clockUS+13424;};
  while(clockUS<stop) {
   if(grouped.radio.grant.pending&&clockUS>=groupDue)
    assert(grouped.radio.grant.grant(token,grouped.radio.requested,grouped.radio.duration,clockUS));
   grouped.serviceInGate();clockUS+=grouped.t.us+100;
  }
  unsigned groupEnds=0;uint32_t groupStart=0,previousStart=0;uint16_t previous=0;
  for(const auto&e:grouped.events) {
   if(e.id==41) {
    assert(coverage[scenario]==groupEnds);uint16_t counter=mtkawdl::le32(e.bytes.data());
    uint64_t stamp=mtkawdl::be32(e.bytes.data()+20);mtkawdl::Window expected{};
    assert(mtkawdl::currentWindow(grouped.state,stamp,expected));
    assert(counter==expected.counter&&stamp>=expected.start&&stamp-expected.start<=8000);
    assert(mtkawdl::le32(e.bytes.data()+28)==expected.channel);
    if(scenario==1&&coverage[scenario]) {
     assert(counter==uint16_t(previous+4));
     int64_t gap=int64_t(uint32_t(stamp-previousStart))-4*int64_t(mtkawdl::awUs);
     assert(gap>=-5*1024&&gap<=5*1024);
    }
    groupStart=previousStart=stamp;previous=counter;++coverage[scenario];
   } else {assert(coverage[scenario]==groupEnds+1);++groupEnds;
    uint32_t dwell=mtkawdl::be32(e.bytes.data()+4)-groupStart;
    assert(dwell/1024>=54&&dwell/1024<=74);}
  }
 }
 fprintf(stderr,"measured grouped coverage RLM=%u ROC-only=%u\n",coverage[0],coverage[1]);
 assert(coverage[1]>coverage[0]);
 // Honor the driver's requested timer interval; fixed 1ms polling can hide
 // misses when the production timer asks for 2ms. Include bounded jitter.
 for(unsigned latency:{3000,8000}) {
  AirportMtkAwdlInterface timed;init(timed);timed.state.baseCounter=65532;
  for(unsigned i=0;i<timed.state.sequence.count;++i)
   timed.state.sequence.channels[i]=timed.state.ownSequence.channels[i]=(i%3==1?44:6);
  uint8_t token=1;uint64_t due=0,end=clockUS+2700000;
  timed.radio.onReserve=[&]{timed.radio.grant.request(++token,timed.radio.requested,clockUS);due=clockUS+latency;};
  while(clockUS<end){
   if(timed.radio.grant.pending&&clockUS>=due)
    assert(timed.radio.grant.grant(token,timed.radio.requested,timed.radio.duration,clockUS));
   timed.serviceInGate();assert(timed.t.us);clockUS+=timed.t.us+250;
  }
  assert(timed.awTimeline.starts==42&&timed.awTimeline.ends==41);
 }
 // Cross presence, dispatch jitter and grant latency using the actual timer.
 // Check each wire event against its expected window, not merely balanced totals.
 for(unsigned presence:{1,2,4,8,16,32,64})
 for(unsigned latency:{3000,8000})
 for(unsigned jitter:{0,250,750}) {
  AirportMtkAwdlInterface sweep;init(sweep);
  assert(sweep.state.setPresence(presence,clockUS));
  sweep.state.baseCounter=uint16_t(65536-presence);
  for(unsigned i=0;i<sweep.state.sequence.count;++i)
   sweep.state.sequence.channels[i]=sweep.state.ownSequence.channels[i]=(i%3==1?44:6);
  sweep.radio.give(1,sweep.state.channel(clockUS),mtkawdl::maxRocMs);
  uint8_t token=1;uint64_t due=0,length=uint64_t(presence)*mtkawdl::awUs;
  uint64_t epoch=clockUS,stop=clockUS+length*20;
  sweep.radio.onReserve=[&]{sweep.radio.grant.request(++token,sweep.radio.requested,clockUS);due=clockUS+latency;};
  while(clockUS<stop){
   if(sweep.radio.grant.pending&&clockUS>=due)
    assert(sweep.radio.grant.grant(token,sweep.radio.requested,sweep.radio.duration,clockUS));
   sweep.serviceInGate();assert(sweep.t.us);clockUS+=sweep.t.us+jitter;
  }
  fprintf(stderr,"sweep presence=%u latency=%u jitter=%u starts=%llu ends=%llu\n",
          presence,latency,jitter,(unsigned long long)sweep.awTimeline.starts,
          (unsigned long long)sweep.awTimeline.ends);
  assert(sweep.awTimeline.starts==20);
  unsigned starts=0,ends=0;uint32_t startTime=0,previousTime=0;
  for(const auto&event:sweep.events){
   if(event.id==41){
    assert(starts==ends);
    uint64_t edge=epoch+length*starts;
    mtkawdl::Window expected{};assert(mtkawdl::currentWindow(sweep.state,edge,expected));
    startTime=mtkawdl::be32(event.bytes.data()+20);
    assert(startTime>=edge&&startTime-edge<=8000);
    if(starts) {int64_t gap=int64_t(uint32_t(startTime-previousTime))-int64_t(length);
     assert(gap>=-5*1024&&gap<=5*1024);}
    previousTime=startTime;
    assert(mtkawdl::le32(event.bytes.data())==expected.counter);
    assert(mtkawdl::le32(event.bytes.data()+28)==expected.channel);++starts;
   }else{
    assert(starts==ends+1);++ends;
    uint32_t actual=mtkawdl::be32(event.bytes.data()+4)-startTime;
    assert(actual+10*1024>=length&&actual<=length+10*1024);
   }
  }
  assert(starts==20&&starts==ends+unsigned(sweep.awTimeline.open));
 }
 // Firmware may shorten an early ROC. Keep its actual grant for partial TX;
 // do not issue new tokens every tick just because it cannot cover native AW.
 AirportMtkAwdlInterface clipped;init(clipped);clipped.radio.grant.cancel();
 clipped.state.sequence.channels[0]=clipped.state.ownSequence.channels[0]=0;
 clipped.state.sequence.channels[1]=clipped.state.ownSequence.channels[1]=44;
 clipped.radio.onReserve=[&]{clipped.radio.grant.request(7,44,clockUS);};
 clockUS=1000000+4*mtkawdl::awUs-24000;clipped.serviceInGate();
 clockUS+=1000;assert(clipped.radio.grant.grant(7,44,32,clockUS));
 for(unsigned i=0;i<10;++i){clipped.serviceInGate();clockUS+=1000;}
 assert(clipped.radio.reserves==1&&clipped.radio.aborts==0&&clipped.events.empty());
 // A longer clipped grant permits real partial TX after the start tolerance,
 // remains unannounced, then requests the next EAW at its planned lead time.
 AirportMtkAwdlInterface partial;init(partial);partial.radio.grant.cancel();
 partial.state.sequence.channels[0]=partial.state.ownSequence.channels[0]=0;
 partial.state.sequence.channels[1]=partial.state.ownSequence.channels[1]=44;
 partial.state.sequence.channels[2]=partial.state.ownSequence.channels[2]=0;
 partial.state.sequence.channels[3]=partial.state.ownSequence.channels[3]=44;
 partial.radio.onReserve=[&]{partial.radio.grant.request(8,partial.radio.requested,clockUS);};
 clockUS=1000000+4*mtkawdl::awUs-24000;partial.serviceInGate();
 clockUS+=1000;assert(partial.radio.grant.grant(8,44,50,clockUS));
 clockUS=partial.requestedWindow.start+9000;
 uint8_t multicast[24]{};multicast[4]=1;
 partial.queue[0]=partial.makeFrame(multicast,sizeof(multicast));
 partial.queueTime[0]=clockUS;partial.queueCount=1;partial.serviceInGate();
 assert(partial.events.empty()&&partial.radio.reserves==1&&partial.radio.transmits==1&&!partial.queueCount);
 clockUS=partial.radio.grant.deadline;partial.serviceInGate();
 assert(partial.radio.reserves==1&&!partial.radio.grant.pending&&partial.events.empty());
 clockUS=1000000+12*mtkawdl::awUs-mtkawdl::rocLeadUs;partial.serviceInGate();
 assert(partial.radio.reserves==2&&partial.radio.grant.pending&&partial.events.empty());
 // Discovery station waits can release the gate and expire membership. A
 // stale add must be removed and cannot authorize an AW from the old edge.
 AirportMtkAwdlInterface station;init(station);station.dataPeers.observe(peer,clockUS);
 uint8_t unicastFrame[24]{};memcpy(unicastFrame+4,peer,6);
 station.queue[0]=station.makeFrame(unicastFrame,sizeof(unicastFrame));
 station.queueTime[0]=clockUS;station.queueCount=1;
 unsigned adds=0,deletes=0;
 station.radio.onPeer=[&](bool add){if(add){++adds;clockUS+=20000;station.dataPeers.reset();}else ++deletes;};
 station.serviceInGate();assert(adds==1&&deletes==1&&station.events.empty());
 for(auto &slot:station.discoveryTxPeers)assert(!slot[0]);
 mbuf_freem(station.queue[station.queueHead]);station.queueCount=0;
 // A cache/traffic callback reviving a peer during discovery cleanup must
 // restore its station after the delete, without losing the new owner.
 AirportMtkAwdlInterface revived;init(revived);memcpy(revived.discoveryTxPeers[0],peer,6);
 adds=deletes=0;
 revived.radio.onPeer=[&](bool add){if(add)++adds;else {++deletes;assert(revived.dataPeers.setTraffic(peer,true,clockUS));}};
 revived.serviceInGate();assert(adds==1&&deletes==1&&revived.dataPeers.find(peer,clockUS)>=0);
 assert(!memcmp(revived.discoveryTxPeers[0],peer,6));
 revived.radio.onPeer=[&](bool add){if(add)++adds;else ++deletes;};
 assert(revived.dataPeers.setTraffic(peer,false,clockUS));revived.serviceInGate();
 assert(adds==1&&deletes==2&&!mtkawdl::unicast(revived.discoveryTxPeers[0]));
 // Discovery advertisements can revive membership too, without native ownership.
 AirportMtkAwdlInterface observed;init(observed);memcpy(observed.discoveryTxPeers[0],peer,6);
 observed.radio.onPeer=[&](bool add){if(!add)observed.dataPeers.observe(peer,clockUS);};
 observed.serviceInGate();assert(!memcmp(observed.discoveryTxPeers[0],peer,6));
 observed.radio.onPeer=nullptr;clockUS+=mtkawdl::peerLifetimeUs+1;observed.serviceInGate();
 assert(!mtkawdl::unicast(observed.discoveryTxPeers[0]));
 // A stale add whose cleanup failed remains tracked for the next cleanup tick.
 AirportMtkAwdlInterface failedCleanup;init(failedCleanup);failedCleanup.dataPeers.observe(peer,clockUS);
 failedCleanup.queue[0]=failedCleanup.makeFrame(unicastFrame,sizeof(unicastFrame));
 failedCleanup.queueTime[0]=clockUS;failedCleanup.queueCount=1;
 failedCleanup.radio.peerDeleteResult=kIOReturnNotReady;
 failedCleanup.radio.onPeer=[&](bool add){if(add)failedCleanup.dataPeers.reset();};
 failedCleanup.serviceInGate();bool tracked=false;
 for(auto &slot:failedCleanup.discoveryTxPeers)tracked|=!memcmp(slot,peer,6);assert(tracked);
 failedCleanup.radio.peerDeleteResult=0;failedCleanup.radio.onPeer=nullptr;failedCleanup.serviceInGate();
 for(auto &slot:failedCleanup.discoveryTxPeers)assert(!mtkawdl::unicast(slot));
 mbuf_freem(failedCleanup.queue[failedCleanup.queueHead]);failedCleanup.queueCount=0;
 // Sync disable in the early-end callback must not submit another ROC.
 AirportMtkAwdlInterface stopped;init(stopped);stopped.state.sequence.channels[1]=stopped.state.ownSequence.channels[1]=44;
 stopped.serviceInGate();stopped.onEnd=[&]{stopped.enabled=false;};
 clockUS=stopped.awTimeline.active.end-7000;stopped.serviceInGate();
 assert(stopped.events.size()==2&&stopped.radio.reserves==0&&!stopped.awTimeline.open);
 // End callback may replace the channel sequence and its clock.
 AirportMtkAwdlInterface replaced;init(replaced);replaced.state.sequence.channels[1]=replaced.state.ownSequence.channels[1]=44;
 replaced.serviceInGate();replaced.onEnd=[&]{replaced.state.sequence.channels[1]=replaced.state.ownSequence.channels[1]=6;};
 clockUS=replaced.awTimeline.active.end-7000;replaced.serviceInGate();
 assert(replaced.radio.requested!=44);
 // Audit every accepted presence mode, including the 1024TU EAW.
 for(unsigned presence:{1,2,4,8,16,32,64}) {
  AirportMtkAwdlInterface wide;init(wide);wide.radio.grant.cancel();
  assert(wide.state.setPresence(presence,clockUS));
  uint8_t token=1;uint64_t due=0;
  wide.radio.onReserve=[&]{wide.radio.grant.request(++token,wide.radio.requested,clockUS);due=clockUS+3000;};
  uint64_t end=clockUS+uint64_t(presence)*mtkawdl::awUs*4;
  while(clockUS<end){
   if(wide.radio.grant.pending&&clockUS>=due)
    assert(wide.radio.grant.grant(token,wide.radio.requested,wide.radio.duration,clockUS));
   wide.serviceInGate();clockUS+=1000;
  }
  fprintf(stderr,"presence=%u starts=%llu ends=%llu\n",presence,
          (unsigned long long)wide.awTimeline.starts,(unsigned long long)wide.awTimeline.ends);
  assert(wide.awTimeline.starts==4&&wide.awTimeline.ends>=3);
 }
 // Tahoe programs mode 1 with a remote synchronization MAC. Accept it, and
 // preserve a pending grant when native refreshes the identical role.
 AirportMtkAwdlInterface mode;init(mode);mode.state.nativeElectionManaged=true;
 apple80211_awdl_sync_state control{};control.version=1;control.state=1;
 memcpy(control.master,peer,6);control.mode_flags=0x20;
 assert(mode.setAWDL_SYNC_STATE(&control)==0);
 mode.radio.grant.request(7,6,clockUS);unsigned aborts=mode.radio.aborts;
 control.flags=65532;assert(mode.setAWDL_SYNC_STATE(&control)==0);
 assert(mode.radio.aborts==aborts&&mode.radio.grant.pending&&mode.syncState.flags==65532);
 // Native opmode reprogramming at 0/10/20TU must take effect after the
 // recorded AW-end, including a synchronous setter in the start callback.
 for(unsigned offset:{0U,10U*1024,20U*1024}) {
  AirportMtkAwdlInterface transition;init(transition);
  transition.state.nativeElectionManaged=true;
  apple80211_awdl_sync_state modeRequest{};modeRequest.version=1;modeRequest.state=3;
  memcpy(modeRequest.master,local,6);
  if(!offset) transition.onStart=[&]{assert(!transition.setAWDL_SYNC_STATE(&modeRequest));};
  transition.serviceInGate();uint64_t end=transition.awTimeline.radioEnd;
  if(offset) {clockUS+=offset;assert(!transition.setAWDL_SYNC_STATE(&modeRequest));}
  assert(transition.awTimeline.open&&transition.events.size()==1&&transition.radio.aborts==0);
  assert(transition.state.syncRole==1);
  transition.onStart=nullptr;clockUS=end;transition.serviceInGate();
  assert(transition.events.size()>=2&&transition.events[1].id==43&&transition.state.syncRole==3);
  assert((mtkawdl::be32(transition.events[1].bytes.data()+4)-
          mtkawdl::be32(transition.events[0].bytes.data()+20))/1024==64);
 }
 // Exercise sequence/presence/social-channel and election setters together.
 // Last requests win while the event and PSF keep the old schedule.
 AirportMtkAwdlInterface controls;init(controls);controls.state.nativeElectionManaged=true;
 controls.serviceInGate();uint64_t controlsEnd=controls.awTimeline.radioEnd;
 clockUS+=10000;apple80211_awdl_sync_channel_sequence sequence{};
 sequence.version=1;sequence.length=16;sequence.step_count=3;
 for(unsigned i=0;i<16;++i)sequence.seqs[i].channel=44;
 assert(!controls.setAWDL_SYNCHRONIZATION_CHANNEL_SEQUENCE(&sequence));
 apple80211_awdl_presence_mode presence{1,8};assert(!controls.setAWDL_PRESENCE_MODE(&presence));
 apple80211_awdl_secondary_master_channel secondary{1,6};
 assert(!controls.setAWDL_SECONDARY_MASTER_CHANNEL(&secondary));
 apple80211_awdl_master_channel primary{1,6};assert(!controls.setAWDL_MASTER_CHANNEL(&primary));
 apple80211_awdl_election_params election{};election.version=1;memcpy(election.master,local,6);
 controls.syncParams.non_election_master=1;assert(!controls.setAWDL_ELECTION_PARAMS(&election));
 assert(controls.state.sequence.channels[3]==6&&controls.state.presence==4&&controls.state.syncRole==1);
 assert(controls.state.controlsDirty&&controls.awTimeline.open&&controls.radio.aborts==0);
 uint8_t controlFrame[512];mtkawdl::Advertisement controlWire{};
 size_t controlSize=mtkawdl::buildAction(controls.state,controlFrame,sizeof(controlFrame),clockUS);
 assert(mtkawdl::parseAction(controlFrame,controlSize,controlWire)&&controlWire.presence==4&&controlWire.sequence.channels[3]==6);
 uint16_t nextCounter=controls.state.counter(controlsEnd);
 clockUS=controlsEnd;controls.serviceInGate();
 assert(controls.state.sequence.channels[0]==6&&controls.state.sequence.channels[1]==6&&
        controls.state.sequence.channels[3]==44&&controls.state.presence==8&&controls.state.syncRole==3);
 assert(controls.state.counter(clockUS)==nextCounter&&!controls.state.controlsDirty);
 assert(controls.events[1].id==43&&mtkawdl::be32(controls.events[1].bytes.data()+4)==controlsEnd);
 // Changing the selected native advertiser in the start callback must not
 // cut a zero-TU end. Consume its validated RX clock after the full old AW.
 AirportMtkAwdlInterface newParent;init(newParent);newParent.state.nativeElectionManaged=true;
 auto &newSample=newParent.nativePeerSamples[0];newSample.valid=true;newSample.received=clockUS;
 memcpy(newSample.peer,peer,6);auto &newAd=newSample.advertisement;
 memcpy(newAd.master,peer,6);memcpy(newAd.sync,peer,6);
 newAd.counter=0;newAd.down=64;newAd.period=16;newAd.presence=4;newAd.sequence=newParent.state.sequence;
 auto &newPeer=newParent.state.peers[0];newPeer.used=true;newPeer.seen=clockUS;memcpy(newPeer.mac,peer,6);
 awdl_peer_advert_add newAdvert{};mtkawdl::put16(newAdvert.bytes+2,64);
 mtkawdl::put16(newAdvert.bytes+10,16);mtkawdl::put16(newAdvert.bytes+12,16);newAdvert.bytes[16]=4;
 mtkawdl::putBE32(newAdvert.bytes+20,uint32_t(clockUS));
 memcpy(newAdvert.bytes+32,peer,6);memcpy(newAdvert.bytes+38,peer,6);
 newParent.onStart=[&]{assert(!newParent.setAWDL_AWDL_ADVERTISERS(&newAdvert));};
 newParent.serviceInGate();uint64_t parentEnd=newParent.awTimeline.radioEnd;
 assert(newParent.events.size()==1&&newParent.radio.aborts==0&&!newParent.state.nativeParentSelected);
 newParent.onStart=nullptr;clockUS=parentEnd;newParent.serviceInGate();
 assert(newParent.events.size()>=2&&newParent.events[1].id==43&&newParent.state.nativeParentSelected);
 assert(mtkawdl::be32(newParent.events[1].bytes.data()+4)==parentEnd&&newParent.state.counter(clockUS)==4);
 // A parent with an unrelated counter does not reset an emitted host/wire
 // timeline. The discontinuity is rejected and remains observable.
 AirportMtkAwdlInterface discontinuity;init(discontinuity);discontinuity.state.nativeElectionManaged=true;
 discontinuity.serviceInGate();uint64_t discontinuityEnd=discontinuity.awTimeline.radioEnd;
 clockUS+=10000;auto &foreign=discontinuity.state.peers[0];foreign.used=true;foreign.seen=foreign.epoch=clockUS;
 foreign.baseCounter=23296;memcpy(foreign.mac,peer,6);memcpy(foreign.advertisement.master,peer,6);
 discontinuity.state.selectNativeParent(peer);discontinuity.state.elect(clockUS);
 uint16_t expectedCounter=discontinuity.state.counter(discontinuityEnd);
 clockUS=discontinuityEnd;discontinuity.serviceInGate();
 assert(discontinuity.state.counter(clockUS)==expectedCounter&&discontinuity.state.clockRejected==1);
 assert(discontinuity.events.size()>=2&&discontinuity.events[1].id==43&&
        mtkawdl::be32(discontinuity.events[1].bytes.data()+4)==discontinuityEnd);
 AirportMtkAwdlInterface endCallback;init(endCallback);endCallback.serviceInGate();
 endCallback.onEnd=[&]{size_t events=endCallback.events.size();endCallback.serviceInGate();
  assert(endCallback.events.size()==events&&!endCallback.awTimeline.open);};
 clockUS=endCallback.awTimeline.radioEnd;endCallback.serviceInGate();
 assert(endCallback.events.size()==2&&!endCallback.state.controlsHeld);
 // Repeat opmode/PSF/sequence programming every EAW across counter wrap.
 AirportMtkAwdlInterface toggles;init(toggles);toggles.state.nativeElectionManaged=true;
 toggles.state.baseCounter=65532;
 auto &togglePeer=toggles.state.peers[0];togglePeer.used=true;togglePeer.seen=togglePeer.epoch=clockUS;
 togglePeer.baseCounter=65532;memcpy(togglePeer.mac,peer,6);memcpy(togglePeer.advertisement.master,peer,6);
 toggles.state.selectNativeParent(peer);toggles.state.elect(clockUS);
 uint64_t toggleStop=clockUS+2700000,toggleDue=0;uint8_t toggleToken=1;
 toggles.radio.onReserve=[&]{toggles.radio.grant.request(++toggleToken,6,clockUS);toggleDue=clockUS+3000;};
 uint16_t programmed=0;bool programmedValid=false;
 while(clockUS<toggleStop) {
  if(toggles.radio.grant.pending&&clockUS>=toggleDue)
   assert(toggles.radio.grant.grant(toggleToken,6,toggles.radio.duration,clockUS));
  if(toggles.awTimeline.open&&clockUS-toggles.awTimeline.lastStart>=10000&&
     (!programmedValid||programmed!=toggles.awTimeline.active.counter)) {
   programmed=toggles.awTimeline.active.counter;programmedValid=true;
   apple80211_awdl_sync_state mode{};mode.version=1;mode.state=programmed%8?1:2;memcpy(mode.master,peer,6);
   assert(!toggles.setAWDL_SYNC_STATE(&mode));
   apple80211_awdl_sync_params params{1,16,16,16,programmed%8?440U:110U,0};
   assert(!toggles.setAWDL_SYNC_PARAMS(&params));
   apple80211_awdl_sync_channel_sequence seq{};seq.version=1;seq.length=16;seq.step_count=3;
   for(unsigned j=0;j<16;++j)seq.seqs[j].channel=6;
   assert(!toggles.setAWDL_SYNCHRONIZATION_CHANNEL_SEQUENCE(&seq));
   // A new RX observation retains the same peer's clock despite opmode changes.
   togglePeer.seen=clockUS;toggles.state.elect(clockUS);
  }
  toggles.serviceInGate();assert(toggles.t.us);clockUS+=toggles.t.us+250;
 }
 assert(toggles.awTimeline.starts==42&&toggles.awTimeline.ends==41&&toggles.reserveInvalidations==0);
 unsigned toggleStarts=0,toggleEnds=0;uint16_t toggleCounter=65528;uint32_t toggleStart=0,lastToggleStart=0;
 for(const auto&e:toggles.events) {
  if(e.id==41) {assert(toggleStarts==toggleEnds);uint16_t c=mtkawdl::le32(e.bytes.data());
   assert(c==uint16_t(toggleCounter+4));toggleCounter=c;
   toggleStart=mtkawdl::be32(e.bytes.data()+20);
   if(toggleStarts) {int64_t gap=int64_t(uint32_t(toggleStart-lastToggleStart))-4*int64_t(mtkawdl::awUs);
    assert(gap>=-5*1024&&gap<=5*1024);}
   lastToggleStart=toggleStart;++toggleStarts;
  } else {assert(toggleStarts==toggleEnds+1);++toggleEnds;
   unsigned duration=(mtkawdl::be32(e.bytes.data()+4)-toggleStart)/1024;
   assert(duration>=54&&duration<=74);}
 }
 // Never reopen an early-closed real EAW with a changed role/master record.
 AirportMtkAwdlInterface earlyControl;init(earlyControl);earlyControl.state.nativeElectionManaged=true;
 earlyControl.state.sequence.channels[1]=earlyControl.state.ownSequence.channels[1]=44;
 earlyControl.serviceInGate();uint64_t earlyEnd=earlyControl.awTimeline.active.end;
 apple80211_awdl_sync_state earlyMode{};earlyMode.version=1;earlyMode.state=3;memcpy(earlyMode.master,local,6);
 clockUS+=10000;assert(!earlyControl.setAWDL_SYNC_STATE(&earlyMode));
 clockUS=earlyEnd-7000;earlyControl.serviceInGate();assert(earlyControl.events.size()==2);
 // The measured 97ms grant delay exceeds the old 55ms lookahead. Learn a
 // bounded lead from accepted grants and cover following sparse channel AWs.
 AirportMtkAwdlInterface latency;init(latency);latency.radio.grant.cancel();
 const uint8_t latencyChannels[16]={6,0,0,44,0,0,0,0,6,0,0,44,0,0,0,0};
 memcpy(latency.state.sequence.channels,latencyChannels,16);latency.state.ownSequence=latency.state.sequence;
 clockUS+=97000;latency.radio.grant.request(1,6,clockUS-97000);
 assert(latency.radio.grant.grant(1,6,100,clockUS));
 latency.serviceInGate();assert(latency.reserveLeadUS==105000);
 uint64_t latencyDue=0,latencyStop=clockUS+2*16*4*mtkawdl::awUs;uint8_t latencyToken=1;
 latency.radio.onReserve=[&]{clockUS+=5000;latency.radio.grant.request(++latencyToken,latency.radio.requested,clockUS);latencyDue=clockUS+(latency.radio.requested==44?97000:3000);};
 while(clockUS<latencyStop) {
  if(latency.radio.grant.pending&&clockUS>=latencyDue)
   assert(latency.radio.grant.grant(latencyToken,latency.radio.requested,latency.radio.duration,clockUS));
  latency.serviceInGate();assert(latency.t.us);clockUS+=latency.t.us+250;
 }
 unsigned offChannel=0;for(const auto&e:latency.events)if(e.id==41&&mtkawdl::le32(e.bytes.data()+28)==44)++offChannel;
 fprintf(stderr,"adaptive offchannel=%u lead=%u reserves=%u starts=%llu\n",offChannel,latency.reserveLeadUS,latency.radio.reserves,(unsigned long long)latency.awTimeline.starts);
 assert(offChannel==4&&latency.reserveLeadUS>=105000&&latency.reserveLeadUS<=125000);
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
 // A fresh same-parent advertisement with a discontinuous clock must not
 // terminate the already notified grant or replace the host counter.
 selected.radio.give(10,6,70);selected.serviceInGate();assert(selected.awTimeline.open);
 clockUS+=12000;sample.received=clockUS;cached.seen=clockUS;ad.counter=64;
 mtkawdl::put16(advert.bytes,64);mtkawdl::putBE32(advert.bytes+20,uint32_t(clockUS));
 uint16_t hostCounter=selected.state.counter(clockUS);aborts=selected.radio.aborts;
 assert(selected.setAWDL_AWDL_ADVERTISERS(&advert)==0);
 assert(selected.awTimeline.open&&selected.radio.aborts==aborts&&selected.state.counter(clockUS)==hostCounter);
 assert(selected.state.clockRejected==0); // observation is consumed at AW end
 // A fresh selected-parent PSF can arrive while the synchronous RLM wait
 // releases the gate, then again while ROC is pending and during the AW.
 // Keep the radio clock AND outgoing synchronization TLV on one timeline.
 for(int drift:{-3000,3000}) {
  AirportMtkAwdlInterface held;init(held);held.radio.grant.cancel();
  for(unsigned i=0;i<16;++i) held.state.sequence.channels[i]=(i%2?44:0);
  held.state.ownSequence=held.state.sequence;
  held.state.nativeElectionManaged=held.state.nativeParentSelected=true;
  memcpy(held.state.nativeParent,peer,6);
  auto &p=held.state.peers[0];p.used=true;p.seen=p.epoch=clockUS;
  memcpy(p.mac,peer,6);memcpy(p.advertisement.master,peer,6);
  memcpy(p.advertisement.sync,peer,6);p.advertisement.presence=4;
  p.advertisement.sequence=held.state.sequence;held.state.elect(clockUS);
  clockUS=1000000+4*mtkawdl::awUs-24000;
  uint64_t epoch=held.state.epoch;uint16_t base=held.state.baseCounter;
  auto sampleClock=[&]{p.seen=clockUS;p.epoch=uint64_t(int64_t(epoch)-drift);held.state.elect(clockUS);};
  held.radio.onReserve=[&]{clockUS+=10000;sampleClock();held.radio.grant.request(11,44,clockUS);};
  held.serviceInGate();
  assert(held.radio.reserves==1&&held.radio.aborts==0&&held.radio.grant.pending);
  assert(held.state.epoch==epoch&&held.state.baseCounter==base&&held.events.empty());
  clockUS+=1000;sampleClock();held.serviceInGate();
  assert(held.state.epoch==epoch&&held.radio.reserves==1&&held.events.empty());
  held.radio.give(11,44,100);clockUS=held.requestedWindow.start;held.serviceInGate();
  assert(held.awTimeline.open&&held.events.size()==1);
  uint64_t end=held.awTimeline.radioEnd;
  clockUS+=20000;sampleClock();held.serviceInGate();
  uint8_t frame[512];mtkawdl::Advertisement wire{};
  size_t n=mtkawdl::buildAction(held.state,frame,sizeof(frame),clockUS);
  assert(mtkawdl::parseAction(frame,n,wire));
  assert(wire.counter==held.state.counter(clockUS)&&wire.sequence.channels[1]==44);
  assert(held.state.epoch==epoch&&held.awTimeline.radioEnd==end&&held.events.size()==1);
  mtkawdl::State beforeRelease=held.state;
  clockUS=end;held.serviceInGate();
  assert(!held.awTimeline.open&&held.events.size()==2&&held.state.clockCorrections==1);
  int32_t adjustment=int16_t(held.state.counter(end)-beforeRelease.counter(end))*int32_t(mtkawdl::awUs)+
   int32_t((end-held.state.epoch)%mtkawdl::awUs)-int32_t((end-beforeRelease.epoch)%mtkawdl::awUs);
  assert(adjustment==(drift>0?512:-512));
  assert((mtkawdl::be32(held.events[1].bytes.data()+4)-
          mtkawdl::be32(held.events[0].bytes.data()+20))/1024==64);
 }
 // Sparse grants plus repeated clock observations across counter rollover.
 // Every announced counter must be the next real nonzero sequence slot.
 for(int drift:{-3000,3000}) {
  AirportMtkAwdlInterface run;init(run);run.radio.grant.cancel();
  memcpy(run.state.sequence.channels,sparseChannels,16);run.state.ownSequence=run.state.sequence;
  run.state.baseCounter=65504;
  run.state.nativeElectionManaged=run.state.nativeParentSelected=true;
  memcpy(run.state.nativeParent,peer,6);auto &p=run.state.peers[0];
  p.used=true;p.seen=p.epoch=clockUS;p.baseCounter=65504;
  memcpy(p.mac,peer,6);memcpy(p.advertisement.master,peer,6);run.state.elect(clockUS);
  uint64_t origin=clockUS,due=0,nextSample=clockUS+70000,stop=clockUS+4000000;
  uint8_t token=1;
  run.radio.onReserve=[&]{clockUS+=10000;p.seen=clockUS;run.state.elect(clockUS);
   run.radio.grant.request(++token,run.radio.requested,clockUS);
   due=clockUS+(run.radio.requested==44?35000:3000);};
  clockUS+=70000;
  while(clockUS<stop) {
   if(clockUS>=nextSample) {
    // Model one peer clock with an offset, then its observations settle.
    p.epoch=uint64_t(int64_t(origin)-drift);p.seen=clockUS;
    run.state.elect(clockUS);nextSample=clockUS+70000;
   }
   if(run.radio.grant.pending&&clockUS>=due)
    assert(run.radio.grant.grant(token,run.radio.requested,run.radio.duration,clockUS));
   run.serviceInGate();assert(run.t.us);clockUS+=run.t.us+250;
  }
  assert(run.reserveInvalidations==0&&run.state.clockDeferred>0&&run.state.clockCorrections>0);
  unsigned starts=0,ends=0;uint16_t previous=65504;uint32_t start=0,previousStart=0;
  for(const auto &event:run.events) {
   if(event.id==41) {
    assert(starts==ends);uint16_t expected=previous;
    do {expected=uint16_t(expected+4);} while(!sparseChannels[(expected/4)%16]);
    uint16_t counter=mtkawdl::le32(event.bytes.data());assert(counter==expected);
    uint32_t timestamp=mtkawdl::be32(event.bytes.data()+20);
    if(starts) {
     int64_t gap=int64_t(uint32_t(timestamp-previousStart))-uint16_t(counter-previous)*int64_t(mtkawdl::awUs);
     assert(gap>=-5*1024&&gap<=5*1024);
    }
    previous=counter;start=previousStart=timestamp;++starts;
   } else {
    assert(starts==ends+1);++ends;
    uint32_t duration=mtkawdl::be32(event.bytes.data()+4)-start;
    assert(duration/1024>=54&&duration/1024<=74);
   }
  }
  assert(starts>=14&&ends>=13);
 }
 // Consecutive same-channel EAWs have no idle slot to hide a correction.
 // Include a fresh PSF delivered synchronously by the native start callback.
 for(int drift:{-3000,3000}) {
  AirportMtkAwdlInterface run;init(run);run.state.baseCounter=65532;
  run.state.nativeElectionManaged=run.state.nativeParentSelected=true;
  memcpy(run.state.nativeParent,peer,6);auto &p=run.state.peers[0];
  p.used=true;p.seen=p.epoch=clockUS;p.baseCounter=65532;
  memcpy(p.mac,peer,6);memcpy(p.advertisement.master,peer,6);run.state.elect(clockUS);
  uint64_t origin=clockUS,due=0,nextSample=clockUS+10000,stop=clockUS+2700000;
  uint8_t token=1;
  auto fresh=[&]{p.epoch=uint64_t(int64_t(origin)-drift);p.seen=clockUS;run.state.elect(clockUS);};
  run.onStart=fresh;
  run.radio.onReserve=[&]{clockUS+=1000;fresh();
   run.radio.grant.request(++token,6,clockUS);due=clockUS+3000;};
  while(clockUS<stop) {
   if(clockUS>=nextSample) {fresh();nextSample=clockUS+10000;}
   if(run.radio.grant.pending&&clockUS>=due)
    assert(run.radio.grant.grant(token,6,run.radio.duration,clockUS));
   run.serviceInGate();assert(run.t.us);clockUS+=run.t.us+250;
  }
  assert(run.reserveInvalidations==0&&run.awTimeline.starts==42&&run.awTimeline.ends==41);
  unsigned starts=0,ends=0;uint16_t previous=65528;uint32_t start=0,previousStart=0;
  for(const auto &e:run.events) {
   if(e.id==41) {
    assert(starts==ends);uint16_t counter=mtkawdl::le32(e.bytes.data());
    assert(counter==uint16_t(previous+4));previous=counter;
    uint32_t timestamp=mtkawdl::be32(e.bytes.data()+20);
    if(starts) {int64_t gap=int64_t(uint32_t(timestamp-previousStart))-4*int64_t(mtkawdl::awUs);
     assert(gap>=-5*1024&&gap<=5*1024);}
    start=previousStart=timestamp;++starts;
   } else {assert(starts==ends+1);++ends;
    uint32_t duration=mtkawdl::be32(e.bytes.data()+4)-start;
    assert(duration/1024>=54&&duration/1024<=74);}
  }
 }
 // MCU sleep replaces schedule while preserving the target channel: abort stale request.
 AirportMtkAwdlInterface changed;init(changed);changed.radio.grant.cancel();
 changed.radio.onReserve=[&]{changed.state.sequence.channels[4]=44;};changed.serviceInGate();
 assert(changed.radio.aborts==1&&changed.requestedChannel==0&&changed.events.empty());
 assert(changed.reserveInvalidations==1&&(changed.reserveInvalidReason&1)&&!changed.state.clockHoldUntil);
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
