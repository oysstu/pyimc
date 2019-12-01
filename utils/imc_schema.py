"""
Parser for the IMC.xml specification file.
"""

from xml.etree import ElementTree as ET
from typing import List

# Mapping between IMC type and size
imctype_sz = {
    'int8_t': 1,
    'uint8_t': 1,
    'int16_t': 2,
    'uint16_t': 2,
    'int32_t': 4,
    'uint32_t': 4,
    'int64_t': 8,
    'uint64_t': 8,
    'fp32_t': 4,
    'fp64_t': 8,
    # Variable fields have a minimum size of 2 bytes
    'rawdata': 2,
    'plaintext': 2,
    'vector': 2,
    'message': 2,
    'message-list': 2
}

# IMC types that can vary in size
variable_types = ['rawdata', 'plaintext', 'message', 'message-list', 'vector']


class IMC:
    """
    Representation of an entire IMC definition (xml file)
    """
    def __init__(self, imc_path):
        self.name = None
        self.long_name = None
        self.version = None
        self.description = None
        self.header = None  # type: IMCHeader
        self.footer = None  # type: IMCFooter
        self.groups = []  # type: List[IMCGroup]
        self.messages = []  # type: List[IMCMessage]
        self.types = []
        self.serialization = []
        self.units = {}
        self.enumerations = []  # type: List[IMCEnum]
        self.bitfields = []  # type: List[IMCEnum]
        self.message_groups = []
        self.flags = []

        self.parse(imc_path)
        self.validate()

    def validate(self):
        # Check that all message ids are unique
        mgids = set()
        abbrevs = set()
        for m in self.messages:
            if m.id in mgids:
                raise ValueError('Not all IMC message ids are unique ({} - {}).'.format(m.name, m.id))

            if m.abbrev in abbrevs:
                raise ValueError('Not all IMC message abbreviations are unique ({} - {}).'.format(m.name, m.abbrev))

            mgids.add(m.id)
            abbrevs.add(m.abbrev)

    def parse(self, imc_path):
        tree = ET.parse(imc_path)
        root = tree.getroot()
        self.name = root.attrib['name']
        self.long_name = root.attrib['long-name']
        self.version = root.attrib['version']
        for child in root:
            tag = child.tag
            if tag == 'description':
                self.description = child.text
            elif tag == 'types':
                self.types = [x.attrib['name'] for x in child.findall('type')]
            elif tag == 'serialization':
                self.serialization = [x.attrib['name'] for x in child.findall('type')]
            elif tag == 'units':
                self.units = {x.attrib['abbrev']: x.attrib['name'] for x in child.findall('unit')}
            elif tag == 'enumerations':
                self.enumerations = [IMCEnum(x) for x in child.findall('def')]
            elif tag == 'bitfields':
                self.bitfields = [IMCEnum(x) for x in child.findall('def')]
                for b in self.bitfields:
                    b.unit = 'Bitfield'
            elif tag == 'message-groups':
                for group in child.findall('message-group'):
                    self.message_groups.append(
                        (group.attrib['abbrev'], [x.attrib['abbrev'] for x in group.findall('message-type')]))
            elif tag == 'flags':
                self.flags = [(x.attrib['name'], x.attrib['abbrev']) for x in child.findall('flag')]
            elif tag == 'header':
                self.header = IMCHeader(child)
            elif tag == 'footer':
                self.footer = IMCFooter(child)
            elif tag == 'groups':
                self.groups = [IMCGroup(x) for x in child.findall('group')]
            elif tag == 'message':
                self.messages.append(IMCMessage(child))
            else:
                print('Unknown IMC tag "{}" encountered.'.format(tag))

        # Messages in a message-group should have that supertype as a parent
        for m in self.messages:
            for group, children in self.message_groups:
                if m.abbrev in children:
                    m.parent = group

    def sortby_message_dependencies(self):
        """
        Sorts the messages according to their dependencies.
        Messages with inline messages or message-lists will be placed at the end.
        :return:
        """
        msg_deps = {}  # The dependencies of the message
        msg_tmp = {}  # The IMCMessage classes
        for m in self.messages:
            message_fields = [x.message_type for x in m.fields if x.message_type]
            if message_fields:
                msg_deps[m.abbrev] = message_fields
                msg_tmp[m.abbrev] = m

        # Add messages with message dependencies back iteratively, while keeping track of inter dependencies
        self.messages = [x for x in self.messages if x.abbrev not in msg_deps.keys()]
        last_size = -1
        while msg_deps:
            keys = list(msg_deps.keys())

            # Ensure finite loop
            if len(keys) == last_size:
                raise RuntimeError('Failed to resolve inter-message dependencies (circular dependency?)')

            for k in keys:
                has_deps = any([x in keys for x in msg_deps[k]])
                if not has_deps:
                    msg_deps.pop(k)
                    self.messages.append(msg_tmp.pop(k))
                    break  # Strictly not necessary, but enables output to be semi-sorted


