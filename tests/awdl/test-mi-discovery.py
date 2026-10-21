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
#include <AWDL/AwdlProtocol.hpp>
#define __IO80211_TARGET __MAC_26_0
using IOReturn=unsigned;
constexpr unsigned APPLE80211_VERSION=1,kIOReturnSuccess=0,kIOReturnBadArgument=1,
 kIOReturnUnsupported=2,kIOReturnNotReady=3,kIOReturnNoMemory=4,
 APPLE80211_C_FLAG_20MHZ=1,APPLE80211_C_FLAG_2GHZ=8,APPLE80211_C_FLAG_5GHZ=16;
uint64_t clockUS=1000000;uint64_t awdlNow(){return clockUS;}
struct apple80211_channel{uint32_t version,channel,flags;};
'''+ '\n'.join(structs)+r'''
struct Timer{unsigned ms=0;void setTimeoutMS(unsigned n){ms=n;}void cancelTimeout(){}};
struct Packet{std::vector<uint8_t> bytes;};using mbuf_t=Packet*;
void mbuf_freem(mbuf_t m){delete m;}void *mbuf_data(mbuf_t m){return m->bytes.data();}
struct IO80211Buffer{uint8_t bytes[2048]{};unsigned length=0,returned=0;
 void*getBytesNoCopy(){return bytes;}unsigned getCapacity(){return sizeof(bytes);}
 void setLength(unsigned n){length=n;}void returnBuffer(){++returned;}};
struct IO80211BufferPool{IO80211Buffer b;bool missing=false;IO80211Buffer*getBuffer(){return missing?nullptr:&b;}};
struct Hal{
 bool grant=true,on=true;unsigned transmitted=0;std::vector<std::vector<uint8_t>> frames;
 bool awdlIsEnabled(){return on;}void awdlAbort(){}bool awdlChannelAllowed(unsigned c){return c==6||c==149;}
 bool awdlCanTransmit(unsigned){return grant;}IOReturn awdlReserve(unsigned,unsigned){return 0;}
 IOReturn awdlPeer(const uint8_t*,bool){return 0;}
 IOReturn awdlTransmit(mbuf_t m,unsigned){++transmitted;frames.push_back(m->bytes);delete m;return 0;}
};
struct AirportMtkAwdlInterface{
 Hal radio;Hal*hal=&radio;Timer t;Timer*timer=&t;IO80211BufferPool pool;
 bool enabled=true,stopping=false,trafficPeerInstalled=false,trafficActive=false;
 uint8_t trafficPeer[6]{},installedTrafficPeer[6]{};
 mtkawdl::State state;
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
 uint64_t queueTime[64]{};unsigned queueCount=0,queueHead=0,nativeCalls=0;
 void setProperty(const char*,uint64_t,unsigned){}void setProperty(const char*,bool){}
 void setProperty(const char*,void*,unsigned){}
 void publishScheduler(uint64_t){}void inputNative(const uint8_t*,size_t){}
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
 puts("PASS actual MI/control/RX: borrowed ABI/copy, bitmap validation/cancel, unchanged refresh, delayed granted-only MIF, EAW rate, PSF suppress/allow, native discovery independent of host sync parser, RSSI/framing rejects and buffer ownership.");
}
'''
with tempfile.TemporaryDirectory(prefix='mtk-mi-discovery-') as d:
 p=Path(d)/'test.cpp';p.write_text(code);b=Path(d)/'test'
 subprocess.run(['clang++','-std=c++14','-Wall','-Wextra','-fsanitize=address,undefined','-I'+str(root/'include'),str(p),'-o',str(b)],check=True)
 subprocess.run([str(b)],check=True)
