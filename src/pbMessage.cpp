#include <DUNE/IMC/Message.hpp>
#include <pybind11/pybind11.h>
#include <pybind11/operators.h>
#include <DUNE/IMC/Packet.hpp>


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
    const char* getName(void) const override {
        PYBIND11_OVERLOAD_PURE(const char*, Message, getName); 
        }
    uint16_t getId(void) const override { 
        PYBIND11_OVERLOAD_PURE(uint16_t, Message, getId); 
        }
    uint16_t getSubId(void) const override { 
        PYBIND11_OVERLOAD(uint16_t, Message, getSubId); 
        }
    void setSubId(uint16_t subId) override { 
        PYBIND11_OVERLOAD(void, Message, setSubId, subId); 
        }
    fp64_t getValueFP(void) const override { 
        PYBIND11_OVERLOAD(fp64_t, Message, getValueFP); 
        }
    void setValueFP(fp64_t val) override { 
        PYBIND11_OVERLOAD(void, Message, setValueFP, val); 
        }
    unsigned getFixedSerializationSize(void) const override { 
        PYBIND11_OVERLOAD(unsigned, Message, getPayloadSerializationSize); 
        }
    unsigned getVariableSerializationSize(void) const override { 
        PYBIND11_OVERLOAD(unsigned, Message, getVariableSerializationSize); 
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
    void fieldsToJSON(std::ostream& os, unsigned indent_level) const override {
        PYBIND11_OVERLOAD(void, Message, fieldsToJSON,os, indent_level);
        }
};

py::bytes fserialize(const Message* msg){ 
    unsigned sz = msg->getSerializationSize();
    uint8_t* buf = (uint8_t*)std::malloc(sz);
    uint16_t n_written = Packet::serialize(msg, buf, sz);

    return py::bytes(reinterpret_cast<const char*>(buf), static_cast<size_t>(n_written));
};

void pbMessage(py::module &m) {
    py::class_<Message, PyMessage>(m, "Message")
            .def(py::init<>())
            .def("clone", &Message::clone)
            .def("clear", &Message::clear)
            .def("validate", &Message::validate)
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
            .def_property("sub_id", &Message::getSubId, &Message::setSubId)
            .def("serialize", &fserialize);
}
