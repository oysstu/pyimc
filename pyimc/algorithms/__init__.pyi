import pyimc
from typing import Tuple

class CRC8:
    def __init__(self, polynomial, value = 0):
        """
        Generic computation of 8-bit CRCs.
        :param polynomial: CRC poly
        :param value: Initial CRC8 value
        """
        ...

    @property
    def value(self) -> int:
        """
        Retrive the current CRC8 value
        :return: The stored CRC8 value
        """
        ...

    @value.setter
    def value(self, val: int) -> None:
        """
        Set the current CRC8 value
        :param val: The value to set the CRC8 to
        :return: None
        """
        ...

    def put_byte(self, value: int) -> int:
        """
        Compute the CRC8 of one byte (based on current state)
        :param value: The byte
        :return: The current CRC8 value
        """
        ...

    def put_array(self, value: bytes) -> int:
        """
        Compute the CRC8 of one byte (based on current state)
        :param value: The bytes
        :return: The CRC8 value after processing the bytes
        """
        ...

