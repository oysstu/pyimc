"""
Functionality related to the DUNE lsf logs.
"""

import ctypes
import pyimc


class IMCHeader(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
       ('sync', ctypes.c_uint16),
       ('mgid', ctypes.c_uint16),
       ('size', ctypes.c_uint16),
       ('timestamp', ctypes.c_double),
       ('src', ctypes.c_uint16),
       ('src_ent', ctypes.c_uint8),
       ('dst', ctypes.c_uint16),
       ('dst_ent', ctypes.c_uint8)
    ]


class IMCFooter(ctypes.LittleEndianStructure):
    _pack_ = 1
    _fields_ = [
       ('crc16', ctypes.c_uint16)
    ]


class LSFReader:
    def __init__(self, lsf_path):
        self.fpath = lsf_path
        self.f = None
        self.pos = 0
        self.header = IMCHeader()  # Preallocate header buffer
        self.parser = pyimc.Parser()
        self.index = []

    def __enter__(self):
        self.f = open(self.fpath, mode='rb')
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.f.close()

    def read(self, msg_types=None):
        if type(msg_types) is pyimc.Message:
            msg_types = (msg_types,)

        # Check for file end
        while self.f.peek(1):
            self.pos = self.f.tell()  # save message start
            bytes_read = self.f.readinto(self.header)
            if bytes_read < ctypes.sizeof(IMCHeader):
                raise RuntimeError('LSF file ended abruptly.')

            self.parser.reset()
            self.f.seek(self.pos)
            b = self.f.read(self.header.size + ctypes.sizeof(IMCHeader) + ctypes.sizeof(IMCFooter))
            msg = self.parser.parse(b)
            sz = self.header.size + ctypes.sizeof(IMCHeader) + ctypes.sizeof(IMCFooter)
            yield msg


if __name__ == '__main__':
    with LSFReader('/home/oysstu/Downloads/imc_test/Data.lsf') as lsf:
        for msg in lsf.read():
            print(msg)

