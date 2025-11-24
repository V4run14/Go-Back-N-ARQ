'''Go-Back-N ARQ server implementation.'''
import socket
import sys
import random
from packet import Packet


class Server:
    '''A simple Go-Back-N ARQ server implementation.'''
    def __init__(self, address, port, rcwnd=1, mss=4,
                 window_size=1, output_file='output.txt', p=0):
        self.address = address
        self.port = port
        self.rcwnd = rcwnd
        # Not using window_size here because server only sends ACKs,
        # so there will be no need for reliability here
        self.window_size = window_size
        self.buffer = []
        self.last_ack_pkt = 0
        self.mss = mss
        self.output_file = output_file
        self.probabilistic_failure = p

    def rdt_send(self, client_socket, addr):
        '''Send an ACK packet to the client.'''
        ack_packet = Packet(seq_num=self.last_ack_pkt, payload=b'')
        client_socket.sendto(ack_packet.pack(), addr)
        print(f"Sent ACK for seq num: {ack_packet.seq_num}")
   
    def handle_buffer(self, packet: Packet):
        '''Handle incoming packet and buffer it if in order.'''
        if (packet.seq_num == self.last_ack_pkt and
                len(self.buffer) < self.rcwnd * self.mss):
            self.buffer.extend(packet.payload)
            self.last_ack_pkt = packet.seq_num + len(packet.payload)
            print(f"Buffered packet with seq num: {packet.seq_num}")
            if len(self.buffer) >= self.mss:
                self.flush_buffer()
        else:
            print(
                f"Out of order packet received with seq num: {packet.seq_num}."
                f" Expected: {self.last_ack_pkt}"
            )

    def flush_buffer(self):
        '''Flush the buffer to process the data.'''
        data = bytes(self.buffer)
        with open(self.output_file, 'ab') as f:
            f.write(data)
        self.buffer = []
        print(f"Flushed {len(data)} bytes to {self.output_file}")

    def rdt_receive(self, client_socket):
        '''Receive a packet from the client socket.'''
        packet_data, addr = client_socket.recvfrom(16+self.mss)
        r = random.random()
        packet = Packet(payload=b'')
        packet.unpack(packet_data)

        # Introducing random drops
        if r <= self.probabilistic_failure:
            print(f'Dropping packet - {packet.seq_num}')
            return
        
        # Check for checksum 
        if not packet.verify_checksum():
            print(f"Corrupted packet received with seq num: {packet.seq_num}")
            return None
        
        # Check if no payload is there
        # Implies it is the last packet
        if len(packet.payload) <= 0:
            print("File transmission complete")
            raise KeyboardInterrupt
        print(f"Received packet with seq num: {packet.seq_num}")
        self.handle_buffer(packet)
        # Send an ACK back to the client
        # In case of loss, three duplicate ACKs should trigger a fast retransmit in TCP case
        self.rdt_send(client_socket, addr)
        return packet

    def start(self):
        '''Start the server to listen for incoming packets.'''
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server_socket:
            server_socket.bind((self.address, self.port))
            print(f"Server listening on {self.address}:{self.port}")
            while True:
                self.rdt_receive(server_socket)

    def stop(self):
        '''Stop the server and flush any remaining data.'''
        self.flush_buffer()
        print("Server stopped.")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'output.txt'
    probability_value = float(sys.argv[3]) if len(sys.argv) > 3 else 0
    print(f"Server Port: {port}\nOutput file: {output_file}\nProbability Value: {probability_value}\n")
    server = Server(address='localhost', port=port, mss=1, window_size=4,
                    output_file=output_file, p=probability_value)
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()
