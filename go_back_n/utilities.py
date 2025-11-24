"""
Utilities for building and verifying our custom packet header.
"""


def udp_checksum(data: bytes) -> int:
    """
    Compute 16-bit one's-complement checksum (RFC 1071) for the given bytes.
    Pads with a zero byte if the length is odd.
    Returns checksum as an integer 0..0xffff.
    """
    if len(data) % 2:
        data = data + b"\x00"
    s = 0
    for i in range(0, len(data), 2):
        word = (data[i] << 8) + data[i + 1]
        s += word
        # carry around
        s = (s & 0xFFFF) + (s >> 16)
    # final wrap
    s = (s & 0xffff) + (s >> 16)
    return (~s) & 0xffff
