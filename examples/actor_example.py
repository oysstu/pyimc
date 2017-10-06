"""
The following example describes how to use the ActorBase class.

When derived from this class announces itself as a CCU, similar to Neptus, and can send and receive IMC messages.
The event loop is based on asyncio. Interactions with asyncio is done through the decorators.
@Subscribe adds a subscriber to a certain IMC message
@Periodic adds a function to be run periodically by the event loop.
"""

import logging
import sys
from typing import Tuple

import pyimc
from pyimc.actor import ActorBase
from pyimc.decorators import Periodic, Subscribe


class ExampleActor(ActorBase):
    def __init__(self, target_name):
        """
        Initialize the actor
        :param target_name: The name of the target system
        """
        super().__init__()

        self.last_pos = None  # type: Tuple[float, float, float]

        # This list contains the target systems to maintain communications with
        self.heartbeat.append(target_name)


    @Subscribe(pyimc.EstimatedState)
    def recv_estate(self, msg: pyimc.EstimatedState):
        """
        This function is called whenever EstimatedState messages are received
        :param msg: Functions decorated with @Subscribe must always have one parameter for the message
        :return: None
        """

        # EstimatedState consists of a reference position (LLH) and a local offset.
        # Convert to a single lat/lon coordinate
        (lat, lon, hae) = pyimc.coordinates.toWGS84(msg)

        if self.last_pos:
            # Compute the distance between the current and previous EstimatedState
            dist = pyimc.coordinates.WGS84.distance(*self.last_pos, lat, lon, hae)
            logging.info('The target system moved {} meters since last EstimatedState message.'.format(dist))

        self.last_pos = (lat, lon, hae)

    @Periodic(10.0)
    def run_periodic(self):
        """
        This function is called every ten seconds. Remember that asyncio (and most of python) is single-threaded.
        Doing extensive computations here will halt the event loop. If the UDP buffer fills up this in turn means that
        messages will be lost.
        :return:
        """
        logging.info('Periodic function was executed.')

if __name__ == '__main__':
    # Setup logging level and console output
    logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)

    # Create an actor, targeting the lauv-simulator-1 system
    actor = ExampleActor('lauv-simulator-1')

    # This command starts the asyncio event loop
    actor.run()