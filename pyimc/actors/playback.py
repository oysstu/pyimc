import time
import asyncio
import logging
import sys

import pyimc
from pyimc.actors.base import ActorBase
from pyimc.lsf import LSFReader
from pyimc.decorators import RunOnce, Subscribe

logger = logging.getLogger('pyimc.actors.playback')


class PlaybackActor(ActorBase):
    """
    Playback actor class. Plays back an LSF file in addition to networked messages.
    Messages are dispatched according to the offset from the first message (timestamp) from that system
    """

    def __init__(self, lsf_path, speed: float=1.0, offset_time: bool=True, start_time: float=None):
        """
        :param speed: The speed factor to play back the data with (1.0: realtime, negative: no delay)
        :param offset_time: Optionally offset messages to current system time
        :param start_time: Optional starting time for the playback (compared with imc timestamp)
        """
        super().__init__()

        # Args
        self.lsf_path = lsf_path
        self.speed = speed
        self.offset_time = offset_time
        self.start_time = start_time

        # State
        self.t0 = None  # Time of actor start
        self.t0_sys = {}  # Timestamp of first message from each system

    @RunOnce()
    @asyncio.coroutine
    def playback(self):
        self.t0 = time.time()

        # Retrieve message subscription types (to skip unwanted messages)
        # LoggingControl is appended, as that is the first message (and therefore contains timestamp of local system)
        all_messages = not all([pyimc.Message in msgtype.__bases__ for msgtype in self._subs.keys()])
        msg_types = None if all_messages else list(self._subs.keys()) + [pyimc.LoggingControl]

        for msg in LSFReader.read(self.lsf_path, types=msg_types):
            try:
                t0_sys = self.t0_sys[msg.src]
            except KeyError:
                self.t0_sys[msg.src] = msg.timestamp

            # Time since start of log
            t_msg = self.t0 + msg.timestamp - self.t0_sys[msg.src]

            if self.offset_time:
                msg.timestamp = t_msg

            # Optional: Skip messages until given time, except core messages
            if self.start_time and msg.timestamp < self.start_time:
                if type(msg) is pyimc.Announce:
                    self.recv_announce(msg)
                elif type(msg) is pyimc.EntityList:
                    self.recv_entity_list(msg)
                elif type(msg) is pyimc.EntityInfo:
                    self.recv_entity_info(msg)

                continue

            # Sleep until message should be posted
            # Also important to give CPU time to other tasks
            t_sleep = (t_msg - time.time())/self.speed if self.speed > 0 else 0
            yield from asyncio.sleep(max(0, t_sleep))

            # Post message to actor
            self.post_message(msg)


if __name__ == '__main__':
    pass


