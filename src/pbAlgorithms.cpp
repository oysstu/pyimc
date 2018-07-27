#include "pbUtils.hpp"

#include <pybind11/pybind11.h>

#include <DUNE/Algorithms.hpp>

namespace py = pybind11;
using namespace pybind11::literals;

using namespace DUNE::Algorithms;

void pbAlgorithms(py::module &m) {
        py::module alg = m.def_submodule("algorithms", "algorithms");

#ifdef DUNE_ALGORITHMS_CRC8_HPP_INCLUDED_
        auto c = py::class_<CRC8>(alg, "CRC8");
        c.def(py::init<uint8_t, uint8_t>(), py::arg("polynomial"), py::arg("value") = 0);
        c.def("put_byte", &CRC8::putByte);
        c.def("put_array", [](CRC8 &crc8, const py::bytes data) {
                char* buffer;
                ssize_t length;
                if (PYBIND11_BYTES_AS_STRING_AND_SIZE(data.ptr(), &buffer, &length))
                    py::pybind11_fail("Unable to extract bytes contents!");

                return crc8.putArray(reinterpret_cast<uint8_t*>(buffer), static_cast<unsigned int>(length));
        }, "data"_a, "Compute the CRC8 of an array of bytes.");
        c.def_property("value", &CRC8::get, &CRC8::set);
#endif
}
