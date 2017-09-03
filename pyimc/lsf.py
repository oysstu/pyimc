"""
Functionality related to the DUNE lsf logs.
"""

import io
import ctypes
import pyimc
import pickle
import heapq
from typing import List, Dict, Union, Iterable


# Re-definition of IMC Header and Footer
# Used to determine how many bytes should be read from file,
# and to be able to skip parsing of unnecessary messages
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
        self.f = None  # type: io.BufferedIOBase
        self.header = IMCHeader()  # Preallocate header buffer
        self.parser = pyimc.Parser()
        self.idx = {}  # type: Dict[Union[int, str], List[int]]

    def __enter__(self):
        self.f = open(self.fpath, mode='rb')
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.f.close()


    def peek_header(self):
        bytes_read = self.f.readinto(self.header)
        if bytes_read < ctypes.sizeof(IMCHeader):
            raise RuntimeError('LSF file ended abruptly.')

        # Return file position to before header
        self.f.seek(-ctypes.sizeof(IMCHeader), io.SEEK_CUR)

    def write_index(self):
        """
        Run through the lsf-file and generate an index file
        :return:
        """
        self.f.seek(0)

        # Check for file end
        while self.f.peek(1):
            self.peek_header()

            # Timestamp of first message is used to avoid index/lsf mismatch on load
            if self.f.tell() == 0:
                self.idx['timestamp'] = self.header.timestamp

            # Store position for this message
            try:
                self.idx[self.header.mgid].append(self.f.tell())
            except (KeyError, AttributeError) as e:
                self.idx[self.header.mgid] = [self.f.tell()]

            # Go to next message
            self.f.seek(ctypes.sizeof(IMCHeader) + self.header.size + ctypes.sizeof(IMCFooter), io.SEEK_CUR)

        self.f.seek(0)

        # Store index
        fbase, ext = os.path.splitext(self.fpath)
        with open(fbase + '.pyimc_idx', mode='wb') as f:
            pickle.dump(self.idx, f)

    def read_index(self):
        fbase, ext = os.path.splitext(self.fpath)
        if os.path.isfile(fbase + '.pyimc_idx'):
            with open(fbase + '.pyimc_idx', 'rb') as f_idx:
                self.idx = pickle.load(f_idx)

            # Verify that timestamp matches first message
            self.peek_header()
            if self.header.timestamp != self.idx['timestamp']:
                self.idx = {}

            # Remove timestamp entry
            del self.idx['timestamp']

    def sorted_idx_iter(self, types: List[int]) -> Iterable[int]:
        """
        Returns an iterator of file positions sorted by file position (across different message types)
        :param types: The message types to return, None returns all types
        :return: Generator object for sorted file positions
        """
        if types:
            idx_iters = [self.idx[key] for key in types if key in self.idx]
        else:
            idx_iters = [val for key, val in self.idx.items()]

        # Use the heapq.merge function to return sorted iterator of file indices
        return heapq.merge(*idx_iters)

    def read(self, msg_types=None):
        if msg_types:
            msg_types = [pyimc.Factory.id_from_abbrev(x.__name__) for x in msg_types]

        self.read_index()
        if not self.idx and msg_types:
            self.write_index()

        if self.idx:
            # Read using index
            for pos in self.sorted_idx_iter(msg_types):
                self.f.seek(pos)
                self.peek_header()
                self.parser.reset()
                b = self.f.read(self.header.size + ctypes.sizeof(IMCHeader) + ctypes.sizeof(IMCFooter))
                msg = self.parser.parse(b)
                yield msg
        else:
            # Read file without index
            # Check for file end
            while self.f.peek(1):
                self.peek_header()

                if not msg_types or self.header.mgid in msg_types:
                    self.parser.reset()
                    b = self.f.read(self.header.size + ctypes.sizeof(IMCHeader) + ctypes.sizeof(IMCFooter))
                    msg = self.parser.parse(b)
                    yield msg
                else:
                    self.f.seek(ctypes.sizeof(IMCHeader) + self.header.size + ctypes.sizeof(IMCFooter), io.SEEK_CUR)


if __name__ == '__main__':
    import os, time
    idir = '.'
    with LSFReader(os.path.join(idir, 'Data.lsf')) as lsf:
        for msg in lsf.read(msg_types=[pyimc.Announce]):
            print(msg)