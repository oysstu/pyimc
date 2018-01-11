import argparse
import os
import string

from .imc_schema import IMC


# C++ template code for InlineMessage fields
inline_message_template = """
v{message}.def_property("{field}", 
[](const {message} &x){{return x.{field}.isNull() ? nullptr : x.{field}.get();}}, 
[]({message} *x, const py::handle &y){{
    if(y.is_none()){{
        x->{field}.clear();
    }} else {{
        try {{
            x->{field}.set(y.cast<{inline_type}*>()); 
        }}
        catch(const py::cast_error &e){{
            PyErr_Clear();
            throw py::cast_error("Failed to cast to C++ type. Expected types are {inline_type} or NoneType.");
        }}
        x->{field}.setParent(x);
    }}
}}, py::keep_alive<1, 2>());
"""

# C++ template for rawdata fields
rawdata_template = """
v{message}.def_property("{field}",
    [](const {message} &x){{return py::bytes(x.{field}.data(), x.{field}.size());}},
    []({message} &x, py::bytes &b){{bytes_to_vector(b, x.{field});}}, py::return_value_policy::take_ownership);
"""

class IMCPybind(IMC):
    """
    Generates python bindings for DUNE+IMC using pybind11.
    """
    common_include = ['pybind11/pybind11.h']
    common_namespace = ['namespace py = pybind11;', 'using namespace DUNE::IMC;']

    def __init__(self, imc_path, whitelist=None, out_dir='src/generated'):
        super().__init__(imc_path)
        self.odir = out_dir
        self.whitelist = whitelist
        if not os.path.exists(self.odir):
            os.makedirs(self.odir)

    def write_bindings(self):
        self.write_supertypes()
        self.write_enumerations()
        self.write_bitfields()
        self.write_messages()
        self.write_generated()


    def write_supertypes(self):
        """
        Generate the message supertypes bindings
        """
        include = self.common_include + ['DUNE/IMC/SuperTypes.hpp']
        s = ['#include <{}>'.format(x) for x in include]
        s += self.common_namespace

        s.append('\nvoid pbSuperTypes(py::module &m) {')
        for abbrev, children in self.message_groups:
            s.append('\tpy::class_<{0}, Message>(m, "{0}", "Super type {1}");'.format(abbrev, abbrev))
        s.append('}')

        opath = os.path.join(self.odir, 'pbSuperTypes.cpp')
        with open(opath, 'wt') as f:
            f.write('\n'.join(s))

    def write_enumerations(self):
        """
        Generate the global enumerations
        """
        include = self.common_include + ['DUNE/IMC/Enumerations.hpp']
        s = ['#include <{}>'.format(x) for x in include]
        s += self.common_namespace
        s.append('\nvoid pbEnumerations(py::module &m) {')

        for e in self.enumerations:
            if e.abbrev == 'Boolean':
                continue
            s.append('\tpy::enum_<{0}>(m, "{0}", "{1}")'.format(e.abbrev, e.name))

            for v in e.values:
                s.append('\t\t.value("{2}", {0}::{1}_{2})'.format(e.abbrev, e.prefix, v.abbrev))
            s[-1] = s[-1] + ';'
        s.append('}\n')

        opath = os.path.join(self.odir, 'pbEnumerations.cpp')
        with open(opath, 'wt') as f:
            f.write('\n'.join(s))

    def write_bitfields(self):
        """
        Generate the global bitfields
        """
        include = self.common_include + ['DUNE/IMC/Bitfields.hpp']
        s = ['#include <{}>'.format(x) for x in include]
        s += self.common_namespace
        s.append('\nvoid pbBitfields(py::module &m) {')

        for e in self.bitfields:
            s.append('\tpy::enum_<{0}>(m, "{0}", "{1}", py::arithmetic())'.format(e.abbrev, e.name))

            for v in e.values:
                s.append('\t\t.value("{2}", {0}::{1}_{2})'.format(e.abbrev, e.prefix, v.abbrev))
            s[-1] = s[-1] + ';'
        s.append('}\n')

        opath = os.path.join(self.odir, 'pbBitfields.cpp')
        with open(opath, 'wt') as f:
            f.write('\n'.join(s))

    def write_messages(self):
        for m in self.messages:
            if self.whitelist and m.abbrev.lower() not in self.whitelist:
                continue

            include = self.common_include + ['DUNE/IMC/Message.hpp',
                                             'DUNE/IMC/SuperTypes.hpp',
                                             'DUNE/IMC/Definitions.hpp']
            s = ['#include <{}>'.format(x) for x in include]
            s.append('#include "../pbUtils.hpp"')
            s += self.common_namespace

            s.append('\nvoid pb{}(py::module &m) {{'.format(m.abbrev))
            s.append('\tauto v{0} = py::class_<{0}, {1}>(m, "{0}", "{2}");'.format(m.abbrev, m.parent, m.name))
            s.append('\tv{}.def(py::init<>());'.format(m.abbrev))

            # Members
            for f in m.fields:
                if f.type == 'rawdata':
                    rawdata = rawdata_template.format(message=m.abbrev, field=f.abbrev.lower())
                    s.extend(['\t' + x for x in rawdata.splitlines()])
                elif f.type == 'message':
                    inline_type = f.message_type if f.message_type else 'Message'
                    inline_message = inline_message_template.format(message=m.abbrev,
                                                                    field=f.abbrev.lower(),
                                                                    inline_type=inline_type)
                    s.extend(['\t' + x for x in inline_message.splitlines()])
                else:
                    s.append('\tv{0}.def_readwrite("{1}", &{0}::{1});'.format(m.abbrev, f.abbrev.lower()))

            # Inline enums/bitfields
            enum_fields = [f for f in m.fields if f.values and (f.unit == 'Enumerated' or f.unit == 'Bitfield')]
            for f in enum_fields:
                e = f.get_inline_enum()
                arit = ', py::arithmetic()' if e.is_bitfield() else ''
                # Some enumerations start with lower case, use upper case for python name
                pyname = string.capwords(e.name.replace('_', ' ')).replace(' ', '')
                pyname += 'Bits' if e.is_bitfield() else 'Enum'
                # Fields starting with digits is invalid in Python, prepend underscore
                if pyname[0].isdigit():
                    pyname = '_' + pyname
                cppname = e.name.replace(' ', '') + ('Bits' if e.is_bitfield() else 'Enum')
                s.append('\n\tpy::enum_<{0}::{1}>(v{0}, "{2}", "{3}"{4})'.format(m.abbrev, cppname, pyname, e.name, arit))
                for v in e.values:
                    # Fields starting with digits is invalid in Python, prepend underscore
                    pyval = '_' + v.abbrev if v.abbrev[0].isdigit() else v.abbrev
                    s.append('\t\t.value("{0}", {1}::{2}::{3}_{4})'.format(pyval, m.abbrev, cppname, e.prefix, v.abbrev))
                s[-1] = s[-1] + ';'

            s.append('}')

            opath = os.path.join(self.odir, 'pb{}.cpp'.format(m.abbrev))
            with open(opath, 'wt') as f:
                f.write('\n'.join(s))

    def write_generated(self):
        """
        Generate a single point of entry for pybind for all generated bindings
        """
        include = self.common_include + ['DUNE/IMC/Definitions.hpp']
        s = ['#pragma once']
        s += ['#include <{}>'.format(x) for x in include]
        s.append('#include "../pbMessageList.hpp"')
        s += self.common_namespace
        s.append('')

        # Write forward declarations
        fnames = ['Enumerations', 'SuperTypes', 'Bitfields']
        fnames += [m.abbrev for m in self.messages if not self.whitelist or m.abbrev.lower() in self.whitelist]
        s.extend(['void pb{}(py::module&);'.format(x) for x in fnames])

        # Entry point
        s.append('\nvoid pbGenerated(py::module &m) {')

        # Instantiate MessageList<T>
        msglst = [x.message_type for y in self.messages for x in y.fields if x.message_type]
        msglst.append('Message')
        msglst = set(msglst)  # Unique entries
        s.extend(['\tpbMessageList<{0}>(m);'.format(ml) for ml in msglst])

        # Calls to messages
        s.extend(['\tpb{}(m);'.format(x) for x in fnames])
        s.append('}')

        opath = os.path.join(self.odir, 'pbGenerated.hpp')
        with open(opath, 'wt') as f:
            f.write('\n'.join(s))


