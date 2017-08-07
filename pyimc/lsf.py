"""
Functionality related to the DUNE lsf logs.
"""

import io
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

    def __enter__(self):
        self.f = open(self.fpath, mode='rb')
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.f.close()

    def read(self, msg_types=None):
        if msg_types:
            msg_types = [x.__name__ for x in msg_types]

        # Check for file end
        while self.f.peek(1):
            bytes_read = self.f.readinto(self.header)
            if bytes_read < ctypes.sizeof(IMCHeader):
                raise RuntimeError('LSF file ended abruptly.')

            if not msg_types or pyimc.Factory.abbrev_from_id(self.header.mgid) in msg_types:
                self.parser.reset()
                # Set position back to before header
                self.f.seek(-ctypes.sizeof(IMCHeader), io.SEEK_CUR)
                b = self.f.read(self.header.size + ctypes.sizeof(IMCHeader) + ctypes.sizeof(IMCFooter))
                msg = self.parser.parse(b)
                yield msg
            else:
                self.f.seek(self.header.size + ctypes.sizeof(IMCFooter), io.SEEK_CUR)


if __name__ == '__main__':
    import os
    idir = '.'
    with LSFReader(os.path.join(idir, 'Data.lsf')) as lsf:
        for msg in lsf.read(msg_types=[pyimc.Announce]):
            print(msg)

