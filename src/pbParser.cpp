#include <pybind11/pybind11.h>

#include <DUNE/IMC/Parser.hpp>

namespace py = pybind11;
using namespace DUNE::IMC;

// Implement parsing of sequence of bytes (faster than looping in python)
// Cannot derive as parser does not have virtual destructor
class PyParser {
public:
    PyParser(void) : m_parser() { /* empty */ }
    ~PyParser(void) { /* empty */ }

    // Wrappers
    void reset(void) { m_parser.reset();}
    //Message* parse(uint8_t byte) { return m_parser.parse(byte);}

    // New batch-parse function
    Message* parse(py::bytes data){
        m_msg = nullptr;

        for (const auto& b : data){
            m_msg = m_parser.parse(b.cast<uint8_t>());
            if(m_msg)
                break;
        }
        return m_msg;
    }

private:
    Parser m_parser;
    Message* m_msg;
};


void pbParser(py::module &m) {
    py::class_<PyParser>(m, "Parser")
    .def(py::init<>())
    .def("reset", &PyParser::reset)
    .def("parse", &PyParser::parse);
}