class IMCGroup:
    """
    Defines a division of the declared IMC IDs into a predefined range (e.g sensors 250-299)
    """
    def __init__(self, el=None):
        if el:
            self.name = el.attrib['name']
            self.abbrev = el.attrib['abbrev']
            self.min = int(el.attrib['min'])
            self.max = int(el.attrib['max'])

    def __contains__(self, item: int):
        # Allows the "in" keyword to be used to check for group membership
        return self.min <= item <= self.max


class IMCMessage:
    """
    The definition of an IMC message. Can contain one or multiple values
    """
    def __init__(self, el):
        self.id = el.attrib['id']
        self.name = el.attrib['name']
        self.abbrev = el.attrib['abbrev']
        self.source = el.attrib.get('source', None)
        self.description = '\n'.join([x.text for x in el.findall('description') if x])
        self.fields = [IMCField(x) for x in el.findall('field')]  # type: List[IMCField]
        self.flags = el.attrib.get('flags', None)
        self.used_by = el.attrib.get('used-by', None)
        self.parent = 'Message'  # Default parent class

    def is_variable(self) -> bool:
        return any([f.is_variable() for f in self.fields])


class IMCHeader:
    """
    Header which is present for all messages (e.g dst/src addresses)
    """
    def __init__(self, el):
        self.description = '\n'.join([x.text for x in el.findall('description')])
        self.fields = [IMCField(x) for x in el.findall('field')]  # type: List[IMCField]


class IMCFooter:
    """
    Footer which is present for all messages (e.g checksum)
    """
    def __init__(self, el):
        self.description = '\n'.join([x.text for x in el.findall('description')])
        self.fields = [IMCField(x) for x in el.findall('field')]  # type: List[IMCField]


class IMCField:
    """
    A field contains a value or enumeration/bitfield
    """
    def __init__(self, el):
        self.name = el.attrib['name']
        self.abbrev = el.attrib['abbrev']
        self.type = el.attrib['type']
        self.unit = el.attrib.get('unit', None)
        self.description = '\n'.join([x.text for x in el.findall('description') if x])
        self.note = el.attrib.get('note', None)  # Rarely used

        # If type is message or message-list, this field designates which type these messages are
        self.message_type = el.attrib.get('message-type', None)

        # If type is numeric vector, this field designates which type the contained values are
        self.vector_type = el.attrib.get('vector-type', None)

        # Value default / bounds
        self.fixed = el.attrib.get('fixed', None)  # Constant value (true/false)
        self.value = el.attrib.get('value', None)  # Default value
        self.min = el.attrib.get('min', None)  # Min value
        self.max = el.attrib.get('max', None)  # Max value

        # Defined by enum/bitfield (defined globally)
        self.enum_def = el.attrib.get('enum-def', None)
        self.bitfield_def = el.attrib.get('bitfield-def', None)

        # Field is defined by local enum
        self.values = [IMCValue(x) for x in el.findall('value')]
        self.prefix = el.attrib.get('prefix', None)

    def __repr__(self):
        return 'IMCField({}, {})'.format(self.abbrev, self.type)

    def is_variable(self) -> bool:
        """
        Is the field variable in size?
        Note: inline messages are counted as variable even if the message type is not.
        :return:
        """
        return True if self.type in variable_types else False

    def get_size(self):
        """
        Get the minimum field size in bytes (2 bytes for variable fields)
        :return:
        """
        return imctype_sz[self.type]

    def is_enum(self) -> bool:
        return self.unit == 'Enumerated'

    def is_bitfield(self) -> bool:
        return self.unit == 'Bitfield'

    def is_inline_enum(self) -> bool:
        return bool(self.values)

    def get_inline_enum(self):
        # Return inline enum seperately (defined outside _fields_)
        if self.values:
            # Defines an inline enumeration
            en = IMCEnum()
            en.abbrev = self.abbrev
            en.name = self.name
            en.prefix = self.prefix
            en.values = self.values
            en.unit = self.unit
            en.type = self.type
            en.is_inline = True
            return en


class IMCEnum:
    """
    Represents a declaration of an enumeration or bitfield
    """
    def __init__(self, el=None):
        self.is_inline = False

        if el:
            self.name = el.attrib['name']
            self.abbrev = el.attrib['abbrev']
            self.prefix = el.attrib['prefix']
            self.unit = el.attrib.get('unit', None)
            self.type = el.attrib.get('type', None)
            self.values = [IMCValue(x) for x in el.findall('value')]  # type: List[IMCValue]

    def is_bitfield(self):
        if self.unit:
            return True if self.unit and self.unit.lower() == 'bitfield' else False


class IMCValue:
    """
    Denotes a possible value an enumeration or bitfield can take.
    """
    def __init__(self, el):
        self.abbrev = el.attrib['abbrev']  # Abbreviation
        self.name = el.attrib['name']  # Full name
        self.id = el.attrib['id']  # The assosciated value, integer in hex or dec

        # Avoid leading digits in abbrev
        #if str.isdigit(self.abbrev[0]):
            #self.abbrev = '_' + self.abbrev

    def __repr__(self):
        return 'IMCValue({}, {})'.format(self.id, self.abbrev)


if __name__ == '__main__':
    pass
