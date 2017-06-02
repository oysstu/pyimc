#include <pybind11/pybind11.h>

#include <DUNE/Algorithms/CRC8.hpp>

namespace py = pybind11;

using namespace DUNE::Algorithms;

void pbAlgorithms(py::module &m) {
        py::module alg = m.def_submodule("algorithms", "algorithms");
        py::class_<CRC8>(alg, "CRC8")
        .def(py::init<uint8_t, uint8_t>())
        .def("putArray", &CRC8::putArray)
        .def("putByte", &CRC8::putByte)
        .def_property("value", &CRC8::get, &CRC8::set);
}
