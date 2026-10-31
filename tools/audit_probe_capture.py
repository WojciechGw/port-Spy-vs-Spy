"""Conservative coverage check for probe PCAPNG: never infer loss from omissions.

Counts validated complete probe frames contained in individual TCP payloads.
TCP stream reassembly is intentionally not performed; a fragmented frame
therefore cannot establish coverage. Duplicate capture records are not labelled
as retransmissions. Accepts Ethernet/IPv4 captures produced by Windows PktMon.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import socket
import struct

from net_probe_peer import check_frame, ProbeError


def packets(path):
    data = path.read_bytes()
    offset = 0
    endian = '<'
    interfaces = []
    while offset < len(data):
        if len(data)-offset < 12:
            raise ValueError('Truncated PCAPNG block')
        if data[offset:offset+4] == b'\x0a\x0d\x0d\x0a':
            magic = data[offset+8:offset+12]
            if magic not in (b'\x4d\x3c\x2b\x1a', b'\x1a\x2b\x3c\x4d'):
                raise ValueError('Invalid PCAPNG byte order')
            endian = '<' if magic == b'\x4d\x3c\x2b\x1a' else '>'
            interfaces = []
        kind, size = struct.unpack_from(endian+'II', data, offset)
        if size < 12 or size % 4 or offset+size > len(data):
            raise ValueError('Invalid PCAPNG block size')
        if struct.unpack_from(endian+'I', data, offset+size-4)[0] != size:
            raise ValueError('PCAPNG block length mismatch')
        body = data[offset+8:offset+size-4]
        if kind == 1:
            if len(body) < 8:
                raise ValueError('Short interface block')
            interfaces.append(struct.unpack_from(endian+'H', body)[0])
        elif kind == 6:
            if len(body) < 20:
                raise ValueError('Short packet block')
            interface, _, _, captured, original = struct.unpack_from(endian+'IIIII', body)
            if interface >= len(interfaces) or captured > len(body)-20:
                raise ValueError('Invalid packet block')
            yield interfaces[interface], body[20:20+captured], original
        offset += size


def tcp(raw):
    if len(raw) < 14:
        return None
    pos = 14
    ethertype = int.from_bytes(raw[12:14], 'big')
    while ethertype in (0x8100, 0x88a8):
        if len(raw) < pos+4: return None
        ethertype = int.from_bytes(raw[pos+2:pos+4], 'big')
        pos += 4
    if ethertype != 0x0800 or len(raw) < pos+20:
        return None
    ip = raw[pos:]
    ihl = (ip[0] & 15)*4
    total = int.from_bytes(ip[2:4], 'big')
    if ip[0] >> 4 != 4 or ihl < 20 or total > len(ip) or total < ihl+20:
        return None
    if ip[9] != 6 or int.from_bytes(ip[6:8], 'big') & 0x3fff:
        return None
    segment = ip[ihl:total]
    header = (segment[12] >> 4)*4
    if header < 20 or header > len(segment): return None
    sport, dport = struct.unpack_from('!HH', segment)
    return (socket.inet_ntoa(ip[12:16]), sport, socket.inet_ntoa(ip[16:20]), dport), segment[header:]


def audit(paths, report):
    local_ip, local_port = report['local_address']
    peer_ip, peer_port = report['peer_address']
    forward = (local_ip, local_port, peer_ip, peer_port)
    reverse = (peer_ip, peer_port, local_ip, local_port)
    seen = {kind: set() for kind in 'PRQA'}
    counts = Counter()
    raw_seen = set()
    for path in paths:
        for link, raw, original in packets(path):
            counts['packet_records'] += 1
            if len(raw) < original: counts['truncated_records'] += 1
            if link not in (1, 101):
                counts['unsupported_link_records'] += 1
                continue
            decoded = tcp(raw if link == 1 else b'\0'*12+b'\x08\x00'+raw)
            if decoded is None or decoded[0] not in (forward, reverse): continue
            counts['connection_records'] += 1
            if raw in raw_seen: counts['identical_packet_copies'] += 1
            raw_seen.add(raw)
            endpoints, payload = decoded
            if not payload: continue
            found = 0
            for i in range(len(payload)-31):
                if payload[i:i+4] != b'\xa5\x5aN\x01': continue
                try:
                    kind, seq, _ = check_frame(payload[i:i+32])
                except ProbeError:
                    continue
                expected_direction = forward if kind in 'PQ' else reverse
                if endpoints != expected_direction: continue
                seen[kind].add(seq)
                counts[kind+'_records'] += 1
                found += 1
            if not found: counts['payload_without_complete_frame'] += 1
    expected = {row['sample']-1 for row in report['records']}
    missing = {kind: sorted(n+1 for n in expected-seen[kind]) for kind in 'PR'}
    result = dict(counts=dict(counts), unique_frames={k:len(v) for k,v in seen.items()},
                  missing_request_samples=missing['P'], missing_reply_samples=missing['R'],
                  all_completed_samples_observed=bool(expected) and not any(missing.values()),
                  slow_samples=[dict(sample=r['sample'], rtt_ms=r['span_ms'],
                       request_observed=r['sample']-1 in seen['P'],
                       reply_observed=r['sample']-1 in seen['R'])
                       for r in report['records'] if r['span_ms'] > 200],
                  sources=[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in paths],
                  limitation='Full frames in single TCP payloads only; no reassembly. '
                    'Missing capture records do not prove network packet loss. '
                    'Identical packet copies do not prove retransmission.')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture_directory', type=Path)
    args = parser.parse_args()
    folder = args.capture_directory
    report = json.loads((folder/'probe.json').read_text(encoding='utf-8'))
    paths = sorted(folder.glob('packets*.pcapng'))
    if not paths:
        parser.error('no packets*.pcapng files')
    result = audit(paths, report)
    (folder/'coverage.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if not k.startswith('missing_')},indent=2))


if __name__ == '__main__':
    main()
