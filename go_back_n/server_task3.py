'''Server variant for Task 3: cycles loss probability per completed transfer.'''
import argparse
import random
import socket
from packet import Packet, DATA_TYPE


class CyclingServer:
    '''Go-Back-N server that advances loss probability after each transfer.'''

    def __init__(self, address, port, mss=500, output_file='output.txt',
                 loss_values=None, transfers_per_p=5):
        self.address = address
        self.port = port
        self.mss = mss
        self.output_file = output_file
        self.loss_values = loss_values or [round(x / 100, 2) for x in range(1, 11)]
        self.loss_index = 0
        self.loss_prob = self.loss_values[self.loss_index]
        self.transfers_per_p = transfers_per_p
        self.transfer_count = 0
        self.expected_seq = 0
        self.last_client_addr = None
        self.transfer_started = False

    def _advance_loss(self):
        if self.loss_index + 1 < len(self.loss_values):
            self.loss_index += 1
        self.loss_prob = self.loss_values[self.loss_index]
        print(f"Advancing to loss probability p={self.loss_prob}")

    def rdt_send_ack(self, server_socket, addr):
        ack_packet = Packet.ack(self.expected_seq)
        server_socket.sendto(ack_packet.pack(), addr)
        print(f"Sent ACK for seq num: {ack_packet.seq_num}")

    def rdt_receive(self, server_socket):
        packet_data, addr = server_socket.recvfrom(8 + self.mss)
        self.last_client_addr = addr
        if random.random() <= self.loss_prob:
            tmp = Packet(payload=b'')
            tmp.unpack(packet_data)
            print(f'Packet loss, sequence number = {tmp.seq_num} (p={self.loss_prob})')
            self.rdt_send_ack(server_socket, addr)
            return

        packet = Packet(payload=b'')
        packet.unpack(packet_data)
        if packet.type_field != DATA_TYPE:
            return

        # new transfer detection
        if packet.seq_num == 0 and self.expected_seq != 0:
            print("New transfer detected; resetting state and truncating output.")
            self.expected_seq = 0
            self.transfer_started = False
        if packet.seq_num == 0 and not self.transfer_started:
            open(self.output_file, 'wb').close()
            self.transfer_started = True

        if not packet.verify_checksum():
            print(f"Corrupted packet received with seq num: {packet.seq_num}")
            self.rdt_send_ack(server_socket, addr)
            return

        if len(packet.payload) == 0:
            print("File transmission complete signal received.")
            self.rdt_send_ack(server_socket, addr)
            self.expected_seq = 0
            self.transfer_started = False
            self.transfer_count += 1
            if self.transfer_count >= self.transfers_per_p:
                self.transfer_count = 0
                self._advance_loss()
            print(f"Ready for next transfer with p={self.loss_prob}")
            return

        if packet.seq_num == self.expected_seq:
            with open(self.output_file, 'ab') as f:
                f.write(packet.payload)
            self.expected_seq += len(packet.payload)
            print(f"Received in-order packet with seq num: {packet.seq_num}")
            self.rdt_send_ack(server_socket, addr)
        else:
            print(
                f"Out-of-order packet with seq num: {packet.seq_num}. "
                f"Expected: {self.expected_seq}"
            )
            self.rdt_send_ack(server_socket, addr)

    def start(self):
        print(
            f"Starting server on {self.address}:{self.port} with initial p={self.loss_prob} "
            f"(advancing after {self.transfers_per_p} transfers per p)"
        )
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server_socket:
            server_socket.bind((self.address, self.port))
            while True:
                self.rdt_receive(server_socket)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Task 3 server that cycles loss probabilities.")
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
                        help="Number of transfers to run at each p before advancing (default 5).")
    args = parser.parse_args()

    values = []
    current = args.pmin
    while current <= args.pmax + 1e-9:
        values.append(round(current, 2))
        current += args.pstep

    srv = CyclingServer(address="0.0.0.0", port=args.port,
                        mss=500, output_file=args.output,
                        loss_values=values,
                        transfers_per_p=args.per_p)
    srv.start()
