"""
Functionality related to the DUNE lsf logs.
"""

import io
from io import BytesIO
import os
import logging
import ctypes
import pyimc
import pickle
import heapq
import gzip
import warnings
from typing import List, Dict, Union, Iterable, Type, Tuple
import inspect

try:
    import pandas as pd
except ModuleNotFoundError:
    pass


logger = logging.getLogger('pyimc.lsf')


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
    The class creates an index by default, but this can be disabled if the file will only be read once. It is also
    possible to disable the storing of this index to file, e.g. if the LSF-file is located in a read-only filesystem.

    Must either be used through the one-off static method or using 'with LSFReader(..) as x:'
    """
    @staticmethod
    def read(lsf: Union[str, bytes], types: List[Type[pyimc.Message]] = None, use_index=True, save_index=True):
        """
        Read all messages of the specified type(s)
        :param lsf: The path to an LSF-file on the filesystem, or an in-memory lsf-file (bytes)
        :param types: List of types to return
        :param use_index: If true, generates an index of the message types (speeds up subsequent reads)
        :param save_index: If true, the generated index is saved to a pyimc_idx file
        :return: Message generator object
        """
        with LSFReader(lsf, use_index=use_index, save_index=save_index) as lsf_reader:
            for message in lsf_reader.read_message(types=types):
                yield message

    def __init__(self, lsf: Union[str, bytes], use_index=True, save_index=True):
        """
        Reads an LSF file.
        :param lsf: The path to an LSF-file on the filesystem, or an in-memory lsf-file (bytes)
        :param types: The message types to return. List of pyimc message classes.
        :param use_index: If true, generates an index of the message types (speeds up subsequent reads)
        :param save_index: If true, the generated index is saved to a pyimc_idx file
        """
        self.lsf = lsf
        self.f = None  # type: io.BufferedIOBase
        self.header = IMCHeader()  # Preallocate header buffer
        self.idx = {}  # type: Dict[Union[int, str], List[int]]
        self.use_index = use_index
        self.save_index = save_index

    def __enter__(self):
        # Open file/stream
        if type(self.lsf) is str:
            self.f = open(self.lsf, mode='rb')
        elif type(self.lsf) is bytes:
            self.f = BytesIO(self.lsf)
        elif type(self.lsf) in (io.BytesIO, io.FileIO, gzip.GzipFile):
            self.f = self.lsf
        else:
            raise ValueError('LSF file must be passed as raw data (bytes), path (string) or file object.')

        # Attempt to read an pre-existing index file
        if type(self.lsf) is str:
            fbase, ext = os.path.splitext(self.lsf)
            if os.path.isfile(fbase + '.pyimc_idx') and os.path.getsize(fbase + '.pyimc_idx') > 0:
                self.read_index(fbase + '.pyimc_idx')

        # Generate/save index
        if not self.idx and self.use_index:
            self.generate_index()
            if self.save_index and type(self.lsf) is str:
                self.write_index(os.path.splitext(self.lsf)[0] + '.pyimc_idx')

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Close file/stream
        self.f.close()

    def peek_header(self):
        bytes_read = self.f.readinto(self.header)
        if bytes_read < ctypes.sizeof(IMCHeader):
            raise RuntimeError('LSF file ended abruptly.')

        # Return file position to before header
        self.f.seek(-ctypes.sizeof(IMCHeader), io.SEEK_CUR)

    def generate_index(self):
        """
        Run through the lsf-file and generate a message index (in-memory).
        Speeds up when the file is parsed multiple times, e.g. to output different messages
        :return:a
        """
        self.f.seek(0)

        # Timestamp of first message is used to avoid index/lsf mismatch on load
        self.peek_header()
        self.idx['timestamp'] = self.header.timestamp

        # Check for file end
        while self.f.read(ctypes.sizeof(IMCHeader)):
            self.f.seek(-ctypes.sizeof(IMCHeader), io.SEEK_CUR)
            self.peek_header()

            # Store position for this message
            try:
                self.idx[self.header.mgid].append(self.f.tell())
            except (KeyError, AttributeError):
                self.idx[self.header.mgid] = [self.f.tell()]

            # Go to next message
            self.f.seek(ctypes.sizeof(IMCHeader) + self.header.size + ctypes.sizeof(IMCFooter), io.SEEK_CUR)

        self.f.seek(0)

    def write_index(self, fpath):
        """
        Write message index to pyimc_idx file. Generates index if not already present
        :param fpath: The file path to write (typically lsf_name.pyimc_idx)
        :return:
        """
        if not self.idx:
            self.generate_index()

        # Store index
        with open(fpath, mode='wb') as f:
            pickle.dump(self.idx, f)

    def read_index(self, fpath):
        """

        :param fpath: The path to write (typically lsf_name.pyimc_idx)
        :return:
        """
        with open(fpath, 'rb') as f_idx:
            self.idx = pickle.load(f_idx)

        # Verify that timestamp matches first message
        self.peek_header()
        if self.header.timestamp != self.idx['timestamp']:
            self.idx = {}

        # Remove timestamp entry
        del self.idx['timestamp']

    def count_index(self, msg_type: Type[pyimc.Message]) -> int:
        """
        Get the number of messages for a given type, useful for preallocation.
        Note: generates an index, but only saves if make_index is true
        :param msg_type: The message type to return the index count for.
        :return: The number of messages of a given type
        """

        return len(self.idx[pyimc.Factory.id_from_abbrev(msg_type.__name__)])

    def count_messages(self):
        """ Returns a dictionary of all message types with their counts """
        return {type(pyimc.Factory.produce(k)): len(v) for k, v in self.idx.items() if type(k) is int}

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
        if self.idx and msg_types is not None:
            # Read using index
            for pos in self.sorted_idx_iter(msg_types):
                self.f.seek(pos)
                self.peek_header()
                if self.header.sync != pyimc.constants.SYNC:
                    warnings.warn('Invalid synchronization number. Stopping parsing')
                    break
                b = self.f.read(self.header.size + ctypes.sizeof(IMCHeader) + ctypes.sizeof(IMCFooter))
                msg = pyimc.Packet.deserialize(b)
                yield msg
        else:
            # Reset file pointer to start of file
            self.f.seek(0)

            # Read file without index
            # Check for file end
            while self.f.read(ctypes.sizeof(IMCHeader)):
                self.f.seek(-ctypes.sizeof(IMCHeader), io.SEEK_CUR)
                self.peek_header()

                if self.header.sync != pyimc.constants.SYNC:
                    warnings.warn('Invalid synchronization number. Stopping parsing')
                    break

                if msg_types is None or self.header.mgid in msg_types:
                    b = self.f.read(self.header.size + ctypes.sizeof(IMCHeader) + ctypes.sizeof(IMCFooter))
                    msg = pyimc.Packet.deserialize(b)
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

    def __init__(self, lsf: Union[str, bytes], use_index=True, save_index=True):
        """
        Initialize exporter to a given LSF-file. Generates metadata automatically
        :param lsf_path: The path to the LSF-file
        :param use_index: If true, generates an index of the message types, faster export of multiple message types
        :param save_index: If true, index is saved to file for subsequent runs
        """
        self.lsf = lsf
        self.lsf_reader = LSFReader(lsf, use_index=use_index, save_index=save_index)

        # Metadata
        self.log_name = None  # type: str
        self.logging_system_id = None  # type: int
        self.logging_system_name = None  # type: str
        self.node_map = {}  # type: Dict[int, str]
        self.entity_map = {}  # type: Dict[Tuple[int, int], str]
        self.parse_metadata()

    def get_node_name(self, imc_id: int) -> str:
        """
        Retrieve the name of the system assosciated with an imc address
        :param imc_id: The imc-id of the system
        :return:
        """
        if imc_id == 0xFFFF:
            return '*'
        try:
            return self.node_map[imc_id]
        except KeyError:
            return hex(imc_id)

    def get_node_id(self, sys_name: str) -> Union[int, type(None)]:
        """
        Retrieve the IMC id associated with an IMC system name.
        Note: the name is assumed to be unique
        :param sys_name: The announced name of the system
        :return:
        """
        for k, v in self.node_map.items():
            if v == sys_name:
                return k

        return None

    def get_entity(self, imc_id: int, ent_id: int) -> str:
        """
        Retrieve the name of an entity assosciated with an imc address
        :param imc_id: The imc-id of the system
        :param ent_id: The entity-id of the entity
        :return:
        """
        if ent_id == 0xFF:
            return '*'
        try:
            return self.entity_map[(imc_id, ent_id)]
        except KeyError:
            return str(imc_id)

    def parse_metadata(self):
        """
        Generates metadata from the target LSF file (imc nodes, imc entities)
        :return:
        """
        with self.lsf_reader as lsf:
            try:
                logging_control = next(lsf.read_message(types=[pyimc.LoggingControl]))
                self.log_name = logging_control.name
                self.logging_system_id = logging_control.src
            except StopIteration:
                pass

            # Collect all announced systems (map: imc id -> system name)
            for msg in lsf.read_message(types=[pyimc.Announce]):
                self.node_map[msg.src] = msg.sys_name

            # Collect all entities (imc id, entity id -> entity name)
            for msg in lsf.read_message(types=[pyimc.EntityInfo]):
                self.entity_map[(msg.src, msg.src_ent)] = msg.label

            # Do the same using EntityList
            for msg in lsf.read_message(types=[pyimc.EntityList]):
                if type(msg) is pyimc.EntityList and msg.op == pyimc.EntityList.OperationEnum.REPORT:
                    for entity in msg.list.split(';'):
                        entity_name, entity_id = entity.split('=')
                        self.entity_map[(msg.src, int(entity_id))] = entity_name

            # Try to update logging system name
            try:
                self.logging_system_name = self.node_map[self.logging_system_id]
            except KeyError:
                pass

    def extract_fields(self, msg, msg_fields, skip_lists=False, skip_binary=False):
        """
        Extracts the fields given in msg_fields from the message object
        :param msg: The message object to extract the fields from
        :param msg_fields: The message fields to extract
        :param skip_lists: Skips MessageList types (works poorly with a tabular structure)
        :param skip_binary: Skip fields with binary content
        :return:
        """
        d = []
        for field_name in msg_fields:
            value = getattr(msg, field_name)

            if type(value).__qualname__.startswith('MessageList'):
                sub_msgs = list(value)
                if not sub_msgs or skip_lists:
                    d.append('MessageList<{}>'.format(type(sub_msgs[0]).__qualname__ if sub_msgs else 'Empty'))
                    continue

                sub_fields = [k for k, v in type(sub_msgs[0]).__dict__.items() if type(v).__qualname__ == 'property']
                d.append([self.extract_fields(x, sub_fields) for x in value])
            else:
                if hasattr(value, '__members__'):
                    # Cast enumeration to int
                    d.append(int(value))
                elif pyimc.Message in inspect.getmro(type(value)):
                    # Inline message, handle the same way as lists
                    if skip_lists:
                        d.append('InlineMessage<' + type(value).__qualname__ + '>')
                    else:
                        sub_fields = [k for k, v in type(value).__dict__.items() if type(v).__qualname__ == 'property']
                        d.append([self.extract_fields(value, sub_fields, skip_lists=skip_lists)])
                elif skip_binary and type(value) is bytes:
                    d.append('<binary>')
                else:
                    d.append(value)

        return d

    def export_messages(self, imc_type: Type[pyimc.Message], skip_lists=False, skip_binary=False, condition=None) -> pd.DataFrame:
        """
        Export the messages of the target imc type from the LSF file as a pandas.DataFrame
        :param imc_type: The pyimc type of the target message (e.g. pyimc.EstimatedState)
        :param skip_lists: Skips MessageList types (works poorly with a tabular structure)
        :param skip_binary: Skip fields with binary content (e.g. sidescan-data)
        :param condition: Only export messages where the given lambda expression evaluates to True (lambda(msg))
        :return:
        """
        with self.lsf_reader as lsf:
            base_fields = ['timestamp', 'src', 'src_ent', 'dst', 'dst_ent']
            msg_fields = [k for k, v in imc_type.__dict__.items() if type(v).__qualname__ == 'property']

            data = []
            extra = []
            for msg in lsf.read_message(types=[imc_type]):
                if condition is not None and not condition(msg):
                    continue

                msg_data = [msg.timestamp, self.get_node_name(msg.src), self.get_entity(msg.src, msg.src_ent),
                            self.get_node_name(msg.dst), self.get_entity(msg.dst_ent, msg.dst_ent)]

                msg_data.extend(self.extract_fields(msg, msg_fields, skip_lists, skip_binary))

                if imc_type is pyimc.EstimatedState:
                    extra.append(pyimc.coordinates.toWGS84(msg))

                data.append(msg_data)

            df = pd.DataFrame(data=data, columns=base_fields+msg_fields)
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')

            # Convert estate local frame to lat/lon
            if imc_type is pyimc.EstimatedState:
                df[['lat', 'lon', 'height']] = extra
                del df['x'], df['y'], df['z']

            # Convert enumerations to categorical and bitfields to strings
            tmp = imc_type()
            for field_name in msg_fields:
                val = getattr(tmp, field_name)
                # Both enums and bitfields defines __members__
                if hasattr(val, '__members__'):
                    # Only bitfields defines xor
                    if hasattr(val, '__xor__'):
                        pass
                    else:
                        cat_rev = {int(v): k for k, v in val.__members__.items()}
                        cat_str = [cat_rev[v] if v in cat_rev else 'UNKNOWN' for v in range(max(cat_rev.keys())+1)]
                        df[field_name] = pd.Categorical.from_codes(df[field_name].values, cat_str)

            return df


def merge(lsf_dir, lsf_out):
    """
    Merge all lsf files contained in the subdirectories into a single lsf-file. The messages are sorted by timestamp.
    :param lsf_dir: The root directory to start search for lsf files
    :param lsf_out: The output path of the target lsf file
    :return:
    """
    msgs = []
    for root, _, fnames in os.walk(lsf_dir):
        for fname in fnames:
            if fname.endswith('.lsf'):
                for msg in LSFReader.read(os.path.join(root, fname), use_index=False, save_index=False):
                    msgs.append(msg)
            elif fname.endswith('.lsf.gz') and not os.path.exists(os.path.join(root, fname[:-3])):
                logger.info('Merging "{}"'.format(os.path.join(root, fname)))

                # Try to decompress the full file first
                f_msgs = []
                try:
                    with open(os.path.join(root, fname), 'rb') as f:
                        data = gzip.decompress(f.read())
                        for msg in LSFReader.read(data, save_index=False):
                            f_msgs.append(msg)
                except EOFError:
                    # Gzip file is missing EOF, decompress file gradually
                    logger.warning(e)
                    logger.info('Trying to recover messages by decompressing gradually...')
                    try:
                        f_msgs = []
                        with open(os.path.join(root, fname), 'rb') as f:
                            with gzip.GzipFile(fileobj=f, mode='rb') as gz:
                                for msg in LSFReader.read(gz, save_index=False):
                                    f_msgs.append(msg)
                    except EOFError as e:
                        pass

                msgs.extend(f_msgs)

    msgs.sort(key=lambda x: x.timestamp)

    with open(lsf_out, 'wb') as f:
        for msg in msgs:
            f.write(pyimc.Packet.serialize(msg))


def dump_messages(lsf_path, out_path, fmt: Union[str, List[str]], skip_lists=True, skip_binary=False):
    """
    Dumps all messages in the target file to the target directory in a specified format
    :param lsf_path: The path to the input LSF file
    :param out_path: The output directory of the output messages
    :param fmt: The output format of each message ('csv' / 'json')
    :param skip_lists: Skip fields containing MessageList (works poorly in a tabular format)
    :param skip_binary: Skip fields with binary content
    :return:
    """
    fmts = fmt if type(fmt) in (list, tuple) else [fmt]
    exp = LSFExporter(lsf_path, save_index=False)
    msg_counts = exp.lsf_reader.count_messages()

    # Create output dir
    os.makedirs(out_path, exist_ok=True)

    for msg_type in msg_counts.keys():
        print('Processing {}...'.format(msg_type.__qualname__))
        df = exp.export_messages(imc_type=msg_type, skip_lists=skip_lists, skip_binary=skip_binary)

        # Convert binary fields to string (ignoring non-valid ascii)
        if len(df) > 0:
            for col in df.columns:
                if type(df[col][0]) is bytes:
                    df[col] = df[col].apply(lambda x: x.decode('ascii', errors='replace'))

        if 'csv' in fmts:
            df.to_csv(os.path.join(out_path, msg_type.__qualname__ + '.csv'))
        if 'json' in fmts:
            df.to_json(os.path.join(out_path, msg_type.__qualname__ + '.json'))


if __name__ == '__main__':
    pass
