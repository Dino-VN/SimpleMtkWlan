from pathlib import Path
import subprocess,re
root=Path(__file__).resolve().parents[2]
out=Path(__file__).resolve().parent
s=(root/'SimpleMtkWlan/hal_mwx/MtkMwx.cpp').read_text()
a=s.index('static inline void delay(int usec) {');delay=s[a:s.index('\n}',a)+2]
u=(root/'SimpleMtkWlan/MtkWlanUserClient.cpp').read_text();a=u.index('IOReturn MtkWlanUserClient::externalMethod(');fn=u[a:u.index('\nIOReturn MtkWlanUserClient::',a+10)]
common=(root/'include/ClientKit/Common.h').read_text()
wire='\n'.join(re.search(r'struct '+name+r' \{.*?\n\};',common,re.S).group() for name in ('ioctl_debug','ioctl_debug_set','ioctl_log'))
wire=re.search(r'#define MTK_LOG_CHUNK \d+',common).group()+'\n'+wire
pre=r'''
#include <cstdint>
#include <cassert>
#include <cstdio>
#include <ClientKit/IoctlId.h>
long micros;void IODelay(int n){micros+=n;}void IOSleep(int n){micros+=n*1000;}
#define IOCTL_MASK 0x800000
#define super Base
using IOReturn=int;const int kIOReturnError=4,kIOReturnBadArgument=5;
struct OSObject{};struct IOExternalMethodDispatch{};
struct IOExternalMethodArguments{const void*structureInput;void*structureOutput;size_t structureInputSize,structureOutputSize;};
struct Base:OSObject{int externalMethod(uint32_t,IOExternalMethodArguments*,IOExternalMethodDispatch*,OSObject*,void*){return 9;}};
struct MtkWlanUserClient:Base{static int(*sMethods[IOCTL_ID_MAX])(OSObject*,void*,bool);int externalMethod(uint32_t,IOExternalMethodArguments*,IOExternalMethodDispatch*,OSObject*,void*);};
int(*MtkWlanUserClient::sMethods[IOCTL_ID_MAX])(OSObject*,void*,bool)={};
int calls;int valid(OSObject*,void*,bool){calls++;return 0;}
'''
post=r'''
int main(){
 micros=0;for(int i=0;i<5000;i++)delay(10);assert(micros==50000);
 micros=0;delay(0);delay(-1);assert(micros==0);delay(1);delay(999);assert(micros==1000);delay(1000);delay(1001);assert(micros==4000);
 MtkWlanUserClient u;char data[sizeof(ioctl_log)]={};IOExternalMethodArguments args{data,data,sizeof(data),sizeof(data)};for(auto&f:u.sMethods)f=valid;
 for(uint32_t set=0;set<=1;set++){
  for(uint32_t i=0;i<IOCTL_ID_MAX;i++)assert(u.externalMethod(i|(set?IOCTL_MASK:0),&args,nullptr,nullptr,nullptr)==0);
  assert(u.externalMethod(IOCTL_ID_MAX|(set?IOCTL_MASK:0),&args,nullptr,nullptr,nullptr)==9);
  assert(u.externalMethod((IOCTL_ID_MAX+1)|(set?IOCTL_MASK:0),&args,nullptr,nullptr,nullptr)==9);
 }
 assert(u.externalMethod(UINT32_MAX,&args,nullptr,nullptr,nullptr)==9);assert(calls==2*IOCTL_ID_MAX);
 int before=calls;args.structureOutputSize=sizeof(ioctl_debug)-1;
 assert(u.externalMethod(IOCTL_80211_DEBUG,&args,nullptr,nullptr,nullptr)==kIOReturnBadArgument);
 args.structureInputSize=sizeof(ioctl_debug_set)-1;
 assert(u.externalMethod(IOCTL_80211_DEBUG|IOCTL_MASK,&args,nullptr,nullptr,nullptr)==kIOReturnBadArgument);
 args.structureOutputSize=sizeof(ioctl_log)-1;
 assert(u.externalMethod(IOCTL_80211_LOG,&args,nullptr,nullptr,nullptr)==kIOReturnBadArgument&&calls==before);
 args.structureOutputSize=sizeof(ioctl_log);assert(!u.externalMethod(IOCTL_80211_LOG,&args,nullptr,nullptr,nullptr));
 puts("PASS real delay timing and real dispatch bounds, including masked selectors at/end/beyond table.");}
'''
p=out/'test-basics.cpp';p.write_text(pre+wire+'\n'+delay+'\n'+fn+'\n'+post)
subprocess.run(['clang++','-std=c++14','-fsanitize=address,undefined','-I'+str(root/'include'),str(p),'-o',str(p.with_suffix(''))],check=True)
subprocess.run([str(p.with_suffix(''))],check=True)
