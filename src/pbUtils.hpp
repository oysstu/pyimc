#include <pybind11/pybind11.h>
namespace py = pybind11;

#include <vector>
#include <string>

// Assigns the bytes to the vector
void bytes_to_vector(const py::bytes& b, std::vector<char>& vec);

// Decodes ASCII string while replacing non-unicode characters
py::str ascii_to_unicode_safe(const std::string &str);