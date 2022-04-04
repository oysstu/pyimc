#include <pybind11/detail/common.h>
#include <pybind11/pybind11.h>
namespace py = pybind11;

#include <string_view>
#include <vector>

void bytes_to_vector(const py::bytes& b, std::vector<char>& vec){
    std::string_view sv(b);
    vec.assign(sv.begin(), sv.end());
}

py::str ascii_to_unicode_safe(const std::string &s){
  // "replace": replaces characters with unicode question mark
  py::str str_out(PyUnicode_DecodeASCII(s.data(), s.length(), "replace"));
  return str_out;
}