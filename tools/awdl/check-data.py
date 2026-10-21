#!/usr/bin/env python3
"""Observe native/BSD AWDL data counters for one explicitly selected kext UUID."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import plistlib
import re
import subprocess
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--expected-uuid', required=True)
parser.add_argument('--seconds', type=int, default=10)
parser.add_argument('--probe', action='store_true', help='Send three IPv6 all-nodes pings on awdl0')
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
if not 0 <= args.seconds <= 60:
    parser.error('--seconds must be between 0 and 60')

def run(command):
    return subprocess.check_output(command, stderr=subprocess.PIPE, timeout=45)

def snapshot():
    interfaces = plistlib.loads(run(['ioreg', '-a', '-r', '-c', 'AirportMtkAwdlInterface']))
    if len(interfaces) != 1:
        raise RuntimeError('Expected one AirportMtkAwdlInterface')
    native = {k: v for k, v in interfaces[0].items() if k.startswith('MTKAWDL')
              and isinstance(v, (int, bool, str))}
    table = run(['netstat', '-ibn', '-I', 'awdl0']).decode(errors='replace')
    row = next((line.split() for line in table.splitlines() if '<Link#' in line), None)
    if not row or len(row) < 11:
        raise RuntimeError('Missing awdl0 BSD link counters')
    bsd = dict(zip(('rx_packets', 'rx_errors', 'rx_bytes', 'tx_packets', 'tx_errors', 'tx_bytes'),
                   map(int, row[4:10])))
    return {'native': native, 'bsd': bsd}

def check():
    loaded = run(['kmutil', 'showloaded', '--list-only']).decode(errors='replace')
    identity = next((line for line in loaded.splitlines()
                     if 'com.eiyuumiru.AirportMtkWlan (' in line), '')
    result = {'time': datetime.now().astimezone().isoformat(),
              'expected_uuid': args.expected_uuid.upper(), 'loaded': identity,
              'status': 'unverified', 'reasons': []}
    if not re.search(r'\b' + re.escape(args.expected_uuid) + r'\b', identity, re.I):
        result['reasons'].append('The intended kext UUID is not loaded.')
        return result
    before = snapshot()
    if args.probe:
        probe = subprocess.run(['ping6', '-c', '3', '-i', '0.5', 'ff02::1%awdl0'],
                               capture_output=True, text=True, timeout=10)
        result['probe'] = {'exit_code': probe.returncode, 'stdout': probe.stdout, 'stderr': probe.stderr}
    time.sleep(args.seconds)
    after = snapshot()
    result.update(before=before, after=after)
    keys = ('MTKAWDLNativeTxPackets', 'MTKAWDLNativeRxPackets', 'MTKAWDLNativeDroppedPackets')
    missing = [key for key in keys if key not in before['native'] or key not in after['native']]
    delta = {key: after['native'].get(key, 0) - before['native'].get(key, 0) for key in keys}
    bsd_delta = {key: after['bsd'][key] - before['bsd'][key] for key in before['bsd']}
    result.update(native_delta=delta, bsd_delta=bsd_delta, missing_counters=missing)
    if not after['native'].get('MTKAWDLDataPathEnabled', False):
        result['reasons'].append('The native datapath is disabled or its diagnostic is absent.')
    if missing:
        result['reasons'].append('This loaded build does not expose all native data counters.')
    if any(value < 0 for value in (*delta.values(), *bsd_delta.values())):
        result['reasons'].append('Counters reset during observation.')
    if delta['MTKAWDLNativeTxPackets'] <= 0 or bsd_delta['tx_packets'] <= 0:
        result['reasons'].append('No new native/BSD TX was observed.')
    if delta['MTKAWDLNativeRxPackets'] <= 0 or bsd_delta['rx_packets'] <= 0:
        result['reasons'].append('No new native/BSD RX was observed.')
    result['limitations'] = ['Local multicast ping replies do not prove RF traffic.',
                            'Native TX counts accepted protocol frames, not firmware ACKs.',
                            'Data counters do not validate an AirDrop file transfer.']
    if not result['reasons']:
        result['status'] = 'passed'
    return result

try:
    result = check()
except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, plistlib.InvalidFileException) as exc:
    result = {'status': 'unverified', 'reasons': [str(exc)]}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
raise SystemExit(0 if result['status'] == 'passed' else 1)
