#include <string>

#include <pybind11/pybind11.h>
#include <pybind11/operators.h>

#include <DUNE/IMC/Message.hpp>
#include <DUNE/IMC/MessageList.hpp>

namespace py = pybind11;
using namespace DUNE::IMC;

// Get typename for template parameter
#if defined(__GNUG__) || defined(__clang__)
#include <cstdlib>
#include <cxxabi.h>
template<typename T>
std::string type_name() {
    int status;
    std::string tname = typeid(T).name();
    char *demangled_name = abi::__cxa_demangle(tname.c_str(), NULL, NULL, &status);
    if(status == 0) {
        tname = demangled_name;
        std::free(demangled_name);
    }
    // Erase namespace
    tname.erase(0, strlen("DUNE::IMC::"));
    return tname;
}
#else
template<typename T>
std::string type_name() {
    return std::string(typeid(T).name());
}
#endif


/*
Note on object lifetimes:

keep_alive<Nurse, Patient> indicates that the argument with index Patient should be kept alive 
at least until the argument with index Nurse is freed by the garbage collector. Argument indices 
start at one, while zero refers to the return value. For methods, index 1 refers to the implicit 
this pointer, while regular arguments begin at index 2.

py::keep_alive<1, 2>() - Object life of the first argument (2) is tied to the life of the message list (1)
py::keep_alive<0, 1>() - Object life of the message list (1) is tied to the life of the return value (0)

These flags does not cause python to take ownership of the message list
*/

template<typename T>
void pbMessageList(py::module &m) {
    py::class_<MessageList<T>>(m, (std::string("MessageList") + type_name<T>()).c_str())
    .def(py::init<>())
    .def(py::init<const MessageList<T>&>())
    .def("set_parent", &MessageList<T>::setParent)
    .def("clear", &MessageList<T>::clear)
    .def_property_readonly("size", &MessageList<T>::size)
    // Object lifetime is tied to the message list
#ifdef PYBIND11_CPP14
    .def("append", py::overload_cast<const T&>(&MessageList<T>::push_back), py::keep_alive<1, 2>())
#else
    .def("append", static_cast<void (MessageList<T>::*)(const T&)>(&MessageList<T>::push_back), py::keep_alive<1, 2>())
#endif
    .def("set_timestamp", &MessageList<T>::setTimeStamp)
    .def("extend", [](MessageList<T> &ml, const py::object &iterable) {
        // Throws if not iterable
        for(auto msg : iterable){
            ml.push_back(msg.cast<T*>());
        }
    }, py::keep_alive<1, 2>())

    // Python operators
    .def(py::self != py::self)
    .def(py::self == py::self)
    .def("__len__", &MessageList<T>::size)
    .def("__iter__", [](const MessageList<T> &ml) { return py::make_iterator(ml.begin(), ml.end()); },
                        py::keep_alive<0, 1>() /* Keep message list alive while iterator exists */)
    .def("__getitem__", [](const MessageList<T> &ml, size_t i) {
        if (i >= ml.size())
            throw py::index_error();
        auto it = ml.begin();
        std::advance(it, i);  // Constant-time for random access iterators
        return *it;
    }, py::return_value_policy::reference_internal)
    /// Slicing protocol 
    .def("__getitem__", [](const MessageList<T> &ml, py::slice slice) {
        size_t start, stop, step, slicelength;
        if (!slice.compute(ml.size(), &start, &stop, &step, &slicelength))
            throw py::error_already_set();
        if(step != 1)
            throw py::index_error("Slice indexing with step is not supported.");
        auto begin = ml.begin(); std::advance(begin, start);
        auto end = ml.begin(); std::advance(end, stop);
        return py::make_iterator(begin, end);
    }, py::keep_alive<0, 1>())
    .def("__contains__", [](const MessageList<T> &ml, const T &item){
        for (auto msg : ml){
            if(*msg == item)
                return true;
        }
        return false;
    });
}