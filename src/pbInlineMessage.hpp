#include <pybind11/pybind11.h>
#include <pybind11/operators.h>

#include <DUNE/IMC/InlineMessage.hpp>

namespace py = pybind11;
using namespace DUNE::IMC;


template<typename T>
T* pbInlineMessageGetter(InlineMessage<T> &imsg) {
    if(imsg.isNull())
        return nullptr;
    else
        return imsg.get();
}

template<typename T>
void pbInlineMessageSetter(InlineMessage<T> &imsg, py::object &msg) {
    if(msg.is_none())
        imsg.clear();
    else
        imsg.set(msg.cast<T>());
}