"""PC peer tests: real loopback TCP, fault injection and Pico C wire vectors."""
import binascii
from concurrent.futures import ThreadPoolExecutor
import csv
import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import net_probe_peer as peer


def report():
    return {'records': []}


class FragmentedSocket:
    def __init__(self, parts):
        self.parts = iter(parts)

    def settimeout(self, timeout):
        if timeout <= 0:
            raise AssertionError('deadline must be positive')

    def recv(self, count):
        return next(self.parts)


class PeerTests(unittest.TestCase):
    def test_c_wire_vectors(self):
        fallback = Path.home() / '.rp6502/cc65/bin'
        cl65 = shutil.which('cl65') or str(fallback / 'cl65.exe')
        sim65 = shutil.which('sim65') or str(fallback / 'sim65.exe')
        if not Path(cl65).is_file() or not Path(sim65).is_file():
            self.skipTest('cc65/sim65 not installed; run on build machine for C interoperability')
        # Compile copies so cc65 cannot leave .o files in source directories.
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            for src in ('tests/net_probe_vectors.c', 'src/net-probe/protocol.c', 'src/net-probe/protocol.h'):
                shutil.copyfile(ROOT / src, tmp / Path(src).name)
            binary = tmp / 'vectors'
            subprocess.run([cl65, '-t', 'sim6502', '-o', str(binary),
                            'net_probe_vectors.c', 'protocol.c'], cwd=tmp, check=True,
                           capture_output=True)
            lines = subprocess.check_output([sim65, str(binary)], text=True).splitlines()
        values = [('P', 0, 0), ('P', 299, 0xffffffff), ('Q', 300, 0x12345678),
                  ('R', 255, 65536), ('A', 300, 42)]
        self.assertEqual(lines, [peer.make_frame(*v).hex() for v in values])
        self.assertEqual(binascii.crc_hqx(b'123456789', 0xffff), 0x29b1)

    def test_fragmentation_and_coalescing(self):
        frame = peer.make_frame('P', 0, 7)
        for size in (1, 7, 32):
            conn = FragmentedSocket([frame[i:i+size] for i in range(0, 32, size)])
            self.assertEqual(peer.receive_frame(conn, 1)[0], frame)
        # The second frame must remain in the socket, not be discarded.
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen()
            with socket.create_connection(listener.getsockname()) as sender:
                conn, _ = listener.accept()
                with conn:
                    sender.sendall(frame + frame)
                    self.assertEqual(peer.receive_frame(conn, 1)[0], frame)
                    self.assertEqual(peer.receive_frame(conn, 1)[0], frame)

    def test_truncation_and_timeout(self):
        with self.assertRaisesRegex(peer.ProbeError, 'PEER CLOSED.*3/32'):
            peer.receive_frame(FragmentedSocket([b'abc', b'']), 1)
        with self.assertRaisesRegex(peer.ProbeError, 'FRAME TIMEOUT'):
            peer.receive_frame(FragmentedSocket([]), 0)

    def test_bad_crc_payload_and_header(self):
        for offset in (0, 5, 20, 30):
            frame = bytearray(peer.make_frame('P', 3, 5))
            frame[offset] ^= 1
            with self.assertRaisesRegex(peer.ProbeError, 'CRC/HEADER'):
                peer.check_frame(frame)
        frame = bytearray(peer.make_frame('P', 3, 5))
        frame[20] ^= 1
        frame[30:] = binascii.crc_hqx(frame[:30], 0xffff).to_bytes(2, 'little')
        with self.assertRaisesRegex(peer.ProbeError, 'PAYLOAD'):
            peer.check_frame(frame)
        frame = bytearray(peer.make_frame('P', 3, 5))
        frame[4] = 255
        frame[30:] = binascii.crc_hqx(frame[:30], 0xffff).to_bytes(2, 'little')
        with self.assertRaisesRegex(peer.ProbeError, 'TYPE'):
            peer.check_frame(frame)

    def test_loopback_300_and_saved_phases(self):
        dial, listen = report(), report()
        with socket.socket() as server, ThreadPoolExecutor(max_workers=1) as pool:
            server.bind(('127.0.0.1', 0))
            server.listen()
            def accept():
                conn, _ = server.accept()
                with conn:
                    peer.measure(conn, 'listen', 300, 2, listen)
            future = pool.submit(accept)
            with socket.create_connection(server.getsockname()) as conn:
                peer.measure(conn, 'dial', 300, 2, dial)
            future.result(timeout=5)
        for data in (dial, listen):
            self.assertEqual([r['sample'] for r in data['records']], list(range(1, 301)))
            self.assertIsNone(data['pending_sample'])
            for row in data['records']:
                phases = sum(row[k] or 0 for k in ('tx_ms', 'wait_ms', 'rx_ms', 'other_ms', 'prep_ms'))
                self.assertAlmostEqual(row['span_ms'], phases, places=6)
            with tempfile.TemporaryDirectory() as directory:
                paths = peer.write_reports(Path(directory)/'results', data)
                self.assertEqual(len(json.loads(paths[0].read_text())['records']), 300)
                with paths[1].open(newline='') as stream:
                    self.assertEqual(len(list(csv.DictReader(stream))), 300)

    def test_wrong_reply_preserves_completed_samples(self):
        data = report()
        with socket.socket() as server, ThreadPoolExecutor(max_workers=1) as pool:
            server.bind(('127.0.0.1', 0))
            server.listen()
            def accept():
                conn, _ = server.accept()
                with conn:
                    for n in range(2):
                        request, _ = peer.receive_frame(conn, 2)
                        _, seq, stamp = peer.check_frame(request)
                        conn.sendall(peer.make_frame('R', seq + n, stamp))
            future = pool.submit(accept)
            with socket.create_connection(server.getsockname()) as conn:
                with self.assertRaisesRegex(peer.ProbeError, 'REPLY SEQUENCE'):
                    peer.measure(conn, 'dial', 3, 2, data)
            future.result(timeout=5)
        self.assertEqual(len(data['records']), 1)
        self.assertEqual(data['pending_sample'], 2)

    def test_cli_loopback(self):
        with tempfile.TemporaryDirectory() as directory:
            # Reserve a free port, then let the CLI bind it. The ready line
            # is printed after listen(), so no sleeps or connect retries.
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
            cmd = [sys.executable, str(ROOT/'tools/net_probe_peer.py')]
            server = subprocess.Popen(cmd + ['listen', '--bind', '127.0.0.1', '--port', str(port),
                                            '--output', str(Path(directory)/'listen')],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                self.assertIn('SPY PC', server.stdout.readline())
                self.assertIn('Connection limit', server.stdout.readline())
                self.assertIn('Listening on', server.stdout.readline())
                client = subprocess.run(cmd + ['dial', '--host', '127.0.0.1', '--port', str(port),
                                               '--samples', '3', '--output', str(Path(directory)/'dial')],
                                        capture_output=True, text=True, timeout=10)
                stdout, stderr = server.communicate(timeout=10)
                self.assertEqual(client.returncode, 0, client.stderr + client.stdout)
                self.assertEqual(server.returncode, 0, stderr + stdout)
                for name in ('dial', 'listen'):
                    saved = json.loads((Path(directory)/(name+'.json')).read_text())
                    self.assertTrue(saved['passed'])
                    self.assertEqual(len(saved['records']), 3)
            finally:
                if server.poll() is None:
                    server.kill()
                    server.communicate()

    def test_cli_rejects_bad_arguments(self):
        for args in (['dial'], ['dial', '--host', 'x'], ['listen', '--port', '0'],
                     ['listen', '--samples', '301']):
            result = subprocess.run([sys.executable, str(ROOT/'tools/net_probe_peer.py'), *args],
                                    capture_output=True, timeout=5)
            self.assertEqual(result.returncode, 2)


if __name__ == '__main__':
    unittest.main()
