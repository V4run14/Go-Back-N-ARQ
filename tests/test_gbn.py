import io
import os
import socket
import threading
import time
import contextlib
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, mock

# Make go_back_n importable when tests are run from repo root
ROOT = Path(__file__).resolve().parents[1]
GBN_PATH = ROOT / "go_back_n"
import sys

if str(GBN_PATH) not in sys.path:
    sys.path.insert(0, str(GBN_PATH))

from client import Client  # noqa: E402
from server import Server  # noqa: E402


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _run_server(server: Server):
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()


class GoBackNTests(TestCase):
    def test_transfer_no_loss(self):
        with TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            infile = tmpdir / "in.txt"
            outfile = tmpdir / "out.txt"
            data = b"hello-go-back-n" * 4
            infile.write_bytes(data)

            port = _free_port()
            srv = Server(address="127.0.0.1", port=port, mss=4,
                         output_file=str(outfile), p=0.0)
            server_thread = threading.Thread(target=_run_server, args=(srv,),
                                             daemon=True)
            server_thread.start()
            time.sleep(0.05)  # small delay to ensure server bind

            client = Client(address="0.0.0.0", port=0,
                            server_name="127.0.0.1", server_port_num=port,
                            mss=4, window_size=4)
            client.start(str(infile))

            server_thread.join(timeout=1.0)
            self.assertEqual(outfile.read_bytes()[: len(data)], data)

    def test_timeout_on_initial_loss(self):
        with TemporaryDirectory() as tmpdir, \
                contextlib.redirect_stdout(io.StringIO()) as buf:
            tmpdir = Path(tmpdir)
            infile = tmpdir / "in.txt"
            outfile = tmpdir / "out.txt"
            data = b"timeout-check-data"
            infile.write_bytes(data)

            port = _free_port()

            # Drop the first packet, then accept the rest
            drop_sequence = iter([0.0] + [1.0] * 100)

            def fake_random():
                try:
                    return next(drop_sequence)
                except StopIteration:
                    return 1.0

            srv = Server(address="127.0.0.1", port=port, mss=4,
                         output_file=str(outfile), p=0.5)
            with mock.patch("server.random.random", side_effect=fake_random):
                server_thread = threading.Thread(target=_run_server,
                                                 args=(srv,), daemon=True)
                server_thread.start()
                time.sleep(0.05)

                client = Client(address="0.0.0.0", port=0,
                                server_name="127.0.0.1", server_port_num=port,
                                mss=4, window_size=4)
                client.start(str(infile))

                server_thread.join(timeout=2.0)

            output = buf.getvalue()
            self.assertIn("Timeout, sequence number =", output)
            self.assertEqual(outfile.read_bytes()[: len(data)], data)
