import socket, logging, time
from operator import itemgetter
from typing import Dict, Tuple, Union

import pyimc
from pyimc.decorators import *
from pyimc.udp import IMCSenderUDP, multicast_ip
from pyimc.network_utils import get_interfaces
from pyimc.node import IMCNode
from pyimc.exception import AmbiguousKeyError


class ActorBase(IMCBase):
    """
    Base actor class. Implements rudimentary bookkeeping of other IMC nodes and exchange of necessary messages.
    """
    def __init__(self):
        super().__init__()

        # Using a map from (imcadr, sys_name) to the nodes
        self.nodes = {}  # type: Dict[Tuple[int, str], IMCNode]

        # Set initial announce details
        self.announce = pyimc.Announce()
        self.announce.src = 0x3334  # imcjava uses 0x3333
        self.announce.sys_name = 'ccu-pyimc-{}'.format(socket.gethostname().lower())
        self.announce.sys_type = pyimc.SYSTEMTYPE_CCU

        # Set initial entities
        self.entities = {'Daemon': 0}
        self.services = None  # Generated on first announce
        self.heartbeat = []  # type: List[Union[str, int, Tuple[int, str]]]

    def resolve_node_id(self, node_id):
        # Resolve IMCNode
        id_type = type(node_id)
        if id_type is str or id_type is int:
            # Search for keys with the name or id, raise exception if not found or ambiguous
            idx = 0 if id_type is int else 1
            possible_nodes = [x for x in self.nodes.keys() if x[idx] == node_id]
            if not possible_nodes:
                raise KeyError('Specified IMC node does not exist.')
            elif len(possible_nodes) > 1:
                raise AmbiguousKeyError('Specified IMC node has multiple possible choices', choices=possible_nodes)
            else:
                return self.nodes[possible_nodes[0]]
        elif id_type is tuple:
            # Determine the correct order of arguments
            if type(node_id[0]) is int and type(node_id[1]) is str:
                return self.nodes[node_id]
            else:
                raise TypeError('Node id tuple must be (int, str).')
        elif id_type is IMCNode:
            # Resolve by an preexisting IMCNode object
            return self.resolve_node_id((node_id.announce.src, node_id.announce.sys_name))
        elif isinstance(node_id, pyimc.Message):
            # Resolve by imc address in received message
            return self.resolve_node_id(node_id.src)
        else:
            raise TypeError('Expected node_id as int, str, tuple(int,str) or Message, received {}'.format(id_type))

    def send(self, node_id, msg):
        """
        Send an imc message to the specified imc node. The node can be specified through it's imc address, system name
        or a tuple of both. If either of the first two does not uniquely specify a node an AmbiguousNode exception is 
        raised.
        :param node_id: The destination node (imc adr (int), system name (str) or a tuple(imc_adr, sys_name))
        :param msg: The imc message to send
        :return: 
        """

        # Fill out source params
        msg.src = self.announce.src
        msg.setTimeStampCurrent()

        node = self.resolve_node_id(node_id)
        node.send(msg)

    @Subscribe(pyimc.Announce)
    def recv_announce(self, msg):
        # TODO: Check if IP of a node changes

        # Return if announce originates from this ccu
        if msg.src == self.announce.src and msg.sys_name == self.announce.sys_name:
            # TODO: Check if another node is broadcasting our ID
            return

        # Update announce
        key = (msg.src, msg.sys_name)
        try:
            self.nodes[key].update_announce(msg)
        except KeyError:
            # If the key is new, check for duplicate names/imc addresses
            key_imcadr = [x for x in self.nodes.keys() if x[0] == key[0] or x[1] == key[1]]
            if key_imcadr:
                logging.warning('Multiple nodes are announcing the same IMC address or name: {} and {}'.format(key, key_imcadr))

            # New node
            self.nodes[key] = IMCNode(msg)

        if not self.nodes[key].entities:
            q_ent = pyimc.EntityList()
            q_ent.op = pyimc.EntityList.OP_QUERY
            self.send(key, q_ent)

    @Subscribe(pyimc.EntityList)
    def recv_entity_list(self, msg):
        try:
            node = self.resolve_node_id(msg)
            if msg.op == pyimc.EntityList.OP_REPORT:
                node.update_entity_list(msg)
            elif msg.op == pyimc.EntityList.OP_QUERY:
                # Format entities into string and send back to node that requested it
                ent_lst_sorted = sorted(self.entities.items(), key=itemgetter(1))  # Sort by value (entity id)
                ent_lst = pyimc.EntityList()
                ent_lst.op = pyimc.EntityList.OP_REPORT
                ent_lst.list = ';'.join('{}={}'.format(k, v) for k, v in ent_lst_sorted)
                self.send(node, ent_lst)
        except (AmbiguousKeyError, KeyError):
            errstr = 'receiving' if msg.op == pyimc.EntityList.OP_REPORT else 'sending'
            logging.debug('Unable to resolve node when ' + errstr + ' EntityList')
            pass

    @Subscribe(pyimc.Heartbeat)
    def recv_heartbeat(self, msg):
        node = self.resolve_node_id(msg)
        node.update_heartbeat(msg)

    @Periodic(10)
    def send_announce(self):
        """
        Send an announce. Will use properties stored in this class (e.g self.lat, self.lon to set parameters)
        :return: 
        """
        # Build imc+udp string
        # TODO: Add TCP protocol for IMC
        if self._port_imc:
            if not self.services:
                self.services = ['imc+udp://{}:{}/'.format(adr[1], self._port_imc) for adr in get_interfaces()]
                self.announce.services = ';'.join(self.services)
            with IMCSenderUDP(multicast_ip) as s:
                self.announce.setTimeStampCurrent()
                for i in range(30100, 30105):
                    s.send(self.announce, i)
        else:
            logging.debug('IMC socket not ready')

    @Periodic(5)
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
                logging.exception(e.msg + '({})'.format(e.choices))
            except KeyError as e:
                pass

    @Periodic(90)
    def prune_nodes(self):
        """
        Clear nodes that have not announced themselves or sent heartbeat in the past 90 seconds
        """
        t = time.time()
        rm_nodes = []  # Avoid changes to dict during iteration
        for node in self.nodes.values():
            has_heartbeat = type(node.heartbeat) is float and t - node.heartbeat < 60
            has_announce = type(node.announce) is pyimc.Announce and t - node.announce.timestamp < 60
            if not (has_heartbeat or has_announce):
                logging.info('Connection to node "{}" timed out'.format(node))
                rm_nodes.append(node)

        for node in rm_nodes:
            try:
                key = (node.announce.src, node.announce.sys_name)
                del self.nodes[key]
            except (KeyError, AttributeError) as e:
                logging.exception('Encountered exception when removing node: {}'.format(e.msg))

    @Periodic(10)
    def print_debug(self):
        # Prints connected nodes every 10 seconds (debugging)
        # TODO: add time since last announce/heartbeat to log
        logging.info('Connected nodes: {}'.format(list(self.nodes.keys())))

    @Subscribe(pyimc.Message)
    def unknown_message(self, msg):
        if type(msg) is pyimc.Message:
            try:
                node = self.resolve_node_id(msg)
            except (KeyError, AmbiguousKeyError):
                node = 'Unknown'

            logging.info('Unknown message received: {} ({}) from {}'.format(msg.name, msg.id, node))


if __name__ == '__main__':
    # Setup logging level and console output
    logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)

    class ActorChild(ActorBase):
        def __init__(self):
            super().__init__()

    # Run actor
    x = ActorBase()
    x.heartbeat.append('lauv-simulator-1')
    x.run()

