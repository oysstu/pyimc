"""
This example illustrates how to send a request for the plan database from a system.
"""

import logging
import sys
from typing import Tuple

import pyimc
from pyimc.actor import ActorBase
from pyimc.decorators import Periodic, Subscribe


class PlanActor(ActorBase):
    def __init__(self, target_name):
        """
        Initialize the actor
        :param target_name: The name of the target system
        """
        super().__init__()

        # Initialize local variables
        self.target = target_name
        self.db_reqid = 0  # Optional number that is incremented for requests

        # This list contains the target systems to maintain communications with
        self.heartbeat.append(target_name)

    @Periodic(10.0)
    def req_plandb(self):
        """
        Request the plan database every ten seconds if the system is connected.
        :return: None
        """
        # Check if target system is currently connected
        try:
            # This function resolves the map of connected nodes
            node = self.resolve_node_id(self.target)

            # Request the PlanDB state
            logging.debug("Requesting PlanDB state from target.")
            db_req = pyimc.PlanDB()

            # Enumerations are exposed as a subclass of the message
            db_req.type = pyimc.PlanDB.TypeEnum.REQUEST
            db_req.op = pyimc.PlanDB.OperationEnum.GET_STATE  # Note: DSTATE does not seem to work as intended
            db_req.request_id = self.db_reqid
            self.db_reqid += 1

            # Send the IMC message to the node
            self.send(node, db_req)

        except KeyError as e:
            # Target system is not connected
            logging.debug('Target system is not connected.')


    @Subscribe(pyimc.PlanDB)
    def recv_plandb(self, msg: pyimc.PlanDB):
        try:
            # Check if message originates from the target system
            node = self.resolve_node_id(self.target)
            if msg.src == node.id:
                # Check for a successful PlanDB request of the correct type
                if msg.type == pyimc.PlanDB.TypeEnum.SUCCESS and msg.op == pyimc.PlanDB.OperationEnum.GET_STATE:
                    dbstate = msg.arg  # type: pyimc.PlanDBState

                    # The IMC MessageList type interface is designed to be as close to a python list as possible
                    # It has support for iteration, indexing, slicing, append, extend, len, in
                    # The caveat is that it cannot be assigned to from a list (use append, clear, extend instead)
                    plan_names = [p.plan_id for p in dbstate.plans_info]
                    logging.info('Target system has the following plans: {}'.format(plan_names))

        except KeyError as e:
            pass


if __name__ == '__main__':
    # Setup logging level and console output
    logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)

    # Create an actor, targeting the lauv-simulator-1 system
    actor = PlanActor('lauv-simulator-1')

    # This command starts the asyncio event loop
    actor.run()