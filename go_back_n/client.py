'''Client class for Go-Back-N ARQ protocol implementation.'''
import time
import socket
import sys
import threading
from packet import Packet, ACK_TYPE, DATA_TYPE


class Client:
    '''A simple Go-Back-N ARQ client implementation.'''

    def __init__(self, address, port, server_name, server_port_num,
                 mss=500, window_size=1):
        self.address = address
        self.port = port
        self.server_hostname = server_name
        self.server_port = server_port_num
        self.window_size = window_size
        self.buffer = b""
        self.base = 0  # earliest unacked byte
        self.next_seq = 0  # next byte to send
        self.mss = mss
        self.rto = 1.0
        self.timer = None
        self.timer_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.timeouts = 0
        self.max_timeouts = 10  # fail-fast guard to avoid infinite loops

    def _start_timer(self, client_socket):
        with self.timer_lock:
            if self.timer is None:
                self.timer = threading.Timer(self.rto, self.handle_timeout,
                                             [client_socket])
                self.timer.start()

    def _stop_timer(self):
        with self.timer_lock:
            if self.timer is not None:
                self.timer.cancel()
                self.timer = None

    def send_window(self, client_socket):
        '''Send packets while the window has space.'''
        while (self.next_seq < len(self.buffer) and
               self.next_seq < self.base + self.window_size * self.mss):
            end = min(self.next_seq + self.mss, len(self.buffer))
            payload = self.buffer[self.next_seq:end]
            packet = Packet(seq_num=self.next_seq, payload=payload,
                            type_field=DATA_TYPE)
            client_socket.sendto(packet.pack(),
                                 (self.server_hostname, self.server_port))
            print(f"Sent packet with seq num: {packet.seq_num}.")
            if self.base == self.next_seq:
                self._start_timer(client_socket)
            self.next_seq = end

    def rdt_receive(self, client_socket):
        '''Receive ACKs and advance the window.'''
        while not self.stop_event.is_set():
            packet_data, _ = client_socket.recvfrom(1024)
            packet = Packet(payload=b'')
            packet.unpack(packet_data)
            if packet.type_field != ACK_TYPE or not packet.verify_checksum():
                continue
            ack_num = packet.seq_num
            if ack_num > self.base:
                self.base = ack_num
                self.timeouts = 0
                print(f"Received ACK for seq num: {ack_num}")
                if self.base == self.next_seq:
                    self._stop_timer()
                else:
                    self._start_timer(client_socket)
                if self.base >= len(self.buffer):
                    self.stop_event.set()
                    break
                self.send_window(client_socket)

    def handle_timeout(self, client_socket):
        '''Handle timeout by retransmitting all unacked packets.'''
        print(f"Timeout, sequence number = {self.base}")
        self.timeouts += 1
        if self.timeouts >= self.max_timeouts:
            print("Maximum timeouts exceeded, aborting transfer.")
            self.stop_event.set()
            self._stop_timer()
            return
        with self.timer_lock:
            self.timer = None
        seq = self.base
        while seq < self.next_seq:
            end = min(seq + self.mss, len(self.buffer))
            payload = self.buffer[seq:end]
            packet = Packet(seq_num=seq, payload=payload, type_field=DATA_TYPE)
            client_socket.sendto(packet.pack(),
                                 (self.server_hostname, self.server_port))
            print(f"Retransmitted packet with seq num: {packet.seq_num}.")
            seq = end
        if self.base < self.next_seq:
            self._start_timer(client_socket)

    def start(self, file_path):
        '''Start the client to send the file to the server.'''
        with open(file_path, 'rb') as f:
            self.buffer = f.read()

        print(f'Buffer size: {len(self.buffer)} bytes')

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client_socket:
            client_socket.bind((self.address, self.port))
            receive_thread = threading.Thread(
                target=self.rdt_receive,
                args=(client_socket,),
                daemon=True,
            )
            receive_thread.start()

            self.send_window(client_socket)
            while not self.stop_event.is_set():
                time.sleep(0.01)

            # signal completion to server
            final_packet = Packet(seq_num=self.base, payload=b'',
                                  type_field=DATA_TYPE)
            client_socket.sendto(final_packet.pack(),
                                 (self.server_hostname, self.server_port))
            self._stop_timer()

        print("File transmission completed.")

    def stop(self):
        '''Stop the client and clean up resources.'''
        self._stop_timer()
        self.stop_event.set()
        print("Client stopped.")


if __name__ == "__main__":
    server_hostname = sys.argv[1] if len(sys.argv) > 1 else 'localhost'
    server_port = int(sys.argv[2]) if len(sys.argv) > 2 else 7735
    file_to_send = sys.argv[3] if len(sys.argv) > 3 else 'input.txt'
    N = int(sys.argv[4]) if len(sys.argv) > 4 else 4
    MSS = int(sys.argv[5]) if len(sys.argv) > 5 else 500
    print(
        f"Server IP: {server_hostname}\nServer Port: {server_port}\n"
        f"File to Send: {file_to_send}\nWindow Size: {N}\nMSS: {MSS}"
    )
    try:
        client = Client(address='0.0.0.0', port=0,
                        server_name=server_hostname,
                        server_port_num=server_port,
                        mss=MSS, window_size=N)
        client.start(file_to_send)
    except Exception as e:
        print(e)
        sys.exit(1)
