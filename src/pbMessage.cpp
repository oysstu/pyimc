#include <DUNE/IMC/Message.hpp>
#include <pybind11/pybind11.h>
#include <pybind11/operators.h>
#include <DUNE/IMC/Packet.hpp>
#include <DUNE/Time/Format.hpp>
#include <string>
#include <sstream>
#include <algorithm>
#include <iomanip>

namespace py = pybind11;
using namespace DUNE::IMC;

// Helper class to avoid pure virtual issues when inheriting in python
class PyMessage : public Message {
public:
    /* Inherit the constructors */
    using Message::Message;
    using Message::operator==;
    using Message::operator!=;

    /* Trampolines (need one for each virtual function) */
    // PYBIND11_OVERLOAD_PURE(return type, parent class, function name, *args)
    Message* clone(void) const override { 
        PYBIND11_OVERLOAD_PURE(Message*, Message, clone); 
        }
    void clear(void) override { 
        PYBIND11_OVERLOAD_PURE(void, Message, clear); 
        }
    int validate(void) const override { 
        PYBIND11_OVERLOAD_PURE(int, Message, Validate); 
        }
    bool fieldsEqual(const Message& other) const override {
        PYBIND11_OVERLOAD_PURE(bool, Message, fieldsEqual, other);
        }
    const char* getName(void) const override {
        PYBIND11_OVERLOAD_PURE(const char*, Message, getName); 
        }
    uint16_t getId(void) const override { 
        PYBIND11_OVERLOAD_PURE(uint16_t, Message, getId); 
        }
    uint8_t* serializeFields(uint8_t* bfr) const override {
        PYBIND11_OVERLOAD_PURE(uint8_t*, Message, serializeFields, bfr);
        }
    uint16_t deserializeFields(const uint8_t* bfr, uint16_t len) override {
        PYBIND11_OVERLOAD_PURE(uint16_t, Message, deserializeFields, bfr, len);
        }
    uint16_t reverseDeserializeFields(const uint8_t* bfr, uint16_t len) override {
        PYBIND11_OVERLOAD_PURE(uint16_t, Message, reverseDeserializeFields, bfr, len);
        }
};

class PyMessagePublic : public Message { // helper type for exposing protected function
public:
    using Message::fieldsEqual; // inherited with different access modifier
};

py::bytes fserialize(const Message* msg){
    unsigned sz = msg->getSerializationSize();
    uint8_t* buf = (uint8_t*)std::malloc(sz);
    uint16_t n_written = Packet::serialize(msg, buf, sz);

    return py::bytes(reinterpret_cast<const char*>(buf), static_cast<size_t>(n_written));
};

py::bytes fserializeFields(const Message* msg){
    unsigned sz = msg->getPayloadSerializationSize();
    uint8_t* buf = (uint8_t*)std::malloc(sz);
    msg->serializeFields(buf);

    return py::bytes(reinterpret_cast<const char*>(buf), static_cast<size_t>(sz));
};

std::string messageToString(const Message &msg) {
    std::ostringstream os;
    os << msg.getName() << std::endl;
    os << std::setfill('0') << std::uppercase << std::hex;
    os << std::setw(4) << msg.getSource() << ":";
    os << std::setw(2) << static_cast<uint16_t>(msg.getSourceEntity()) << " -> ";
    os << std::setw(4) << msg.getDestination() << ":";
    os << std::setw(2) << static_cast<uint16_t>(msg.getDestinationEntity());
    os << std::nouppercase << std::dec;

    if(msg.getTimeStamp() > 0.0)
        os << std::endl << DUNE::Time::Format::getTimeDate(msg.getTimeStamp());

    msg.fieldsToJSON(os, 4);
    std::string s = os.str();
    s.erase(std::remove_if(s.begin(), s.end(), [](const char& c) {
            return c == ',' || c == '"';
        }), s.end());

    return s;
};



void pbMessage(py::module &m) {
    py::class_<Message, PyMessage>(m, "Message")
            .def(py::init<>())
            .def("clone", &Message::clone)
            .def("clear", &Message::clear)
            .def("validate", &Message::validate)
            .def("fields_equal", &PyMessagePublic::fieldsEqual)
            .def_property_readonly("msg_name", &Message::getName)   // msg_ prefix to avoid name collision
            .def_property_readonly("msg_id", &Message::getId)       // msg_ prefix to avoid name collision
#ifdef PYBIND11_CPP14
            .def("set_timestamp_now", py::overload_cast<>(&Message::setTimeStamp))
            .def_property("timestamp", &Message::getTimeStamp, py::overload_cast<double>(&Message::setTimeStamp))
#else
            .def("set_timestamp_now", static_cast<double (Message::*)(void)>(&Message::setTimeStamp))
            .def_property("timestamp", &Message::getTimeStamp, static_cast<double (Message::*)(double)>(&Message::setTimeStamp))
#endif
            .def_property("src", &Message::getSource, &Message::setSource)
            .def_property("src_ent", &Message::getSourceEntity, &Message::setSourceEntity)
            .def_property("dst", &Message::getDestination, &Message::setDestination)
            .def_property("dst_ent", &Message::getDestinationEntity, &Message::setDestinationEntity)
            .def("serialize", &fserialize)
            .def("serialize_fields", &fserializeFields)
            .def("__getstate__", [](const Message &msg) {
                return py::make_tuple(fserialize(&msg));
            })
            .def("__str__", &messageToString);
}
