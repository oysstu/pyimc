#include <pybind11/pybind11.h>

#include <DUNE/IMC/Constants.hpp>

namespace py = pybind11;

void pbConstants(py::module &m) {
    // Add constants
    py::module m_const = m.def_submodule("constants", "IMC constants");
    m_const.attr("VERSION") = py::str(DUNE_IMC_CONST_VERSION);
    m_const.attr("GIT_INFO") = py::str(DUNE_IMC_CONST_GIT_INFO);
    m_const.attr("MD5") = py::str(DUNE_IMC_CONST_MD5);
    m_const.attr("SYNC") = py::int_(DUNE_IMC_CONST_SYNC);
    m_const.attr("SYNC_REV") = py::int_(DUNE_IMC_CONST_SYNC_REV);
    m_const.attr("HEADER_SIZE") = py::int_(DUNE_IMC_CONST_HEADER_SIZE);
    m_const.attr("FOOTER_SIZE") = py::int_(DUNE_IMC_CONST_FOOTER_SIZE);
    m_const.attr("NULL_ID") = py::int_(DUNE_IMC_CONST_NULL_ID);
    m_const.attr("MAX_SIZE") = py::int_(DUNE_IMC_CONST_MAX_SIZE);
    m_const.attr("UNK_EID") = py::int_(DUNE_IMC_CONST_UNK_EID);
    m_const.attr("SYS_EID") = py::int_(DUNE_IMC_CONST_SYS_EID);
}
