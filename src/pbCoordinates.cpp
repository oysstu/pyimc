#include <pybind11/pybind11.h>

#include <DUNE/Coordinates.hpp>
#include <DUNE/IMC/Definitions.hpp>

namespace py = pybind11;
using namespace pybind11::literals;

using namespace DUNE::Coordinates;
using namespace DUNE::IMC;


void pbCoordinates(py::module &m) {
  py::module c = m.def_submodule("coordinates", "coordinates");

  // WGS84 Class
  auto wgs84 = py::class_<WGS84>(c, "WGS84");
  wgs84.def_static("distance", &WGS84::distance<double, double>, "Calculate distance between two WGS-84 coordinates (ECEF)");
  wgs84.def_static("displace", [](double lat, double lon, double n, double e) {
    WGS84::displace(n, e, &lat, &lon);
    return std::make_tuple(lat, lon);
  }, "lat"_a, "lon"_a,"n"_a, "e"_a, "Displace a WGS-84 coordinate in the NED frame according to given offsets.");

  // UTM Class
  auto utm = py::class_<UTM>(c, "UTM");

  utm.def_static("toWGS84", [](double north, double east, int zone, bool in_north_hem) {
    double lat, lon;
    UTM::toWGS84(north, east, zone, in_north_hem, &lat, &lon);
    return std::make_tuple(lat, lon);
  }, "north"_a, "east"_a, "zone"_a, "in_north_hem"_a, "Calculate WGS84 coordinates for the given zone.");

  utm.def_static("fromWGS84", [](double lat, double lon) {
    double n, e; int zone; bool in_north_hem;
    UTM::fromWGS84(lat, lon, &n, &e, &zone, &in_north_hem);
    return std::make_tuple(n, e, zone, in_north_hem);
  }, "lat"_a, "lon"_a, "Calculate UTM coordinates. Zone selected automatically. Returns (n, e, zone, in_north_hem)");


  // Top-level functions
  c.def("toWGS84", [](const EstimatedState& estate) {
    double lat, lon; float hae;
    toWGS84(estate, lat, lon, hae);
    return std::make_tuple(lat, lon, hae);
  }, "estate"_a);
}