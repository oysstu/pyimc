#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <DUNE/IMC/Message.hpp>
#include <DUNE/IMC/Packet.hpp>
#include <DUNE/Utils/ByteBuffer.hpp>

namespace py = pybind11;
using namespace DUNE::IMC;

py::bytes fserialize(const Message* msg){ 
    unsigned sz = msg->getSerializationSize();
    uint8_t* buf = (uint8_t*)std::malloc(sz);
    uint16_t n_written = Packet::serialize(msg, buf, sz);

    return py::bytes(reinterpret_cast<const char*>(buf), static_cast<size_t>(n_written));
};

void pbPacket(py::module &m) {
    py::class_<Packet>(m, "Packet")
    .def(py::init<>())
    .def("serialize", &fserialize)
    //.def("serialize", py::overload_cast<const Message*, uint8_t*, uint16_t>(&Packet::serialize))
    //.def("serialize", py::overload_cast<const Message*, std::ostream&>(&Packet::serialize))
    //.def("deserialize", py::overload_cast<const uint8_t*, uint16_t, Message*>(&Packet::deserialize))
    //.def("deserialize", static_cast<Message* (Packet::*)(const uint8_t*, uint16_t, Message* = NULL)>(&Packet::deserialize))
    //.def("deserialize", py::overload_cast<std::istream&>(&Packet::deserialize))
    .def("serializeHeader", &Packet::serializeHeader)
    .def("deserializeHeader", &Packet::deserializeHeader)
    .def("deserializePayload", &Packet::deserializePayload);
}

