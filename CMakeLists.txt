cmake_minimum_required(VERSION 3.8)

SET(PROJ_NAME _pyimc)
project(${PROJ_NAME})

add_subdirectory(pybind11)

# Set CXX standard to 17
target_compile_features(${PROJ_NAME} PRIVATE cxx_std_17)

#######################################################
##                     DUNE                          ##
#######################################################

# Embed DUNE into build, but only build dune-core
add_subdirectory(dune EXCLUDE_FROM_ALL)
include_directories(dune/src/)
include_directories(${CMAKE_BINARY_DIR}/DUNEGeneratedFiles/src)  # Contains generated Config.hpp/Version.cpp files
if(MSVC)
    include_directories(dune/vendor/libraries/pthreads-win32)
endif()

set_property(TARGET dune-core PROPERTY POSITION_INDEPENDENT_CODE ON)  # Enable -fPIC on dune-core build

#######################################################
##                      IMC                          ##
#######################################################

# Generate IMC definitions from spec
add_dependencies(dune-core imc)


#######################################################
##                   Source/Libs                     ##
#######################################################

# Find all source files starting with pb
FILE(GLOB_RECURSE CPP_SRC src pb*.cpp)

# Use THIN_LTO if available (Clang/LLVM)
pybind11_add_module(${PROJ_NAME} MODULE THIN_LTO src/pyimc.cpp ${CPP_SRC})

# Link with dune-core
if(MSVC)
    target_link_libraries(${PROJ_NAME} PRIVATE pybind11::module dune-core ws2_32)
else()
    target_link_libraries(${PROJ_NAME} PRIVATE pybind11::module dune-core)
endif()
