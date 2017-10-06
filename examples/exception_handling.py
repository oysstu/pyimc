"""
The following example describes how to handle uncaught exceptions from other decorated functions.
"""

import logging
import sys
from typing import Tuple

import pyimc
from pyimc.actor import ActorBase
from pyimc.decorators import Periodic, Subscribe


class ExceptionActor(ActorBase):
    def __init__(self, target_name):
        """
        Initialize the actor
        :param target_name: The name of the target system
        """
        super().__init__()
        self.heartbeat.append(target_name)
        self.i = 0

    @Subscribe(pyimc.EstimatedState)
    def recv_estate(self, msg: pyimc.EstimatedState):
        """
        Subscribes to EstimatedState messages, and raises an exception after 10 messages has been received.
        Exceptions escaping @Subscribe functions does not terminate the IMC listener.
        """
        #self.i += 1
        return

        logging.info('Received EstimatedState message from target')

        if self.i == 10:
            raise RuntimeError('Exception from subscribed function')


    @Periodic(1.0)
    def run_periodic(self):
        """
        Function that raises an exception after 5 EstimatedState messages has been received.
        Uncaught exceptions in periodic functions terminates the periodic event, but does not stop other events.
        It is possible to re-add the periodic function to the event loop programmatically, but not supported at this time.
        """
        self.i += 1
        if self.i >= 5:
            self.stop()
            #raise RuntimeError('Exception from periodic function')
        else:
            logging.debug('Periodic')

if __name__ == '__main__':
    # Setup logging level and console output
    logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)

    # Create an actor, targeting the lauv-simulator-1 system
    actor = ExceptionActor('lauv-fridtjof')

    # This command starts the asyncio event loop
    actor.run()
