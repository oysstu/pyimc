"""
Functionality related to the DUNE lsf logs.
"""

import io
import os
import ctypes
import pyimc
import pickle
import heapq
import math
from typing import List, Dict, Union, Iterable, Type, Tuple

try:
    import pandas as pd
except ModuleNotFoundError:
    pass


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
    """
    Implements reading of LSF files.
    The class creates an index by default, but this can be disabled if the file will only be read once.

    Must either be used through the one-off static method or using 'with LSFReader(..) as x:'
    """
    @staticmethod
    def read(lsf_path: str, types: List[Type[pyimc.Message]] = None, make_index=True):
        """
        Read all messages of the specified type(s)
        :param lsf_path: Path to the lsf file
        :param types: List of types to return
        :param make_index: If true, an index is created if it does not already exist
        :return: Message generator object
        """
        with LSFReader(lsf_path, make_index=make_index) as lsf_reader:
            for message in lsf_reader.read_message(types=types):
                yield message

    def __init__(self, lsf_path: str, make_index=True):
        """
        Reads an LSF file.
        :param lsf_path: The path to the LSF file.
        :param types: The message types to return. List of pyimc message classes.
        :param make_index: If true, an index that speeds up subsequent reads is created.
        """
        self.fpath = lsf_path
        self.f = None  # type: io.BufferedIOBase
        self.header = IMCHeader()  # Preallocate header buffer
        self.parser = pyimc.Parser()
        self.idx = {}  # type: Dict[Union[int, str], List[int]]
        self.make_index = make_index


    def __enter__(self):
        self.f = open(self.fpath, mode='rb')

        self.read_index()
        if not self.idx and self.make_index:
            self.write_index()

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

    def count_index(self, msgtype: Type[pyimc.Message]) -> int:
        """
        Get the number of messages for a given type, useful for preallocation.
        Note: generates an index, but only saves if make_index is true
        :param msgtype: The message type to return the index count for.
        :return: The number of messages of a given type
        """

        return len(self.idx[pyimc.Factory.id_from_abbrev(msgtype.__name__)])

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

    def read_message(self, types: List[Type[pyimc.Message]] = None):
        """
        Returns a generator that yields the messages in the currently open LSF file.
        This requires the LSFReader object to be opened using the "with" statement.
        See read(), where this is done automatically.
        :return:
        """

        msg_types = None if types is None else [pyimc.Factory.id_from_abbrev(x.__name__) for x in types]

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
            # Reset file pointer to start of file
            self.f.seek(0)

            # Read file without index
            # Check for file end
            while self.f.peek(1):
                self.peek_header()

                if not self.msg_types or self.header.mgid in self.msg_types:
                    self.parser.reset()
                    b = self.f.read(self.header.size + ctypes.sizeof(IMCHeader) + ctypes.sizeof(IMCFooter))
                    msg = self.parser.parse(b)
                    yield msg
                else:
                    self.f.seek(ctypes.sizeof(IMCHeader) + self.header.size + ctypes.sizeof(IMCFooter), io.SEEK_CUR)


class LSFExporter:
    """
    Reads individual messages from the LSF file into apandas.DataFrames table.
    Pandas supports a wide range of output formats such as csv, excel, hdf, json, sql
    TODO: Store IMC addresses with the library
    TODO: Fix MessageLists
    """

    def __init__(self, lsf_path: str):
        self.fpath = lsf_path
        self.lsf_reader = LSFReader(lsf_path, make_index=True)

        # Metadata
        self.log_name = None  # type: str
        self.node_map = {}  # type: Dict[int, str]
        self.entity_map = {}  # type: Dict[Tuple[int, int], str]
        self.parse_metadata()

    def get_node(self, imc_id):
        if imc_id == 0xFFFF:
            return '*'
        try:
            return self.node_map[imc_id]
        except KeyError:
            return hex(imc_id)

    def get_entity(self, imc_id, ent_id):
        if ent_id == 0xFF:
            return '*'
        try:
            return self.entity_map[(imc_id, ent_id)]
        except KeyError:
            return str(imc_id)

    def parse_metadata(self):
        with self.lsf_reader as lsf:
            self.log_name = next(lsf.read_message(types=[pyimc.LoggingControl])).name

            for msg in lsf.read_message(types=[pyimc.Announce]):
                self.node_map[msg.src] = msg.sys_name

            for msg in lsf.read_message(types=[pyimc.EntityInfo]):
                self.entity_map[(msg.src, msg.src_ent)] = msg.label

            for msg in lsf.read_message(types=[pyimc.EntityList]):
                if type(msg) is pyimc.EntityList and msg.op == pyimc.EntityList.OperationEnum.REPORT:
                    for entity in msg.list.split(';'):
                        entity_name, entity_id = entity.split('=')
                        self.entity_map[(msg.src, int(entity_id))] = entity_name

    def extract_fields(self, msg, msg_fields, skip_lists=False):
        d = []
        for f in msg_fields:
            f = getattr(msg, f)

            if type(f).__qualname__.startswith('MessageList'):
                sub_msgs = list(f)
                if not sub_msgs or skip_lists:
                    return []

                sub_fields = [k for k, v in type(sub_msgs[0]).__dict__.items() if type(v).__qualname__ == 'property']
                d.append([self.extract_fields(x, sub_fields) for x in f])
            else:
                d.append(f)

        return d

    def export_messages(self, imc_type: Type[pyimc.Message], skip_lists=False):
        with self.lsf_reader as lsf:
            base_fields = ['timestamp', 'src', 'src_ent', 'dst', 'dst_ent']
            msg_fields = [k for k, v in imc_type.__dict__.items() if type(v).__qualname__ == 'property']

            data = []
            extra = []
            for msg in lsf.read_message(types=[imc_type]):
                msg_data = [msg.timestamp, self.get_node(msg.src), self.get_entity(msg.src, msg.src_ent),
                            self.get_node(msg.dst), self.get_entity(msg.dst_ent, msg.dst_ent)]

                msg_data.extend(self.extract_fields(msg, msg_fields, skip_lists))

                if imc_type is pyimc.EstimatedState:
                    extra.append(pyimc.coordinates.toWGS84(msg))

                data.append(msg_data)

            df = pd.DataFrame(data=data, columns=base_fields+msg_fields)
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')

            if imc_type is pyimc.EstimatedState:
                df[['lat', 'lon', 'height']] = extra
                del df['x'], df['y'], df['z']

            return df


if __name__ == '__main__':
    pass
