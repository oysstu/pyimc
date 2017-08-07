#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <DUNE/IMC/Factory.hpp>

namespace py = pybind11;
using namespace DUNE::IMC;

void pbFactory(py::module &m) {
    py::class_<Factory>(m, "Factory")
    .def_static("produce", static_cast<Message* (*)(const std::string&)>(&Factory::produce))
    .def_static("abbrev_from_id", &Factory::getAbbrevFromId)
    .def_static("id_from_abbrev", &Factory::getIdFromAbbrev);
}