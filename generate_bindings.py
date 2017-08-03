import argparse
import os

from imc_schema import IMC


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
            enum_fields = [f for f in m.fields if f.values]
            for f in enum_fields:
                e = f.get_inline_enum()
                arit = ', py::arithmetic()' if e.is_bitfield() else ''
                fullname = e.name.replace(' ', '') + ('Bits' if e.is_bitfield() else 'Enum')
                s.append('\n\tpy::enum_<{0}::{1}>(v{0}, "{1}", "{2}"{3})'.format(m.abbrev, fullname, e.name, arit))
                for v in e.values:
                    s.append('\t\t.value("{0}", {2}::{3}::{1}_{0})'.format(v.abbrev, e.prefix, m.abbrev, fullname))
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
        fnames += [m.abbrev for m in self.messages if not whitelist or m.abbrev.lower() in whitelist]
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

    def __init__(self, imc_path, whitelist=None, out_dir='src/generated'):
        super().__init__(imc_path)
        self.odir = out_dir
        self.whitelist = whitelist
        if not os.path.exists(self.odir):
            os.makedirs(self.odir)

        self.imc = []

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
        pass

    def write_enumerations(self):
        """
        Generate the global enumerations
        """
        pass

    def write_bitfields(self):
        """
        Generate the global bitfields
        """
        pass

    def write_messages(self):
        pass

    def write_generated(self):
        """
        Generate a single point of entry for pybind for all generated bindings
        """
        pass


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






