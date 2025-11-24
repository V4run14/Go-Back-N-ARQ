'''Client class for Go-Back-N ARQ protocol implementation.'''
import time
import socket
import sys
import threading
from packet import Packet


class Client:
    '''A simple Go-Back-N ARQ client implementation.'''
    seq_num = 0

    def __init__(self, address, port, server_name, server_port_num, rcwnd=4,
                 mss=1,
                 window_size=1):
        self.address = address
        self.port = port
        self.server_hostname = server_name
        self.server_port = server_port_num
        self.rcwnd = rcwnd
        self.window_size = window_size
        self.buffer = b""
        self.last_ack_byte = 0  # Next start sequence number
        self.mss = mss
        self.last_sent_byte = 0
        self.rto = 1.0
        self.estimated_rtt = 1.0
        self.sample_rtt = [0, 0.0]
        self.dev_rtt = 0.0
        self.rtt_timer_calculated = False
        self.timer_thread = None
        self.max_timeouts = 4

    def rdt_send(self, client_socket, recalculate_rto=True):
        '''Send a packet to the server with whatever is pending in the \
        buffer.'''
        # Current window calculation
        start = self.last_ack_byte
        end = min(len(self.buffer), start + self.mss * self.window_size)

        # If last sent byte is less than end, we can send more data
        # print(f'\nWindow start: {start}\n Window end: {end}\nLast Sent Byte: {self.last_sent_byte}\n')
        while (
            self.last_sent_byte < end
            # At least mss bytes to send must be there in the buffer
            and self.last_sent_byte + self.mss <= len(self.buffer)
        ):
            packet = Packet(payload=self.buffer[start:start + self.mss],
                            seq_num=Client.seq_num + self.last_sent_byte)
            
            self.last_sent_byte = start + len(packet.payload)
            start += self.mss
            if self.timer_thread is None:
                self.timer_thread = threading.Timer(self.rto,
                                                    self.handle_timeout,
                                                    [client_socket])
                self.timer_thread.start()
            if recalculate_rto and self.rtt_timer_calculated is False:
                # Placeholder for actual RTT measurement
                # This means the packet is being sent for the first time
                self.sample_rtt = [self.last_sent_byte, time.time()]
                print('Starting to calculate RTT: ', self.sample_rtt)
                self.rtt_timer_calculated = True
            client_socket.sendto(
                packet.pack(),
                (self.server_hostname, self.server_port)
            )
            print(f"Sent packet with seq num: {packet.seq_num}.")

    def rdt_receive(self, client_socket):
        '''Receive a packet from the server socket.'''
        while True:
            if self.max_timeouts <= 0:
                print('Exiting rdt_receive thread')
                sys.exit(1)
            packet_data, _ = client_socket.recvfrom(1024)
            packet = Packet(payload=b'')
            _, payload = packet.unpack(packet_data)
            if (
                self.last_ack_byte + self.mss == packet.seq_num
                and packet.verify_checksum()
            ):
                self.last_ack_byte = packet.seq_num
                self.max_timeouts = 4
                # Cancel the timer since ACK has been received
                if self.timer_thread is not None:
                    self.timer_thread.cancel()
                    self.timer_thread = None

                # Since ACK is sent, we can try to send the next packet in the window
                if self.sample_rtt[0] == self.last_ack_byte:
                    self.sample_rtt[1] = time.time() - self.sample_rtt[1]
                    print('\nSample RTT difference: ', self.sample_rtt)
                    self.recalculate_rto()

                print(f"Received ACK for seq num: {packet.seq_num}")
                
                # We know that all bytes have been ack'ed
                # Let's exit
                if self.last_ack_byte >= len(self.buffer):
                    break

                # Restart the timer if there are outstanding packets
                if self.last_sent_byte > self.last_ack_byte:
                    self.timer_thread = threading.Timer(self.rto,
                                                        self.handle_timeout,
                                                        [client_socket])
                    self.timer_thread.start()

    def recalculate_rto(self):
        '''Recalculate RTO based on the sample RTT using Jacobson/Karels algo.'''
        alpha = 0.125
        beta = 0.25
        sampled_rtt = self.sample_rtt[1]
        self.estimated_rtt = ((1 - alpha) * self.estimated_rtt +
                              alpha * sampled_rtt)
        self.dev_rtt = ((1 - beta) * self.dev_rtt +
                        beta * abs(sampled_rtt - self.estimated_rtt))
        self.rto = self.estimated_rtt + 4 * self.dev_rtt
        self.rtt_timer_calculated = False
        print(f"Recalculated RTO: {self.rto}")
        
    def recalculate_loss_event_rto(self):
        '''Recalculate RTO on loss event by doubling it.'''
        self.sample_rtt = [0, 0.0]
        self.timer_thread = None
        self.rto *= 2
        if self.timer_thread is not None:
            self.timer_thread.cancel()
            self.timer_thread = None
        print(f"Loss event detected, doubled RTO to: {self.rto}")

    def handle_timeout(self, client_socket):
        '''Handle timeout event by resending packets from last ACKed byte.'''
        print("Timeout occurred, resending packets from last ACKed byte.")
        self.max_timeouts = self.max_timeouts - 1
        if self.max_timeouts <= 0:
            raise Exception("Maximum Retry Attempts reached. Terminating file sending attempt")
        self.last_sent_byte = self.last_ack_byte
        self.recalculate_loss_event_rto()  # Exponential backoff
        self.rdt_send(client_socket, recalculate_rto=False)
    
    def start(self, file_path):
        '''Start the client to send the file to the server.'''
        with open(file_path, 'rb') as f:
            self.buffer = f.read()
            if len(self.buffer) % self.mss != 0:
                # Pad the buffer to be multiple of mss
                padding_length = self.mss - (len(self.buffer) % self.mss)
                self.buffer += b' ' * padding_length
        
        print('Buffer size: ', len(self.buffer), '\n')

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client_socket:
            client_socket.bind((self.address, self.port))
            receive_thread = threading.Thread(
                target=self.rdt_receive,
                args=(client_socket,),
            )
            receive_thread.start()
            while self.last_ack_byte < len(self.buffer) and self.max_timeouts > 0:
                if self.max_timeouts <= 0:
                    print('Exiting main thread')
                    sys.exit(1)
                self.rdt_send(client_socket)
                time.sleep(0.01)  # Prevent busy-waiting and high CPU usage
          
            # Send a final packet to indicate end of transmission
            if self.max_timeouts > 0:
                final_packet = Packet(payload=b'', seq_num=self.last_ack_byte)
                client_socket.sendto(
                    final_packet.pack(),
                    (self.server_hostname, self.server_port)
                )
            receive_thread.join()

        print("File transmission completed.")

    def stop(self):
        '''Stop the client and clean up resources.'''
        if self.timer_thread is not None:
            self.timer_thread.cancel()
            self.timer_thread = None
        print("Client stopped.")
        sys.exit(0)


if __name__ == "__main__":
    try:
        server_hostname = sys.argv[1] if len(sys.argv) > 1 else 'localhost'
        server_port = int(sys.argv[2]) if len(sys.argv) > 2 else 8080
        file_to_send = sys.argv[3] if len(sys.argv) > 3 else 'input.txt'
        N = int(sys.argv[4]) if len(sys.argv) > 4 else 4
        MSS = int(sys.argv[5]) if len(sys.argv) > 5 else 1
        print(f"Server IP: {server_hostname}\nServer Port: {server_port}\nFile to Send: {file_to_send}\nWindow Size: {N}\nMSS: {MSS}")
        client = Client(address='0.0.0.0', port=6000,
                        server_name=server_hostname,
                        server_port_num=server_port,
                        mss=MSS, window_size=N)
        client.start(file_to_send)
        client.stop()
    except Exception as e:
        client.stop()
        print(e)
        sys.exit(1)
