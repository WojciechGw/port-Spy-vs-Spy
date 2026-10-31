"""Coverage checks must reject incomplete traces, including duplicated packets."""
import json
from pathlib import Path
import socket
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from audit_probe_capture import audit, packets
from net_probe_peer import make_frame


def block(kind, body):
    body += b'\0' * (-len(body) % 4)
    size = len(body)+12
    return struct.pack('<II', kind, size)+body+struct.pack('<I', size)


def trace(frames, raw_ip=False):
    data = block(0x0a0d0d0a, struct.pack('<IHHq', 0x1a2b3c4d, 1, 0, -1))
    data += block(1, struct.pack('<HHI', 101 if raw_ip else 1, 0, 65535))
    for kind, seq in frames:
        src, dst = ('192.168.1.1','192.168.1.2') if kind in 'PQ' else ('192.168.1.2','192.168.1.1')
        sport, dport = (5000,6502) if kind in 'PQ' else (6502,5000)
        payload = make_frame(kind, seq, 0)
        ip = bytearray(20)
        ip[0] = 0x45
        ip[2:4] = (40+len(payload)).to_bytes(2,'big')
        ip[9] = 6
        ip[12:16], ip[16:20] = socket.inet_aton(src), socket.inet_aton(dst)
        tcp = bytearray(20)
        struct.pack_into('!HH', tcp, 0, sport, dport)
        tcp[12] = 0x50
        packet = (b'' if raw_ip else b'\0'*12+b'\x08\x00')+ip+tcp+payload
        data += block(6, struct.pack('<IIIII',0,0,0,len(packet),len(packet))+packet)
    return data


class AuditTests(unittest.TestCase):
    def evaluate(self, frames, raw_ip=False):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'packets.pcapng'
            path.write_bytes(trace(frames, raw_ip))
            report = dict(local_address=['192.168.1.1',5000], peer_address=['192.168.1.2',6502],
                          records=[dict(sample=1,span_ms=1400),dict(sample=2,span_ms=30)])
            return audit([path], report)

    def test_complete(self):
        for raw in (False, True):
            r=self.evaluate([('P',0),('R',0),('P',1),('R',1)],raw)
            self.assertTrue(r['all_completed_samples_observed'])

    def test_duplicates_do_not_fill_gaps(self):
        r=self.evaluate([('P',0),('P',0),('P',1),('R',1)])
        self.assertFalse(r['all_completed_samples_observed'])
        self.assertEqual(r['missing_reply_samples'],[1])
        self.assertEqual(r['counts']['identical_packet_copies'],1)
        self.assertFalse(r['slow_samples'][0]['reply_observed'])

    def test_both_sides_absent(self):
        r=self.evaluate([('P',1),('R',1)])
        self.assertEqual(r['missing_request_samples'],[1])
        self.assertEqual(r['missing_reply_samples'],[1])

    def test_truncated_block_fails(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'packets.pcapng'
            path.write_bytes(trace([('P',0)])[:-1])
            with self.assertRaises(ValueError): list(packets(path))


if __name__ == '__main__':
    unittest.main()
