#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <DUNE/IMC/Factory.hpp>

namespace py = pybind11;
using namespace DUNE::IMC;

void pbFactory(py::module &m) {
    py::class_<Factory>(m, "Factory")
#ifdef PYBIND11_CPP14
    .def("produce", py::overload_cast<uint32_t>(&Factory::produce))
    .def("produce", py::overload_cast<const std::string&>(&Factory::produce))
#else
    .def_static("produce", static_cast<Message* (*)(uint32_t)>(&Factory::produce))
    .def_static("produce", static_cast<Message* (*)(const std::string&)>(&Factory::produce))
#endif
    .def_static("abbrev_from_id", &Factory::getAbbrevFromId)
    .def_static("id_from_abbrev", &Factory::getIdFromAbbrev);
}