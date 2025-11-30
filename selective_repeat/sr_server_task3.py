'''Selective Repeat server that cycles loss probability after N transfers.'''
import argparse
import random
import socket
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GBN_PATH = ROOT / "go_back_n"
if str(GBN_PATH) not in sys.path:
    sys.path.insert(0, str(GBN_PATH))

from packet import Packet, DATA_TYPE  # noqa: E402


class CyclingSRServer:
    def __init__(self, address, port, mss=500, output_file='output.txt',
                 loss_values=None, transfers_per_p=5, window_size=64):
        self.address = address
        self.port = port
        self.mss = mss
        self.output_file = output_file
        self.loss_values = loss_values or [round(x / 100, 2) for x in range(1, 11)]
        self.loss_index = 0
        self.loss_prob = self.loss_values[self.loss_index]
        self.transfers_per_p = transfers_per_p
        self.transfer_count = 0
        self.window_size = window_size
        self.base = 0
        self.buffer = {}
        self.transfer_started = False

    def _advance_loss(self):
        if self.loss_index + 1 < len(self.loss_values):
            self.loss_index += 1
        self.loss_prob = self.loss_values[self.loss_index]
        print(f"Advancing to loss probability p={self.loss_prob}")

    def rdt_send_ack(self, server_socket, addr, seq):
        ack_packet = Packet.ack(seq)
        server_socket.sendto(ack_packet.pack(), addr)
        print(f"Sent ACK for seq num: {ack_packet.seq_num}")

    def _deliver_in_order(self):
        while self.base in self.buffer:
            payload = self.buffer.pop(self.base)
            with open(self.output_file, 'ab') as f:
                f.write(payload)
            self.base += len(payload)

    def rdt_receive(self, server_socket):
        packet_data, addr = server_socket.recvfrom(8 + self.mss)
        if random.random() <= self.loss_prob:
            tmp = Packet(payload=b'')
            tmp.unpack(packet_data)
            print(f'Packet loss, sequence number = {tmp.seq_num} (p={self.loss_prob})')
            return

        packet = Packet(payload=b'')
        packet.unpack(packet_data)
        if packet.type_field != DATA_TYPE:
            return

        if packet.seq_num == 0 and not self.transfer_started:
            open(self.output_file, 'wb').close()
            self.transfer_started = True
            self.base = 0
            self.buffer.clear()

        if len(packet.payload) == 0:
            print("File transmission complete signal received.")
            self.rdt_send_ack(server_socket, addr, packet.seq_num)
            self.transfer_started = False
            self.base = 0
            self.buffer.clear()
            self.transfer_count += 1
            if self.transfer_count >= self.transfers_per_p:
                self.transfer_count = 0
                self._advance_loss()
            print(f"Ready for next transfer with p={self.loss_prob}")
            return

        if not packet.verify_checksum():
            print(f"Corrupted packet received with seq num: {packet.seq_num}")
            return

        window_end = self.base + self.window_size * self.mss
        if packet.seq_num < self.base:
            print(f"Duplicate packet with seq num: {packet.seq_num}")
            self.rdt_send_ack(server_socket, addr, packet.seq_num)
            return
        if packet.seq_num >= window_end:
            print(f"Packet outside window with seq num: {packet.seq_num} (window_end={window_end})")
            return

        if packet.seq_num not in self.buffer:
            self.buffer[packet.seq_num] = packet.payload
            print(f"Buffered packet with seq num: {packet.seq_num}")
        else:
            print(f"Duplicate buffered packet with seq num: {packet.seq_num}")

        self.rdt_send_ack(server_socket, addr, packet.seq_num)
        self._deliver_in_order()

    def start(self):
        print(
            f"Starting SR server on {self.address}:{self.port} with initial p={self.loss_prob} "
            f"(advancing after {self.transfers_per_p} transfers per p)"
        )
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server_socket:
            server_socket.bind((self.address, self.port))
            while True:
                self.rdt_receive(server_socket)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Selective Repeat server that cycles loss probabilities.")
    parser.add_argument("port", type=int, nargs="?", default=7735,
                        help="UDP port to listen on (default 7735).")
    parser.add_argument("output", nargs="?", default="output.txt",
                        help="Output file path (default output.txt).")
    parser.add_argument("--pmin", type=float, default=0.01,
                        help="Starting loss probability (default 0.01).")
    parser.add_argument("--pmax", type=float, default=0.10,
                        help="Ending loss probability inclusive (default 0.10).")
    parser.add_argument("--pstep", type=float, default=0.01,
                        help="Step between loss probabilities (default 0.01).")
    parser.add_argument("--per-p", type=int, default=5,
                        help="Transfers per probability before advancing (default 5).")
    parser.add_argument("--window", type=int, default=64,
                        help="Receiver window size (default 64).")
    args = parser.parse_args()

    values = []
    current = args.pmin
    while current <= args.pmax + 1e-9:
        values.append(round(current, 2))
        current += args.pstep

    srv = CyclingSRServer(address="0.0.0.0", port=args.port,
                          mss=500, output_file=args.output,
                          loss_values=values,
                          transfers_per_p=args.per_p,
                          window_size=args.window)
    srv.start()
