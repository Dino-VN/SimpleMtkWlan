#!/usr/bin/env python3
"""Check compiler-generated packet/pool/queue virtual slots against the disk KC.

The short headers are declarations for borrowed native objects. Compare their
complete declared prefix, omitting constructor/destructor/metaclass probes.
"""
from pathlib import Path
import importlib.util,re,struct,subprocess,shlex,tempfile,hashlib,argparse
root=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('abi',root/'tests/awdl-abi/check.py');abi=importlib.util.module_from_spec(spec);spec.loader.exec_module(abi)
data=Path('/System/Library/KernelCollections/BootKernelExtensions.kc').read_bytes()
if hashlib.sha256(data).hexdigest()!='21d6da1c4c3e7b72dddf5144da8a4c4b48e294249a16018a5006b61bb2155ccc':
 raise ValueError('Pinned Tahoe KC changed; refresh native evidence and symbols first')
segments=[]
for c,p,_ in abi.commands(data):
 if c!=0x80000035:continue
 _,h,_,_=struct.unpack_from('<QQII',data,p+8)
 for c,p,_ in abi.commands(data,h):
  if c==0x19:
   _,a,_,o,n=struct.unpack_from('<16sQQQQ',data,p+8)
   if n:segments.append((a,o,n))
symbols={}
for line in (root/'build/awdl-panic-kc-symbols.txt').read_text().splitlines():
 m=re.match(r'^([0-9a-fA-F]{16})\s+\S\s+(\S+)$',line)
 if m:symbols[int(m[1],16)]=m[2]
addresses={n:a for a,n in symbols.items()}

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--objroot',type=Path,default=root/'build/awdl-native-v5/obj')
opts=parser.parse_args()
responses=list(opts.objroot.rglob('*common-args.resp'))
if not responses:raise ValueError('Build AirportMtkWlan before running native ABI test')
args=shlex.split(responses[0].read_text())
sdk=subprocess.check_output(['xcrun','--sdk','macosx','--show-sdk-path'],text=True,env={**__import__('os').environ,'DEVELOPER_DIR':'/Applications/Xcode.app/Contents/Developer'}).strip()
with tempfile.TemporaryDirectory(prefix='mtk-native-abi-') as temp:
 obj=Path(temp)/'probe.o'
 subprocess.run(['/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin/clang++']+args+['-isysroot',sdk,'-include','SimpleMtkWlan/PrivateSPI.pch','-c',str(root/'tests/awdl-abi/native-probe.cpp'),'-o',str(obj)],cwd=root,check=True)
 object_data=obj.read_bytes()
sections=[];symtab=None
for c,p,_ in abi.commands(object_data):
 if c==0x19:
  for i in range(struct.unpack_from('<I',object_data,p+64)[0]):
   q=p+72+i*80
   sections.append(struct.unpack_from('<16s16sQQIIIII',object_data,q))
 if c==2:symtab=struct.unpack_from('<IIII',object_data,p+8)
so,n,st,_=symtab
object_symbols=[]
for i in range(n):
 idx,kind,sec,desc,value=struct.unpack_from('<IBBHQ',object_data,so+i*16)
 object_symbols.append((abi.string_at(object_data,st+idx),value,kind))
pairs={'PacketProbe':('IOSkywalkPacket',0x1e0),'PoolProbe':('IOSkywalkPacketBufferPool',0x198),'QueueProbe':('IOSkywalkPacketQueue',0x290),'TxProbe':('IOSkywalkTxSubmissionQueue',0x2a8),'TxCompProbe':('IOSkywalkTxCompletionQueue',0x2b0),'RxCompProbe':('IOSkywalkRxCompletionQueue',0x2b0)}
checked=0
for probe,(native,last) in pairs.items():
 start=next(v for n,v,k in object_symbols if n==f'__ZTV{len(probe)}{probe}')
 a=addresses[f'__ZTV{len(native)}{native}'];seg=next(s for s in segments if s[0]<=a<s[0]+s[2]);offset=seg[1]+a-seg[0]
 seen=set()
 for _,_,sa,size,off,align,reloc,count,flags in sections:
  for i in range(count):
   ro,bits=struct.unpack_from('<II',object_data,reloc+i*8)
   slot=sa+ro-start-16
   if not 0x118<=slot<=last:continue
   candidate=object_symbols[bits&0xffffff][0]
   if 'Probe' in candidate:continue
   pointer=struct.unpack_from('<Q',data,offset+16+slot)[0]
   symbol=symbols.get(0xffffff8000100000+(pointer&0x3fffffff),'')
   if candidate!=symbol:raise ValueError(f'{probe} slot {slot:#x}: {candidate} != {symbol}')
   seen.add(slot);checked+=1
 if not seen:raise ValueError('No slots checked for '+probe)
 print(probe,len(seen),'slots')
print(f'PASS {checked} compiler packet/pool/queue slots match the pinned Tahoe KC (static ABI only).')
