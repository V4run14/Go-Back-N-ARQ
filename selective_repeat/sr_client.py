'''Selective Repeat ARQ client implementation.'''
import socket
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GBN_PATH = ROOT / "go_back_n"
if str(GBN_PATH) not in sys.path:
    sys.path.insert(0, str(GBN_PATH))

from packet import Packet, ACK_TYPE, DATA_TYPE  # noqa: E402


class SRClient:
    '''Selective Repeat sender with per-packet timers.'''

    def __init__(self, address, port, server_name, server_port_num,
                 mss=500, window_size=1):
        self.address = address
        self.port = port
        self.server_hostname = server_name
        self.server_port = server_port_num
        self.window_size = window_size
        self.mss = mss
        self.buffer = b""
        self.base = 0  # first byte of current window
        self.next_seq = 0  # next byte index to send
        self.rto = 0.25
        self.stop_event = threading.Event()
        self.timer_lock = threading.Lock()
        self.timers = {}  # seq -> Timer
        self.acked = set()
        self.lengths = {}  # seq -> payload length
        self.timeouts = 0
        self.max_timeouts = 20  # total timeouts across packets

    def _start_timer(self, client_socket, seq):
        with self.timer_lock:
            if seq in self.timers:
                self.timers[seq].cancel()
            timer = threading.Timer(self.rto, self.handle_timeout,
                                     [client_socket, seq])
            self.timers[seq] = timer
            timer.start()

    def _cancel_timer(self, seq):
        with self.timer_lock:
            t = self.timers.pop(seq, None)
            if t:
                t.cancel()

    def _cancel_all_timers(self):
        with self.timer_lock:
            for t in self.timers.values():
                t.cancel()
            self.timers.clear()

    def send_window(self, client_socket):
        '''Send packets while window has space.'''
        while (self.next_seq < len(self.buffer) and
               self.next_seq < self.base + self.window_size * self.mss):
            end = min(self.next_seq + self.mss, len(self.buffer))
            payload = self.buffer[self.next_seq:end]
            packet = Packet(seq_num=self.next_seq, payload=payload,
                            type_field=DATA_TYPE)
            self.lengths[self.next_seq] = len(payload)
            client_socket.sendto(packet.pack(),
                                 (self.server_hostname, self.server_port))
            print(f"Sent packet with seq num: {packet.seq_num}.")
            self._start_timer(client_socket, packet.seq_num)
            self.next_seq = end

    def rdt_receive(self, client_socket):
        '''Receive ACKs and slide window based on selective ACKs.'''
        while not self.stop_event.is_set():
            try:
                packet_data, _ = client_socket.recvfrom(1024)
            except socket.timeout:
                continue
            except OSError:
                break
            packet = Packet(payload=b'')
            packet.unpack(packet_data)
            if packet.type_field != ACK_TYPE or not packet.verify_checksum():
                continue
            ack_seq = packet.seq_num
            if ack_seq in self.acked:
                continue
            self.acked.add(ack_seq)
            self._cancel_timer(ack_seq)
            print(f"Received ACK for seq num: {ack_seq}")
            while self.base in self.acked:
                self.base += self.lengths.get(self.base, self.mss)
            if self.base >= len(self.buffer):
                self.stop_event.set()
                break
            self.send_window(client_socket)

    def handle_timeout(self, client_socket, seq):
        '''Retransmit only the timed-out packet.'''
        print(f"Timeout, sequence number = {seq}")
        self.timeouts += 1
        if self.timeouts >= self.max_timeouts:
            print("Maximum timeouts exceeded, aborting transfer.")
            self.stop_event.set()
            self._cancel_all_timers()
            return
        end = seq + self.lengths.get(seq, self.mss)
        payload = self.buffer[seq:end]
        packet = Packet(seq_num=seq, payload=payload, type_field=DATA_TYPE)
        client_socket.sendto(packet.pack(),
                             (self.server_hostname, self.server_port))
        print(f"Retransmitted packet with seq num: {packet.seq_num}.")
        self._start_timer(client_socket, seq)

    def start(self, file_path):
        '''Start sending the file.'''
        with open(file_path, 'rb') as f:
            self.buffer = f.read()

        print(f'Buffer size: {len(self.buffer)} bytes')

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client_socket:
            client_socket.settimeout(0.5)
            client_socket.bind((self.address, self.port))
            recv_thread = threading.Thread(target=self.rdt_receive,
                                           args=(client_socket,))
            recv_thread.start()

            self.send_window(client_socket)
            while not self.stop_event.is_set():
                time.sleep(0.01)

            if self.timeouts < self.max_timeouts:
                final_packet = Packet(seq_num=len(self.buffer), payload=b'',
                                      type_field=DATA_TYPE)
                client_socket.sendto(final_packet.pack(),
                                     (self.server_hostname, self.server_port))
            self._cancel_all_timers()
            recv_thread.join(timeout=1.0)

        print("File transmission completed.")

    def stop(self):
        self._cancel_all_timers()
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
        client = SRClient(address='0.0.0.0', port=0,
                         server_name=server_hostname,
                         server_port_num=server_port,
                         mss=MSS, window_size=N)
        client.start(file_to_send)
    except Exception as e:
        print(e)
        sys.exit(1)
