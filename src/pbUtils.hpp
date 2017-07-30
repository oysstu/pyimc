#include <pybind11/pybind11.h>
namespace py = pybind11;

// Assigns the bytes to the vector
void bytes_to_vector(py::bytes& b, std::vector<char>& vec);