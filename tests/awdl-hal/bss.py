"""Check the real device/BSS constructor against MT76 wire constants.

The mocked transport tests ordering, failure containment and isolation from
infrastructure. It cannot establish firmware acceptance of a P2P context.
"""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parents[2]
source = (Path(sys.argv[1]) if len(sys.argv) > 1 else
          root / 'SimpleMtkWlan/hal_mwx/MtkMwx.cpp').read_text()
wire = (root / 'SimpleMtkWlan/hal_mwx/if_mwxreg.h').read_text()
begin = source.index('int\nmt7921_mcu_uni_add_dev(')
function = source[begin:source.index('\n}\n', begin) + 3]
basic = re.search(r'struct mt76_connac_bss_basic_tlv \{.*?\} __packed;', wire, re.S).group()
code = r'''
#include <cassert>
#include <cerrno>
#include <cstdint>
#include <cstring>
#include <cstdio>
#include <cstdlib>
#include <vector>
#include <AWDL/AwdlProtocol.hpp>
#define __packed __attribute__((packed))
#define htole16(x) (x)
#define htole32(x) (x)
#define IEEE80211_ADDR_LEN 6
#define ETHER_ADDR_LEN 6
#define DEV_INFO_ACTIVE 0
#define UNI_BSS_INFO_BASIC 0
#define MCU_UNI_CMD_DEV_INFO_UPDATE 0x20001
#define MCU_UNI_CMD_BSS_INFO_UPDATE 0x20002
#define STA_TYPE_STA 1
#define STA_TYPE_AP 2
#define STA_TYPE_ADHOC 4
#define NETWORK_INFRA (1U << 16)
#define NETWORK_P2P (1U << 17)
#define NETWORK_IBSS (1U << 18)
#define PHY_TYPE_BIT_HR_DSSS 1
#define PHY_TYPE_BIT_ERP 2
#define IEEE80211_M_MONITOR 0
#define IEEE80211_M_HOSTAP 1
#define IEEE80211_M_STA 2
#define IEEE80211_M_IBSS 3
#define EXT_BSSID_START 16
#define HW_BSSID_0 0
#define DEVNAME(sc) "test"
#define printf(...) ((void)0)
#define panic(...) abort()
struct mwx_node { uint16_t wcid; };
struct mwx_vif { uint8_t idx, omac_idx, band_idx, wmm_idx; };
struct mwx_softc {
    struct { int ic_opmode; uint8_t ic_myaddr[6]; } sc_ic;
    mwx_vif sc_awdl_vif;
    uint32_t sc_awdl_epoch;
    uint8_t sc_awdl_address[6];
};
struct Packet { int cmd; bool checked; std::vector<uint8_t> bytes; };
std::vector<Packet> sent;
int fail_at = 0;
bool interrupt_wait = false;
int capture(mwx_softc *sc, int cmd, void *data, int length, bool checked) {
    auto *p = static_cast<uint8_t *>(data);
    sent.push_back({cmd, checked, {p, p + length}});
    if (interrupt_wait) ++sc->sc_awdl_epoch;
    return int(sent.size()) == fail_at ? EIO : 0;
}
int mwx_send_assoc_status(mwx_softc *sc, int cmd, void *p, int n) {
    return capture(sc, cmd, p, n, true);
}
int mwx_mcu_send_wait(mwx_softc *sc, int cmd, void *p, int n) {
    return capture(sc, cmd, p, n, false);
}
''' + basic + '\n' + function + r'''
int main() {
    mwx_softc sc{{IEEE80211_M_STA, {2,1,2,3,4,5}}, {1,1,0,1}, 7,
                {2,1,2,3,4,0x85}};
    mwx_node broadcast{18};
    // MT76 creates NL80211_IFTYPE_P2P_DEVICE as AP|P2P but leaves
    // conn_state=1, BSSID and PHY fields zero. This is a discovery device,
    // not the connected AP BSS configured by uni_add_bss/start_ap.
    std::vector<uint8_t> dev = {1,0,0,0,0,0,12,0,1,0,2,1,2,3,4,0x85};
    std::vector<uint8_t> bss = {1,0,0,0,0,0,32,0,1,1,1,0,2,0,2,0,
        1,1,0,0,0,0,0,0,18,0,0,0,0,0,18,0,0,0,0,0};
    for (bool enable : {true, false}) {
        sent.clear();
        assert(!mt7921_mcu_uni_add_dev(&sc, &sc.sc_awdl_vif, &broadcast, enable));
        assert(sent.size() == 2 && sent[0].checked && sent[1].checked);
        dev[8] = bss[8] = enable;
        assert(sent[enable ? 0 : 1].cmd == 0x20001);
        assert(sent[enable ? 1 : 0].cmd == 0x20002);
        assert(sent[enable ? 0 : 1].bytes == dev);
        assert(sent[enable ? 1 : 0].bytes == bss);
    }
    for (bool enable : {true, false}) for (int failure : {1,2}) {
        sent.clear(); fail_at = failure;
        assert(mt7921_mcu_uni_add_dev(&sc, &sc.sc_awdl_vif, &broadcast, enable) == EIO);
        assert(sent.size() == unsigned(failure));
    }
    fail_at = 0; sent.clear(); interrupt_wait = true;
    assert(mt7921_mcu_uni_add_dev(&sc, &sc.sc_awdl_vif, &broadcast, 1) == ECANCELED);
    assert(sent.size() == 1); interrupt_wait = false;
    // The infrastructure constructor retains its original STA/INFRA context,
    // address, plain wait API and ordering, even with AWDL state present.
    mwx_vif infrastructure{0,0,0,0}; mwx_node station{19};
    sent.clear();
    assert(!mt7921_mcu_uni_add_dev(&sc, &infrastructure, &station, 1));
    assert(sent.size() == 2 && !sent[0].checked && !sent[1].checked);
    auto &infra = sent[1].bytes;
    assert(mtkawdl::le32(infra.data()+12) == 0x10001);
    assert(infra[16] == 1 && infra[29] == 0 && infra[8] == 1);
    assert(!memcmp(sent[0].bytes.data()+10, sc.sc_ic.ic_myaddr, 6));
    for (unsigned i=18; i<24; ++i) assert(infra[i] == 0);
    puts("PASS real device/BSS builder: disconnected MT76 P2P discovery wire packets, enable/disable ordering, both transport failures, interrupted wait, unchanged infrastructure context. Firmware acceptance unverified.");
}
'''
with tempfile.TemporaryDirectory(prefix='mtk-awdl-bss-') as tmp:
    cpp = Path(tmp) / 'test.cpp'
    binary = Path(tmp) / 'test'
    cpp.write_text(code)
    subprocess.run(['clang++', '-std=c++14', '-Wall', '-Wextra',
                    '-fsanitize=address,undefined', '-I' + str(root / 'include'),
                    str(cpp), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
