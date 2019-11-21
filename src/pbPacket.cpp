#include <pybind11/pybind11.h>

#include <DUNE/IMC/Message.hpp>
#include <DUNE/IMC/Packet.hpp>

namespace py = pybind11;
using namespace DUNE::IMC;


Message* pbDeserialize(py::bytes b, Message* msg) {
    // The buffer is the internal storage of the bytes. Do not modify
    char* bfr;
    ssize_t bfr_len;
    if (PYBIND11_BYTES_AS_STRING_AND_SIZE(b.ptr(), &bfr, &bfr_len))
        py::pybind11_fail("Unable to extract bytes contents");

    return DUNE::IMC::Packet::deserialize((uint8_t*)bfr, bfr_len, msg);
}

py::bytes pbSerialize(const Message* msg){
    // Allocate buffer
    ssize_t sz = msg->getSerializationSize();
    py::bytes b(nullptr, sz);  // nullptr -> uninitalized bytes

    // Reference internal bytes
    char* bfr;
    if (PYBIND11_BYTES_AS_STRING_AND_SIZE(b.ptr(), &bfr, &sz))
        py::pybind11_fail("Unable to extract bytes contents");

    // Write
    uint16_t n_written = Packet::serialize(msg, (uint8_t*)bfr, sz);

    return b;
};


void pbPacket(py::module &m) {
    py::class_<Packet>(m, "Packet")
    // Note: take_ownership for instances that are already registered in pybind is referenced without "double owning"
    .def_static("deserialize", &pbDeserialize, py::arg("b"), py::arg("msg") = (Message*)nullptr,  py::return_value_policy::take_ownership)
    .def_static("serialize", &pbSerialize, py::return_value_policy::take_ownership);
}