class IMCPyi(IMC):
    """
    Generates python type hinting (pyi) for DUNE+IMC bindings
    """
    # Mapping between IMC type and pure python type
    imctype_pyi = {
        'int8_t': 'int',
        'uint8_t': 'int',
        'int16_t': 'int',
        'uint16_t': 'int',
        'int32_t': 'int',
        'uint32_t': 'int',
        'int64_t': 'int',
        'uint64_t': 'int',
        'fp32_t': 'float',
        'fp64_t': 'float',
        'rawdata': 'bytes',
        'plaintext': 'str',
        'message': 'Message',
        'message-list': 'MessageList'
    }

    def __init__(self, imc_path, whitelist=None):
        super().__init__(imc_path)
        self.whitelist = whitelist

        self.sortby_message_dependencies()

        self.s = []

    def write_pyi(self):
        self.write_enumerations()
        self.write_bitfields()
        self.write_supertypes()
        self.write_messages()

        with open('utils/imc_static.pyi', 'rt') as fi, open('_pyimc.pyi', 'wt') as fo:
            fo.write(fi.read())
            fo.write('\n'.join(self.s))

    def write_supertypes(self):
        """
        Generate the message supertypes
        """
        for abbrev, children in self.message_groups:
            self.s.append('class {0}(Message):'.format(abbrev, abbrev))
            self.s.append('\tpass\n')

    def write_enumerations(self):
        """
        Generate the global enumerations
        """
        for e in self.enumerations:
            if e.abbrev == 'Boolean':
                continue
            self.s.append('class {0}:'.format(e.abbrev))
            for v in e.values:
                self.s.append('\t{0} = None  # type: int'.format(v.abbrev))
            self.s.append('')

    def write_bitfields(self):
        """
        Generate the global bitfields
        """
        for e in self.bitfields:
            self.s.append('class {0}:'.format(e.abbrev))

            for v in e.values:
                self.s.append('\t{0} = None  # type: int'.format(v.abbrev))
            self.s.append('')

    def write_messages(self):
        for m in self.messages:
            if self.whitelist and m.abbrev.lower() not in self.whitelist:
                continue

            self.s.append('class {0}({1}):'.format(m.abbrev, m.parent, m.name))

            # Members
            for f in m.fields:
                fabbr = f.abbrev.lower()
                inline_type = f.message_type if f.message_type else 'Message'
                self.s.append('\t@property')
                if f.type == 'message':
                    self.s.append('\tdef {0}(self) -> {1}: ...'.format(fabbr, inline_type))
                    self.s.append('\t@{}.setter'.format(fabbr))
                    self.s.append('\tdef {0}(self, {0}: {1}) -> None: ...'.format(fabbr, inline_type))
                elif f.type == 'message-list':
                    self.s.append('\tdef {0}(self) -> MessageList[{1}]: ...'.format(fabbr, inline_type))
                    self.s.append('\t@{}.setter'.format(fabbr))
                    self.s.append('\tdef {0}(self, {0}: MessageList[{1}]) -> None: ...'.format(fabbr, inline_type))
                else:
                    self.s.append('\tdef {}(self) -> {}: ...'.format(fabbr, self.imctype_pyi[f.type]))
                    self.s.append('\t@{}.setter'.format(fabbr))
                    self.s.append('\tdef {0}(self, {0}: {1}) -> None: ...'.format(fabbr, self.imctype_pyi[f.type]))

            # Inline enums/bitfields
            enum_fields = [f for f in m.fields if f.values and (f.unit == 'Enumerated' or f.unit == 'Bitfield')]
            for f in enum_fields:
                e = f.get_inline_enum()
                # Some enumerations start with lower case, use upper case for python name
                pyname = string.capwords(e.name.replace('_', ' ')).replace(' ', '')
                pyname += 'Bits' if e.is_bitfield() else 'Enum'
                self.s.append('\tclass {0}:'.format(pyname))
                for v in e.values:
                    # Fields starting with digits is invalid in Python, prepend underscore
                    pyval = '_' + v.abbrev if v.abbrev[0].isdigit() else v.abbrev
                    self.s.append('\t\t{0} = None'.format(pyval))

            if not m.fields and not enum_fields:
                self.s.append('\tpass')

            self.s.append('')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate IMC pybind11 wrapper code.')
    parser.add_argument('--imc_path', type=str, required=True, help='Path to the IMC XML specification.')
    parser.add_argument('--whitelist', type=str, required=False, default=None,
                        help='Path to a text file with messages to keep (optional).')
    args = parser.parse_args()

    whitelist = []
    if args.whitelist:
        with open(args.whitelist, 'rt') as f:
            # Ignore empty lines and lines that starts with hashtag
            whitelist = [x.strip().lower() for x in f.readlines() if x.strip() and not x.startswith('#')]

            print('Whitelist passed with the following messages:')
            print(whitelist)

    pb = IMCPybind(args.imc_path, whitelist=whitelist)
    pb.write_bindings()

    pyi = IMCPyi(args.imc_path, whitelist=whitelist)
    pyi.write_pyi()





