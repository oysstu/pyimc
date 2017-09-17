cmake_minimum_required(VERSION 3.0)

SET(PROJ_NAME _pyimc)
project(${PROJ_NAME})

# Pybind11
#if(MSVC)
#    set(PYBIND11_CPP_STANDARD /std:c++latest)
#else()
#    set(PYBIND11_CPP_STANDARD -std=c++14)
#endif()
add_subdirectory(pybind11)

# Embed DUNE into build, but only build dune-core
add_subdirectory(dune EXCLUDE_FROM_ALL)
include_directories(dune/src/)
include_directories(${CMAKE_BINARY_DIR}/DUNEGeneratedFiles/src)  # Contains generated Config.hpp/Version.cpp files
set_property(TARGET dune-core PROPERTY POSITION_INDEPENDENT_CODE ON)  # Enable -fPIC on dune-core build

# Generate IMC definitions from spec
add_dependencies(dune-core imc)

# Find all source files starting with pb
FILE(GLOB_RECURSE CPP_SRC src pb*.cpp)

add_library(${PROJ_NAME} MODULE src/pyimc.cpp ${CPP_SRC})
target_link_libraries(${PROJ_NAME} PRIVATE pybind11::module dune-core)
set_target_properties(${PROJ_NAME} PROPERTIES PREFIX "${PYTHON_MODULE_PREFIX}"
                                         SUFFIX "${PYTHON_MODULE_EXTENSION}")

_pybind11_add_lto_flags(${PROJ_NAME} THIN_LTO)

if (NOT MSVC AND NOT ${CMAKE_BUILD_TYPE} MATCHES Debug)
    # Set the default symbol visibility to hidden (very important to obtain small binaries)
    target_compile_options(${PROJ_NAME} PRIVATE "-fvisibility=hidden")

    # Strip unnecessary sections of the binary on Linux/Mac OS
    if(CMAKE_STRIP)
      if(APPLE)
        add_custom_command(TARGET ${PROJ_NAME} POST_BUILD
                           COMMAND ${CMAKE_STRIP} -x $<TARGET_FILE:${PROJ_NAME}>)
      else()
        add_custom_command(TARGET ${PROJ_NAME} POST_BUILD
                           COMMAND ${CMAKE_STRIP} $<TARGET_FILE:${PROJ_NAME}>)
      endif()
    endif()
  endif()

if(MSVC)
    # /MP enables multithreaded builds (relevant when there are many files), /bigobj is
    # needed for bigger binding projects due to the limit to 64k addressable sections
    target_compile_options(${PROJ_NAME} PRIVATE /MP /bigobj)
endif()