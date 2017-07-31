#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <DUNE/IMC/Factory.hpp>

namespace py = pybind11;
using namespace DUNE::IMC;

void pbFactory(py::module &m) {
    py::class_<Factory>(m, "Factory")
    //.def("produce", py::overload_cast<uint32_t>(&Factory::produce))
    //.def("produce", py::overload_cast<const std::string&>(&Factory::produce))
    //.def("produce", static_cast<void (*)(uint32_t)>(&Factory::produce))
    .def_static("produce", static_cast<Message* (*)(const std::string&)>(&Factory::produce))
    //.def_static("getAbbrevs", &Factory::getAbbrevs)
    //.def("getIds", py::overload_cast<std::vector<uint32_t>&>(&Factory::getIds))
    //.def("getIds", py::overload_cast<std::string, std::vector<uint32_t>&>(&Factory::getIds))
    //.def_static("getIds", static_cast<void (*) (std::vector<uint32_t>&)>(&Factory::getIds))
    .def_static("getAbbrevFromId", &Factory::getAbbrevFromId)
    .def_static("getIdFromAbbrev", &Factory::getIdFromAbbrev);
}