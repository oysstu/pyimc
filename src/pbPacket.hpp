#include <pybind11/pybind11.h>

#include <DUNE/IMC/Message.hpp>
#include <DUNE/IMC/Packet.hpp>

namespace py = pybind11;
using namespace DUNE::IMC;


Message* pbDeserialize(py::bytes b, Message* msg = nullptr);

py::bytes pbSerialize(const Message* msg);

// Unpickling
template <typename T>
void pbUnpickleMessage(T &self, py::tuple t) {
    if (t.size() != 1)
        throw std::runtime_error("Invalid state!");

    // Run in-place constructor
    new (&self) T();

    // Restore state
    pbDeserialize(t[0].cast<py::bytes>(), &self);
}

void pbPacket(py::module &m);