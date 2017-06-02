#include <pybind11/pybind11.h>
#include <pybind11/operators.h>

#include <DUNE/IMC/MessageList.hpp>

namespace py = pybind11;
using namespace DUNE::IMC;

// TODO: MessageList is currently untested

template<typename T>
void pbMessageList(py::module &m) {
    py::class_<MessageList<T>>(m, (std::string("MessageList") + typeid(T).name()).c_str())
    .def(py::init<>())
    .def(py::init<const MessageList<T>&>())
    .def("setParent", &MessageList<T>::setParent)
    .def("clear", &MessageList<T>::clear)
    .def("size", &MessageList<T>::size)
    .def("begin", &MessageList<T>::begin)
    .def("end", &MessageList<T>::end)
    //.def("push_back", py::overload_cast<const T&>(&MessageList<T>::push_back))
    //.def("push_back", py::overload_cast<const T*>(&MessageList<T>::push_back))
    .def("getSerializationSize", &MessageList<T>::getSerializationSize)
    .def("serialize", &MessageList<T>::serialize)
    .def("deserialize", &MessageList<T>::deserialize)
    .def("reverseDeserialize", &MessageList<T>::reverseDeserialize)
    //.def("toJSON", &MessageList<T>::toJSON)
    .def("setTimeStamp", &MessageList<T>::setTimeStamp)
    .def("setSource", &MessageList<T>::setSource)
    .def("setSourceEntity", &MessageList<T>::setSourceEntity)
    .def("setDestination", &MessageList<T>::setDestination)
    .def("setDestinationEntity", &MessageList<T>::setDestinationEntity)
    //.def(py::self = py::self)
    .def(py::self != py::self)
    .def(py::self == py::self);
}