"""Exercise production MI controls, scheduler and native RX with failure cases."""
from pathlib import Path
import subprocess, tempfile
root=Path(__file__).resolve().parents[2]
s=(root/'AirportMtkWlan/AirportMtkAwdlInterface.cpp').read_text()
def fn(sig):
 a=s.index(sig); return s[a:s.index('\n}\n',a)+3]
header=(root/'include/Airport/apple80211_ioctl.h').read_text()
structs=[]
for name in ['apple80211_awdl_af_tx_mode','apple80211_awdl_oob_request']:
 a=header.index('struct '+name+' {');b=header.index('} __attribute__((packed));',a)+len('} __attribute__((packed));')
 structs.append(header[a:b])
code=r'''
#include <cassert>
#include <cstdint>
#include <cstring>
#include <cstdio>
#include <vector>
#include <AWDL/AwdlTimeline.hpp>
#define __IO80211_TARGET __MAC_26_0
using IOReturn=unsigned;
constexpr unsigned APPLE80211_VERSION=1,kIOReturnSuccess=0,kIOReturnBadArgument=1,
 kIOReturnUnsupported=2,kIOReturnNotReady=3,kIOReturnNoMemory=4,
 APPLE80211_C_FLAG_20MHZ=1,APPLE80211_C_FLAG_2GHZ=8,APPLE80211_C_FLAG_5GHZ=16;
uint64_t clockUS=1000000;uint64_t awdlNow(){return clockUS;}
struct apple80211_channel{uint32_t version,channel,flags;};
'''+ '\n'.join(structs)+r'''
struct Timer{unsigned ms=0;void setTimeoutMS(unsigned n){ms=n;}void setTimeoutUS(unsigned n){ms=(n+999)/1000;}void cancelTimeout(){}};
struct Packet{std::vector<uint8_t> bytes;};using mbuf_t=Packet*;
void mbuf_freem(mbuf_t m){delete m;}void *mbuf_data(mbuf_t m){return m->bytes.data();}
struct IO80211Buffer{uint8_t bytes[2048]{};unsigned length=0,returned=0;
 void*getBytesNoCopy(){return bytes;}unsigned getCapacity(){return sizeof(bytes);}
 void setLength(unsigned n){length=n;}void returnBuffer(){++returned;}};
struct IO80211BufferPool{IO80211Buffer b;bool missing=false;IO80211Buffer*getBuffer(){return missing?nullptr:&b;}};
struct Hal{
 bool grant=true,on=true;IOReturn txResult=0;uint64_t observedAt=clockUS;unsigned transmitted=0;std::vector<std::vector<uint8_t>> frames;
 bool awdlIsEnabled(){return on;}void awdlAbort(){}bool awdlChannelAllowed(unsigned c){return c==6||c==149;}
 bool awdlGrantSnapshot(mtkawdl::Reservation &out){
  out={};out.granted=grant;out.channel=6;out.token=1;out.grantObservedAt=observedAt;
  out.deadline=clockUS+70000;return on;
 }
 bool awdlCanTransmit(unsigned){return grant;}IOReturn awdlReserve(unsigned,unsigned){return 0;}
 IOReturn awdlPeer(const uint8_t*,bool){return 0;}
 IOReturn awdlTransmit(mbuf_t m,unsigned){++transmitted;frames.push_back(m->bytes);delete m;return txResult;}
};
struct AirportMtkAwdlInterface{
 Hal radio;Hal*hal=&radio;Timer t;Timer*timer=&t;IO80211BufferPool pool;
 bool enabled=true,stopping=false,trafficPeerInstalled=false,trafficActive=false;
 uint8_t trafficPeer[6]{},installedTrafficPeer[6]{};
 mtkawdl::State state;mtkawdl::Timeline awTimeline;mtkawdl::Window requestedWindow{};
 struct NativePeerSample{mtkawdl::Advertisement advertisement;uint8_t peer[6];uint64_t received;bool valid;};
 NativePeerSample nativePeerSamples[16]{};unsigned nativePeerSampleNext=0;
 void notifyAvailabilityWindowStart(uint8_t,uint64_t){}
 void notifyAvailabilityWindowEnd(uint64_t){awTimeline.close();}
 apple80211_awdl_af_tx_mode afMode{};
 struct{unsigned synchronization_frame_period=440;}syncParams;
 struct{int peer_rssi_threshold=-70;}rssiThresholds;
 uint8_t miTemplate[2048]{},syncTemplate[2048]{},rejectedAction[2048]{};
 size_t miTemplateLength=0,templateLength=0,rejectedActionLength=0;
 uint64_t miStart=0,miSubmitted=0,miFailed=0;uint16_t miCounter=0;bool miCounterValid=false;
 uint64_t serviceTicks=0,reserveAttempts=0,grantObservations=0,actionSubmitted=0,actionFailed=0,
 actionReceived=0,actionHostAccepted=0,actionHostRejected=0,actionRSSIRejected=0,
 actionNativeDelivered=0,actionInvalid=0,actionNoBuffer=0,nextAction=0,requestDeadline=0;
 int32_t lastActionRSSI=0;unsigned reserveDuration=0,requestedChannel=0,grantedChannel=0;
 IOReturn reserveStatus=0,actionStatus=0,miStatus=0;mbuf_t queue[64]{};
 uint64_t dataTxSubmitted=0,dataTxFailed=0,dataTxExpired=0;IOReturn dataTxStatus=0;
 uint64_t dataRxFrames=0,dataRxInvalid=0,dataRxUnknownPeer=0,dataRxWrongDestination=0,dataRxReplay=0,dataRxDecoded=0;
 std::vector<std::vector<uint8_t>> received;
 uint64_t queueTime[64]{};unsigned queueCount=0,queueHead=0,nativeCalls=0;
 void setProperty(const char*,uint64_t,unsigned){}void setProperty(const char*,bool){}
 void setProperty(const char*,void*,unsigned){}
 void publishScheduler(uint64_t){}void inputNative(const uint8_t*f,size_t n){received.emplace_back(f,f+n);}
 mbuf_t makeFrame(const uint8_t*f,size_t n){return new Packet{{f,f+n}};}
 IO80211BufferPool*getMgmtFramePool(){return &pool;}
 void bpfTapInput(IO80211Buffer*b,unsigned type,void*meta,unsigned n){
   assert(type==12&&n==72);
   int32_t rssi;memcpy(&rssi,(uint8_t*)meta+44,4);assert(rssi==-40);
   ++nativeCalls;b->returnBuffer();
 }
 IOReturn setAWDL_AF_TX_MODE(apple80211_awdl_af_tx_mode*);
 IOReturn setAWDL_OOB_AUTO_REQUEST(apple80211_awdl_oob_request*);
 void serviceInGate();static bool receive(void*,const uint8_t*,size_t,uint8_t,int8_t);
};
'''+fn('IOReturn AirportMtkAwdlInterface::setAWDL_AF_TX_MODE(')+fn('IOReturn AirportMtkAwdlInterface::setAWDL_OOB_AUTO_REQUEST(')+fn('void AirportMtkAwdlInterface::serviceInGate(')+fn('bool AirportMtkAwdlInterface::receive(')+r'''
int main(){
 AirportMtkAwdlInterface d;const uint8_t local[]={2,1,2,3,4,5},peer[]={2,1,2,3,4,6};
 d.state.init(local,clockUS);
 static_assert(sizeof(apple80211_awdl_oob_request)==56,"Tahoe borrowed payload ABI");
 uint8_t service[]={6,9,0,0,0,0,0,0,0,0,0,0};
 uint8_t raw[56]{};mtkawdl::put32(raw,1);memset(raw+4,255,6);
 mtkawdl::put32(raw+12,24500);mtkawdl::put32(raw+16,0xffffffff);
 mtkawdl::put16(raw+40,sizeof(service));const uint8_t*ptr=service;memcpy(raw+48,&ptr,8);
 apple80211_awdl_oob_request req;memcpy(&req,raw,sizeof(req));
 assert(d.setAWDL_OOB_AUTO_REQUEST(&req)==0&&d.miTemplateLength==sizeof(service));
 assert(d.miStart==1024500);service[3]=99;assert(d.miTemplate[3]==0);service[3]=0;
 clockUS+=1000;assert(!d.setAWDL_OOB_AUTO_REQUEST(&req)&&d.miStart==1024500);
 for(unsigned bitmap:{1U,0x05050505U}){req.unk4=bitmap;assert(d.setAWDL_OOB_AUTO_REQUEST(&req)==kIOReturnUnsupported);}
 req.unk4=0xffffffff;req.data=nullptr;assert(d.setAWDL_OOB_AUTO_REQUEST(&req)==kIOReturnBadArgument);
 req.data=service;req.data_len=2049;assert(d.setAWDL_OOB_AUTO_REQUEST(&req)==kIOReturnBadArgument);
 req.data_len=sizeof(service);req.unk3=1000001;assert(d.setAWDL_OOB_AUTO_REQUEST(&req)==kIOReturnBadArgument);req.unk3=24500;
 apple80211_awdl_af_tx_mode mode{1,3};assert(!d.setAWDL_AF_TX_MODE(&mode));
 d.serviceInGate();assert(!d.radio.transmitted); // start delay, suppress PSF
 clockUS=d.miStart;d.radio.grant=false;d.serviceInGate();assert(!d.radio.transmitted);
 d.radio.grant=true;d.serviceInGate();assert(d.miSubmitted==1&&d.radio.transmitted==1);
 assert(d.radio.frames.back()[30]==3);mtkawdl::Advertisement a{};
 assert(mtkawdl::parseAction(d.radio.frames.back().data(),d.radio.frames.back().size(),a));
 d.serviceInGate();assert(d.miSubmitted==1);clockUS+=4*mtkawdl::awUs;d.serviceInGate();assert(d.miSubmitted==2);
 mode.mode=0;assert(!d.setAWDL_AF_TX_MODE(&mode));d.serviceInGate();assert(d.radio.frames.back()[30]==0);
 mode.mode=1;assert(d.setAWDL_AF_TX_MODE(&mode)==kIOReturnUnsupported&&d.afMode.mode==0);
 req.unk4=0;assert(!d.setAWDL_OOB_AUTO_REQUEST(&req)&&!d.miTemplateLength);
 d.enabled=false;unsigned before=d.radio.transmitted;d.serviceInGate();assert(d.radio.transmitted==before);
 d.enabled=true;
 mtkawdl::State remote;remote.init(peer,clockUS);uint8_t f[256];
 size_t n=mtkawdl::buildAction(remote,f,sizeof(f),clockUS);
 assert(d.receive(&d,f,n,6,-40)&&d.actionHostAccepted==1&&d.nativeCalls==1);
 // MIF supplement without sync must reach native even though host rejects it.
 memcpy(f+40,service,sizeof(service));n=40+sizeof(service);
 assert(d.receive(&d,f,n,6,-40)&&d.actionHostRejected==1&&d.nativeCalls==2);
 assert(d.rejectedActionLength==n&&d.pool.b.returned==2);
 assert(d.receive(&d,f,n,6,-90)&&d.actionRSSIRejected==1&&d.nativeCalls==2);
 f[41]=255;assert(d.receive(&d,f,n,6,-40)&&d.actionInvalid==1&&d.nativeCalls==2);
 f[41]=9;d.pool.missing=true;assert(d.receive(&d,f,n,6,-40)&&d.actionNoBuffer==1);
 // Exercise actual data RX, including hardware-deaggregated and aggregate
 // payloads, per-MSDU replay, malformed tails and destination/peer gates.
 uint8_t eth[55]{},wire[128]{};memcpy(eth,local,6);memcpy(eth+6,peer,6);
 eth[12]=0x86;eth[13]=0xdd;eth[14]=0x60;eth[19]=1;eth[54]=123;
 size_t wn=mtkawdl::encodeData(wire,sizeof(wire),eth,sizeof(eth),40);
 assert(d.receive(&d,wire,wn,6,-40)&&d.received.size()==1);
 assert(d.received.back()==std::vector<uint8_t>(eth,eth+sizeof(eth)));
 d.receive(&d,wire,wn,6,-40);assert(d.dataRxReplay==1&&d.received.size()==1);
 std::vector<uint8_t> aggregate(wire,wire+24);aggregate[0]=0x88;
 aggregate.push_back(0x80);aggregate.push_back(0);
 for(unsigned seq:{41U,42U}) {
  aggregate.insert(aggregate.end(),eth,eth+12);aggregate.push_back(0);aggregate.push_back(wn-24);
  size_t pos=aggregate.size();aggregate.insert(aggregate.end(),wire+24,wire+wn);
  mtkawdl::put16(aggregate.data()+pos+10,seq);
  if(seq==41)while((aggregate.size()-26)%4)aggregate.push_back(0);
 }
 d.receive(&d,aggregate.data(),aggregate.size(),6,-40);assert(d.received.size()==3);
 d.receive(&d,aggregate.data(),aggregate.size(),6,-40);assert(d.dataRxReplay==3);
 auto malformed=aggregate;
 // A truncated final IPv6 payload must not deliver the valid first subframe.
 malformed=aggregate;malformed.pop_back();d.receive(&d,malformed.data(),malformed.size(),6,-40);
 assert(d.dataRxInvalid==1&&d.received.size()==3);
 std::vector<uint8_t> deagg(aggregate.begin(),aggregate.begin()+26);
 deagg.push_back(0xcc);deagg.push_back(0xdd);
 deagg.insert(deagg.end(),eth,eth+12);deagg.push_back(0);deagg.push_back(wn-24);
 size_t dp=deagg.size();deagg.insert(deagg.end(),wire+24,wire+wn);
 mtkawdl::put16(deagg.data()+dp+10,43);
 assert(mtkawdl::relocateDeaggregatedHeader(deagg.data(),deagg.size()));
 deagg.erase(deagg.begin(),deagg.begin()+2);d.receive(&d,deagg.data(),deagg.size(),6,-40);
 assert(d.received.size()==4&&d.received.back()==std::vector<uint8_t>(eth,eth+sizeof(eth)));
 wire[4]^=4;d.receive(&d,wire,wn,6,-40);assert(d.dataRxWrongDestination==1);wire[4]^=4;
 wire[10]^=4;d.receive(&d,wire,wn,6,-40);assert(d.dataRxUnknownPeer==1);wire[10]^=4;
 // Successful submissions, firmware failures, expiry without any grant.
 d.afMode.mode=3;d.miTemplateLength=0;
 auto enqueue=[&](uint64_t time){unsigned tail=(d.queueHead+d.queueCount)%64;
  d.queue[tail]=d.makeFrame(wire,wn);d.queueTime[tail]=time;++d.queueCount;};
 d.state.peers[d.state.find(peer)].advertisement.sequence.channels[0]=6;
 memcpy(wire+4,peer,6);enqueue(clockUS);d.serviceInGate();assert(d.dataTxSubmitted==1&&!d.queueCount);
 d.radio.txResult=kIOReturnNotReady;enqueue(clockUS);d.serviceInGate();assert(d.dataTxFailed==1&&d.dataTxStatus==kIOReturnNotReady);
 d.radio.grant=false;enqueue(clockUS-1000000);enqueue(clockUS);d.serviceInGate();
 assert(d.dataTxExpired==1&&d.queueCount==1);mbuf_freem(d.queue[d.queueHead]);d.queueCount=0;
 // A full queue with alternating expired/live packets preserves live order.
 for(unsigned i=0;i<64;++i){wire[wn-1]=i;enqueue(clockUS-(i%2 ? 0 : 1000000));}
 d.serviceInGate();assert(d.queueCount==32&&d.dataTxExpired==33);
 for(unsigned i=0;i<32;++i)assert(d.queue[(d.queueHead+i)%64]->bytes.back()==i*2+1);
 clockUS+=1000000;d.serviceInGate();assert(!d.queueCount&&d.dataTxExpired==65);
 puts("PASS actual MI/control/RX: borrowed ABI/copy, bitmap/cancel, granted MIF, PSF modes, native discovery, data/aggregate RX, per-MSDU replay, peer/destination gates, atomic malformed-tail rejection, TX submission/failure and no-grant expiry.");
}
'''
with tempfile.TemporaryDirectory(prefix='mtk-mi-discovery-') as d:
 p=Path(d)/'test.cpp';p.write_text(code);b=Path(d)/'test'
 subprocess.run(['clang++','-std=c++14','-Wall','-Wextra','-fsanitize=address,undefined','-I'+str(root/'include'),str(p),'-o',str(b)],check=True)
 subprocess.run([str(b)],check=True)
