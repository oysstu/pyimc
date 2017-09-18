import pyimc
from typing import Generic, TypeVar, Iterable, Union, Tuple

def toWGS84(estate: pyimc.EstimatedState) -> Tuple[float, float, float]:
    """
    Convert the position in an estimated state message to WGS84 coordinates (lat, lon, height above ellipsoid).
    :param estate: Estimated state IMC message
    :return: Tuple of (lat, lon, hae)
    """
    ...

class WGS84:
    @staticmethod
    def distance(lat1: float, lon1: float, hae1:float, lat2: float, lon2: float, hae2: float) -> float: ...

    @staticmethod
    def displace(lat: float, lon: float, n: float, e: float) -> Tuple[float, float]:
        """
        Displaces the given WGS84 coordinates with the north+east offsets.
        :param lat: The starting latitude
        :param lon: The starting longitude
        :param n: The north offset
        :param e: The east offset
        :return: A tuple containing the offset latitude and longitude
        """

class UTM:
    @staticmethod
    def toWGS84(north: float, east: float, zone: int, in_north_hem: bool) -> Tuple[float, float]:
        """
        Converts UTM to WGS84
        :param north: North coordinate
        :param east: East coordinate
        :param zone: The UTM zone
        :param in_north_hem: True if in north hemisphere
        :return: Tuple of (lat, lon) in rad
        """
        ...

    @staticmethod
    def fromWGS84(lat: float, lon: float) -> Tuple[float, float, int, bool]:
        """
        Converts WGS84 to UTM
        :param lat: The latitude in radians
        :param lon: The longitude in radians
        :return: Tuple of (north, east, zone, in_north_hemisphere)
        """
        ...
