import struct
class Ram:
    def __init__(s, path): s.b = open(path,'rb').read()
    def u32(s, a): return struct.unpack_from('<I', s.b, a & 0x7FFFFC)[0]
    def f(s, a): return struct.unpack('>f', struct.pack('>I', s.u32(a)))[0]
    def u16(s, a): w = s.u32(a & ~3); return (w >> 16) & 0xFFFF if (a & 2) == 0 else w & 0xFFFF
    def tag(s, a): return struct.pack('>I', s.u32(a)).decode('latin1')
    def words(s, a, n): return [s.u32(a + 4*i) for i in range(n)]
