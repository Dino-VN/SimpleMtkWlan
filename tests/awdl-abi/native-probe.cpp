#include <Airport/macOS26/IOSkywalkPacketQueue.h>
class PacketProbe : public IOSkywalkPacket { public: ~PacketProbe(); };
PacketProbe::~PacketProbe() {}
class PoolProbe : public IOSkywalkPacketBufferPool { public: ~PoolProbe(); };
PoolProbe::~PoolProbe() {}
class QueueProbe : public IOSkywalkPacketQueue { public: ~QueueProbe(); unsigned getPacketCount() const override {return 0;} };
QueueProbe::~QueueProbe() {}
class TxProbe : public IOSkywalkTxSubmissionQueue { public: ~TxProbe(); };
TxProbe::~TxProbe() {}
class TxCompProbe : public IOSkywalkTxCompletionQueue { public: ~TxCompProbe(); };
TxCompProbe::~TxCompProbe() {}
class RxCompProbe : public IOSkywalkRxCompletionQueue { public: ~RxCompProbe(); };
RxCompProbe::~RxCompProbe() {}
