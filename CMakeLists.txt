cmake_minimum_required(VERSION 3.0)
SET(PROJ_NAME imc)

project(${PROJ_NAME})
add_subdirectory(pybind11)

# TODO: Improve build steps to find dune/imc automatically
SET(DUNE_BUILD $ENV{DUNE_BUILD})
SET(DUNE_ROOT $ENV{DUNE_ROOT})

#find_library(DUNE_CORE NAMES libdune-core.a HINTS ${DUNE_BUILD})
SET(DUNE_CORE ${DUNE_BUILD}/libdune-core.a)

INCLUDE_DIRECTORIES(
    ${DUNE_ROOT}/src/
    ${DUNE_BUILD}/DUNEGeneratedFiles/src/
)

# Find all source files starting with pb
FILE(GLOB_RECURSE CPP_SRC src pb*.cpp)

add_library(${PROJ_NAME} MODULE src/pyimc.cpp ${CPP_SRC})
target_link_libraries(${PROJ_NAME} PRIVATE pybind11::module ${DUNE_CORE})
set_target_properties(${PROJ_NAME} PROPERTIES PREFIX "${PYTHON_MODULE_PREFIX}"
                                         SUFFIX "${PYTHON_MODULE_EXTENSION}")
                                         
# Set build parameters
select_cxx_standard()
if(NOT MSVC)
    # Make sure C++11/14 are enabled
    target_compile_options(${PROJ_NAME} PUBLIC ${PYBIND11_CPP_STANDARD})
endif()

_pybind11_add_lto_flags(${PROJ_NAME} "")

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
