#include <pybind11/pybind11.h>

#include <DUNE/Algorithms/CRC8.hpp>

namespace py = pybind11;

using namespace DUNE::Algorithms;

void pbAlgorithms(py::module &m) {
        py::module alg = m.def_submodule("algorithms", "algorithms");
        py::class_<CRC8>(alg, "CRC8")
        .def(py::init<uint8_t, uint8_t>(), py::arg("polynomial"), py::arg("value") = 0)
        //.def("putArray", &CRC8::putArray) TODO: Change to bytes or iterable wrapper
        .def("put_byte", &CRC8::putByte)
        .def_property("value", &CRC8::get, &CRC8::set);
}
