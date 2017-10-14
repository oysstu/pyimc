cmake_minimum_required(VERSION 3.0)

SET(PROJ_NAME _pyimc)
project(${PROJ_NAME})

add_subdirectory(pybind11)

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

add_library(${PROJ_NAME} MODULE src/pyimc.cpp ${CPP_SRC})

if(MSVC)
    target_link_libraries(${PROJ_NAME} PRIVATE pybind11::module dune-core ws2_32)
else()
    target_link_libraries(${PROJ_NAME} PRIVATE pybind11::module dune-core)
endif()

set_target_properties(${PROJ_NAME} PROPERTIES PREFIX "${PYTHON_MODULE_PREFIX}"
                                         SUFFIX "${PYTHON_MODULE_EXTENSION}")


#######################################################
##                     Pybind11                      ##
#######################################################

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
