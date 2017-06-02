#include <pybind11/pybind11.h>
#include "generated/pbGenerated.hpp"

namespace py = pybind11;

// Forward declarations
void pbMessage(py::module &);
void pbPacket(py::module &);
void pbParser(py::module &);
void pbFactory(py::module &);
void pbConstants(py::module &);
void pbAlgorithms(py::module &);

PYBIND11_PLUGIN(imc) {
    py::module m("imc", "IMC bindings for python");

    // Bind classes
    pbMessage(m);
    pbPacket(m);
    pbParser(m);
    pbFactory(m);
    pbAlgorithms(m);

    // Bind constants
    pbConstants(m);

    // Add classes
    pbGenerated(m);

    return m.ptr();
}
