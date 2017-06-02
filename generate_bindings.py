"""
Parse IMC xml and write pybind11 wrapper code

The function get_cxx_type is copied from the DUNE source code, see license under DUNE_LICENSE
"""

import sys, os, argparse
from xml.etree import ElementTree


def import_module(module_path: str, module_name: str):
    """
    Imports a python module from a path.
    :param module_path: The path to the python file.
    :param module_name: The name of the module.
    :return: Loaded module
    """
    # Use importlib if python 3.5+, else imp
    if sys.version_info[0] > 3 or (sys.version_info[0] == 3 and sys.version_info[1] >= 5):
        import importlib.util
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        foo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(foo)
        return foo
    else:
        import imp
        foo = imp.load_source(module_name, module_path)
        return foo


# Cannot import this function from dune file, as there is no if __name__ == '__main__' guard
def get_cxx_type(field_node):
    type = field_node.get('type')
    msg_type = field_node.get('message-type', 'Message')
    if type == 'plaintext':
        return 'std::string'
    elif type == 'rawdata':
        return 'std::vector<char>'
    elif type == 'message':
        return 'InlineMessage<%s>' % msg_type
    elif type == 'message-list':
        return 'MessageList<%s>' % msg_type
    else:
        return type


def generate_bindings(imc_xml_path: str, dune_path: str, whitelist=None):
    """
    Parses the IMC XML specification and generates pybind c++ code under src/generated
    :param imc_xml_path: The path to the IMC.xml specification
    :param dune_path: Path to dune root (to import generator utils)
    :param whitelist: Optional list of messages to keep (others are ignored).
    :return: 
    """

    # Import utilities from dune python scripts
    dune_generators = os.path.abspath(os.path.join(dune_path, 'programs/generators'))
    if not os.path.exists(dune_generators):
        raise NotADirectoryError('Given DUNE path does not exist.')

    imcutils = import_module(os.path.join(dune_generators, 'imc/utils.py'), 'imc.utils')
    imcdeps = import_module(os.path.join(dune_generators, 'imc/deps.py'), 'imc.deps')

    if not os.path.exists('src/generated'):
        os.makedirs('src/generated')

    tree = ElementTree.parse(imc_xml_path)
    root = tree.getroot()

    fncnames = []  # List of sub-functions to call with the module parameter

    # Write supertypes
    src = []
    fncnames.append('pbSuperTypes')
    with open('src/generated/pbSuperTypes.cpp', 'wt') as fout:
        src.extend(['#include <DUNE/IMC/SuperTypes.hpp>\n'
                    '#include <pybind11/pybind11.h>',
                    'namespace py = pybind11;',
                    'using namespace DUNE::IMC;\n',
                    'void pbSuperTypes(py::module &m)' + '{'])

        for group in root.findall("message-groups/message-group"):
            name = group.get('abbrev')
            comment = group.get('name')
            src.append('py::class_<{0}, Message>(m, "{0}", "Super type {1}");'.format(name, comment))

        src.append('}\n')

        fout.writelines('\n'.join(src))

    # Write module-level enumerations
    src = []
    fncnames.append('pbEnumerations')
    with open('src/generated/pbEnumerations.cpp', 'wt') as fout:
        src.extend(['#include <DUNE/IMC/Enumerations.hpp>',
                    '#include <pybind11/pybind11.h>',
                    'namespace py = pybind11;',
                    'using namespace DUNE::IMC;\n',
                    'void pbEnumerations(py::module &m)' + '{'])

        for en in root.findall('enumerations/def'):
            name = en.get('abbrev')
            comment = en.get('name')

            if name == 'Boolean':
                continue

            src.append('\tpy::enum_<{0}>(m, "{0}", "{1}")'.format(name, comment))
            for field in en.findall('value'):
                fname = en.get('prefix') + '_' + field.get('abbrev')
                fcomment = field.get('name')
                src.append('\t\t.value("{1}", {0}::{1})'.format(name, fname))

            src.append('\t\t.export_values();\n')

        src.append('}\n')
        fout.write('\n'.join(src))

    # Write module-level bitfields
    src = []
    fncnames.append('pbBitfields')
    with open('src/generated/pbBitfields.cpp', 'wt') as fout:
        src.extend(['#include <DUNE/IMC/Bitfields.hpp>',
                    '#include <pybind11/pybind11.h>',
                    'namespace py = pybind11;',
                    'using namespace DUNE::IMC;\n',
                    'void pbBitfields(py::module &m)' + '{'])

        for en in root.findall('bitfields/def'):
            name = en.get('abbrev')
            comment = en.get('name')

            if name == 'Boolean':
                continue

            src.append('\tpy::enum_<{0}>(m, "{0}", "{1}", py::arithmetic())'.format(name, comment))
            for field in en.findall('value'):
                fname = en.get('prefix') + '_' + field.get('abbrev')
                fcomment = field.get('name')
                src.append('\t\t.value("{1}", {0}::{1})'.format(name, fname))

            src.append('\t\t.export_values();\n')

        src.append('}\n')
        fout.write('\n'.join(src))

    # Write IMC message classes
    deps = imcdeps.Dependencies(root)
    abbrevs = deps.get_list()
    messageLists = {}
    for abbrev in abbrevs:
        node = root.find("message[@abbrev='%s']" % abbrev)

        hpp = []
        base = []
        for group in root.findall('message-groups/message-group'):
            if group.find("message-type[@abbrev='%s']" % node.get('abbrev')) is not None:
                base.append(group.get('abbrev'))

        if len(base) == 0:
            base.append('Message')

        classcomment = node.get('name')
        classname = node.get('abbrev')
        if not whitelist or classname.lower() in whitelist:
            fncnames.append('pb{}'.format(classname))
            with open('src/generated/pb{}.cpp'.format(classname), 'wt') as fout:
                # Write header
                fout.writelines('\n'.join(('#include <DUNE/IMC/Message.hpp>',
                                           '#include <DUNE/IMC/Definitions.hpp>',
                                           '#include <DUNE/IMC/SuperTypes.hpp>',
                                           '#include <pybind11/pybind11.h>', ' ',
                                           'namespace py = pybind11;',
                                           'using namespace DUNE::IMC;\n')))

                hpp.append('void pb{}(py::module &m)\n'.format(classname) + '{')

                # Write class entry
                hpp.append('\tauto v{0} = py::class_<{0}, {1}>(m, "{0}", "{2}");'.format(classname, base[0], classcomment))
                hpp.append('\t\tv{}.def(py::init<>());'.format(classname))

                # Parse members
                for f in node.findall('field'):
                    fieldtype = f.get('message-type')
                    fieldname = imcutils.get_name(f)
                    fieldcxxtype = get_cxx_type(f)
                    fielddesc = f.get('name')
                    hpp.append('\t\tv{0}.def_readwrite("{1}", &{0}::{1});'.format(classname, fieldname))
                    if fieldtype:
                        # MessageList<T> bindings are generated afterwards to ensure unique bindings
                        messageLists[fieldtype] = (fieldname, fieldcxxtype, fielddesc)

                # Parse inline enums
                enums = []
                iens = node.findall("field[@unit='Enumerated']")
                for ien in iens:
                    if ien.get('enum-def', None) is not None:
                        continue
                    enumname = imcutils.get_enum_name(ien.get('name'))
                    enumcomment = ien.get('name')
                    hpp.append('\n\tpy::enum_<{0}::{1}>(v{0}, "{1}", "{2}")'.format(classname, enumname, enumcomment))

                    for field in ien.findall('value'):
                        fieldname = ien.get('prefix') + '_' + field.get('abbrev')
                        fieldval = field.get('id')
                        fieldcomment = field.get('name')
                        hpp.append('\t\t.value("{0}", {1}::{2}::{0})'.format(fieldname, classname, enumname))

                    hpp.append('\t\t.export_values();')

                # Parse inline bitfields.
                bitfields = []
                bfs = node.findall("field[@unit='Bitfield']")
                for bf in bfs:
                    if bf.get('bitfield-def', None) is not None:
                        continue
                    bfname = imcutils.get_bfield_name(bf.get('name'))
                    bfcmt = bf.get('name')  # comment

                    hpp.append('\n\tpy::enum_<{0}::{1}>(v{0}, "{1}", "{2}", py::arithmetic())'.format(classname, bfname, bfcmt))
                    for field in bf.findall('value'):
                        fieldname = bf.get('prefix') + '_' + field.get('abbrev')
                        fieldval = field.get('id')
                        fieldcomment = field.get('name')
                        hpp.append('\t\t.value("{0}", {1}::{2}::{0})'.format(fieldname, classname, bfname))

                    hpp.append('\t\t.export_values();')

                fout.write('\n'.join(hpp))
                fout.write('\n}\n')

    with open('src/generated/pbGenerated.hpp', 'wt') as fgen:
        fgen.writelines('\n'.join(('#pragma once', ' '
                                   '#include <pybind11/pybind11.h>',
                                   '#include <DUNE/IMC/Definitions.hpp>',
                                   '#include "../pbMessageList.hpp"', '',
                                   'namespace py = pybind11;',
                                   'using namespace DUNE::IMC;\n\n')))

        # Write forward declarations
        fgen.write('/* Forward declarations to pbGenerated-functions */\n')
        fgen.writelines(['void {}(py::module&);\n'.format(x) for x in fncnames])

        # Write the function that calls all other subgenerated functions
        fgen.write('\n\nvoid pbGenerated(py::module &m) {\n')

        # Write the MessageList<T> instantiations used inside messages
        fgen.write('/* Instantiations of MessageList<T> bindings */\n')
        fgen.writelines(['\tpbMessageList<{0}>(m);\n'.format(k) for k,v in messageLists.items()])

        fgen.write('\n/* Calls to generated class bindings */\n')

        # Write the actual function call
        fgen.writelines(['\t{}(m);\n'.format(x) for x in fncnames])

        fgen.write('}\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate IMC pybind11 wrapper code.')
    parser.add_argument('--imc_path', type=str, required=True, help='Path to the IMC XML specification.')
    parser.add_argument('--dune_path', type=str, required=True, help='Path to the dune root folder.')
    parser.add_argument('--whitelist', type=str, required=False, default=None,
                        help='Path to a text file with messages to keep (optional).')
    args = parser.parse_args()

    whitelist = []
    if args.whitelist:
        with open(args.whitelist, 'rt') as f:
            # Ignore empty lines and lines that starts with hashtag
            whitelist = [x.strip().lower() for x in f.readlines() if x.strip() and not x.startswith('#')]

    print('Whitelist: ', whitelist)

    generate_bindings(args.imc_path, args.dune_path, whitelist)
