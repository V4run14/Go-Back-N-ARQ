'''Selective Repeat ARQ server implementation.'''
import random
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GBN_PATH = ROOT / "go_back_n"
if str(GBN_PATH) not in sys.path:
    sys.path.insert(0, str(GBN_PATH))

from packet import Packet, DATA_TYPE  # noqa: E402


class SRServer:
    '''Selective Repeat receiver with buffering of out-of-order packets.'''

    def __init__(self, address, port, mss=500, output_file='output.txt', p=0.0,
                 window_size=64):
        self.address = address
        self.port = port
        self.mss = mss
        self.output_file = output_file
        self.loss_prob = p
        self.window_size = window_size
        self.base = 0
        self.buffer = {}  # seq -> payload
        self.transfer_started = False

    def rdt_send_ack(self, server_socket, addr, seq):
        ack_packet = Packet.ack(seq)
        server_socket.sendto(ack_packet.pack(), addr)
        print(f"Sent ACK for seq num: {ack_packet.seq_num}")

    def _deliver_in_order(self):
        '''Write contiguous buffered data to file.'''
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

        # start of new transfer
        if packet.seq_num == 0 and not self.transfer_started:
            open(self.output_file, 'wb').close()
            self.transfer_started = True
            self.base = 0
            self.buffer.clear()

        # completion signal
        if len(packet.payload) == 0:
            print("File transmission complete signal received. Resetting state for next transfer.")
            self.rdt_send_ack(server_socket, addr, packet.seq_num)
            self.transfer_started = False
            self.base = 0
            self.buffer.clear()
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
        print(f"SR Server listening on {self.address}:{self.port}, p={self.loss_prob}")
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server_socket:
            server_socket.bind((self.address, self.port))
            while True:
                self.rdt_receive(server_socket)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 7735
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'output.txt'
    probability_value = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
    window_size = int(sys.argv[4]) if len(sys.argv) > 4 else 64
    print(
        f"Server Port: {port}\nOutput file: {output_file}\n"
        f"Probability Value: {probability_value}\nWindow Size: {window_size}\n"
    )
    server = SRServer(address='0.0.0.0', port=port, mss=500,
                      output_file=output_file, p=probability_value,
                      window_size=window_size)
    server.start()
