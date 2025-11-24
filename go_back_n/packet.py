'''Packet structure for Go-Back-N'''
import struct
from utilities import udp_checksum


class Packet: 
    '''Custom packet class for Go-Back-N protocol.
    Header layout (8 bytes): \
     - 32-bit sequence number \
     - 16-bit checksum (one's-complement of data, RFC1071 style) \
     - 16-bit type field (0x5555 for data packets) \
    '''

    def __init__(self, seq_num=0, payload=b''):
        self.seq_num = seq_num
        self.payload = payload
        self.type_field = 0x5555 if len(payload) > 0 else 0xAAAA  # Example type field
        self.checksum = self.compute_checksum()

    def compute_checksum(self) -> int:
        '''Compute UDP-style checksum for the packet.'''
        header = struct.pack('!IHH', self.seq_num, 0, self.type_field)
        return udp_checksum(header + self.payload)
    
    def pack(self) -> bytes: 
        '''Pack the packet into bytes for transmission.'''
        header = struct.pack(
            '!IHH',
            self.seq_num,
            self.checksum,
            self.type_field,
        )
        return header + self.payload
    
    def unpack(self, packet: bytes):
        '''Unpack bytes into packet fields.'''
        header = packet[:8]
        self.seq_num, self.checksum, self.type_field = (
            struct.unpack('!IHH', header)
        )
        self.payload = packet[8:]
        return (header, self.payload)

    def verify_checksum(self) -> bool:
        '''Verify the packet's checksum.'''
        header = struct.pack('!IHH', self.seq_num, 0, self.type_field)
        computed_checksum = udp_checksum(header + self.payload)
        return computed_checksum == self.checksum