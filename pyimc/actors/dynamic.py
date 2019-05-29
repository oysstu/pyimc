import socket
import time
from operator import itemgetter

import pyimc
from pyimc.actors import IMCBase, logger
from pyimc.common import multicast_ip
from pyimc.decorators import Subscribe, Periodic
from pyimc.exception import AmbiguousKeyError
from pyimc.network.udp import IMCSenderUDP
from pyimc.network.utils import get_interfaces


class DynamicActor(IMCBase):
    """
    Actor which announces itself and maintains communication (heartbeat) with a set of specified nodes.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.t_start = time.time()

        # Set initial announce details
        self.announce = pyimc.Announce()
        self.announce.src = self.imc_id  # imcjava uses 0x3333
        self.announce.sys_name = 'ccu-pyimc-{}'.format(socket.gethostname().lower())
        self.announce.sys_type = pyimc.SystemType.CCU
        self.announce.owner = 0xFFFF
        self.announce.src_ent = 1

        # Set initial entities (services generated on first announce)
        self.entities = {'Daemon': 0, 'Service Announcer': 1}

        # IMC nodes to send heartbeat signal to (maintaining comms)
        self.heartbeat = []  # type: List[Union[str, int, Tuple[int, str]]]

    @Subscribe(pyimc.EntityList)
    def reply_entity_list(self, msg):
        """
        Respond to entity list queries
        """
        OpEnum = pyimc.EntityList.OperationEnum
        if msg.op == OpEnum.QUERY:
            try:
                node = self.resolve_node_id(msg)

                # Format entities into string and send back to node that requested it
                ent_lst_sorted = sorted(self.entities.items(), key=itemgetter(1))  # Sort by value (entity id)
                ent_lst = pyimc.EntityList()
                ent_lst.op = OpEnum.REPORT
                ent_lst.list = ';'.join('{}={}'.format(k, v) for k, v in ent_lst_sorted)
                self.send(node, ent_lst)
            except (AmbiguousKeyError, KeyError):
                logger.debug('Unable to resolve node when sending EntityList')

    @Periodic(30)
    def query_entity_list(self):
        """
        Request entity list from nodes without one
        """
        for k, node in self.nodes.items():
            if not node.entities:
                q_ent = pyimc.EntityList()
                q_ent.op = pyimc.EntityList.OperationEnum.QUERY
                self.send(node, q_ent)

    @Periodic(10)
    def send_announce(self):
        """
        Send an announce. Will use properties stored in this class (e.g self.lat, self.lon to set parameters)
        :return:
        """
        # Build imc+udp string
        # TODO: Add TCP protocol for IMC
        if self._port_imc:  # Port must be ready to build IMC service string
            self.services = ['imc+udp://{}:{}/'.format(adr[1], self._port_imc) for adr in get_interfaces()]
            if not self.services:
                # No external interfaces available, announce localhost/loopback
                self.services = ['imc+udp://{}:{}/'.format(adr[1], self._port_imc) for adr in get_interfaces(False)]

            self.announce.services = ';'.join(self.services)
            with IMCSenderUDP(multicast_ip) as s:
                self.announce.set_timestamp_now()
                for i in range(30100, 30105):
                    s.send(self.announce, i)
        elif (time.time() - self.t_start) > 10:
            logger.debug('IMC socket not ready')  # Socket should be ready by now.

    @Periodic(1)
    def send_heartbeat(self):
        """
        Send a heartbeat signal to nodes specified in self.heartbeat
        """
        hb = pyimc.Heartbeat()
        for node_id in self.heartbeat:
            try:
                node = self.resolve_node_id(node_id)
                self.send(node, hb)
            except AmbiguousKeyError as e:
                logger.exception(str(e) + '({})'.format(e.choices))
            except KeyError:
                pass
