'''Go-Back-N ARQ server implementation.'''
import socket
import sys
import random
from packet import Packet, DATA_TYPE


class Server:
    '''A simple Go-Back-N ARQ server implementation.'''

    def __init__(self, address, port, mss=500, output_file='output.txt', p=0.0):
        self.address = address
        self.port = port
        self.mss = mss
        self.output_file = output_file
        self.loss_prob = p
        self.expected_seq = 0
        self.last_client_addr = None

    def rdt_send_ack(self, server_socket, addr):
        '''Send cumulative ACK for next expected byte.'''
        ack_packet = Packet.ack(self.expected_seq)
        server_socket.sendto(ack_packet.pack(), addr)
        print(f"Sent ACK for seq num: {ack_packet.seq_num}")

    def rdt_receive(self, server_socket):
        '''Receive a packet from the client socket.'''
        packet_data, addr = server_socket.recvfrom(8 + self.mss)
        self.last_client_addr = addr
        # probabilistic drop
        if random.random() <= self.loss_prob:
            # still parse to log correct seq
            tmp = Packet(payload=b'')
            tmp.unpack(packet_data)
            print(f'Packet loss, sequence number = {tmp.seq_num}')
            # send cumulative ACK for last in-order
            self.rdt_send_ack(server_socket, addr)
            return

        packet = Packet(payload=b'')
        packet.unpack(packet_data)

        # Only accept data packets
        if packet.type_field != DATA_TYPE:
            return

        # checksum and in-order check
        if not packet.verify_checksum():
            print(f"Corrupted packet received with seq num: {packet.seq_num}")
            self.rdt_send_ack(server_socket, addr)
            return

        # zero-length payload treated as completion signal; stay alive for next transfer
        if len(packet.payload) == 0:
            print("File transmission complete signal received. Resetting state for next transfer.")
            self.rdt_send_ack(server_socket, addr)
            # Prepare for a new transfer starting at seq 0
            self.expected_seq = 0
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
            # send cumulative ACK for last in-order packet
            self.rdt_send_ack(server_socket, addr)

    def start(self):
        '''Start the server to listen for incoming packets.'''
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server_socket:
            server_socket.bind((self.address, self.port))
            print(f"Server listening on {self.address}:{self.port}")
            while True:
                self.rdt_receive(server_socket)

    def stop(self):
        '''Stop the server.'''
        print("Server stopped.")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 7735
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'output.txt'
    probability_value = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0
    print(
        f"Server Port: {port}\nOutput file: {output_file}\n"
        f"Probability Value: {probability_value}\n"
    )
    server = Server(address='0.0.0.0', port=port, mss=500,
                    output_file=output_file, p=probability_value)
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()
