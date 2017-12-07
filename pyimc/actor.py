import socket, logging, time
from operator import itemgetter
from typing import Dict, Tuple, Union

import pyimc
from pyimc.decorators import *
from pyimc.udp import IMCSenderUDP, multicast_ip
from pyimc.network_utils import get_interfaces
from pyimc.node import IMCNode
from pyimc.exception import AmbiguousKeyError

logger = logging.getLogger('pyimc.actor')

class IMCBase:
    def __init__(self):
        self._loop = None  # type: asyncio.BaseEventLoop
        self._task_mc = None  # type: asyncio.Task
        self._task_imc = None  # type: asyncio.Task
        self._subs = {}  # type: Dict[Exception, List[types.MethodType]]
        self._port_imc = None  # type: int
        self._port_mc = None  # type: int

    def _start_subscriptions(self):
        # Add datagram endpoint for multicast announce
        multicast_listener = self._loop.create_datagram_endpoint(lambda: IMCProtocolUDP(self, is_multicast=True),
                                                                 family=socket.AF_INET)

        # Add datagram endpoint for UDP IMC messages
        imc_listener = self._loop.create_datagram_endpoint(lambda: IMCProtocolUDP(self, is_multicast=False),
                                                           family=socket.AF_INET)

        if sys.version_info < (3, 4, 4):
            self._task_mc = self._loop.create_task(multicast_listener)
            self._task_imc = self._loop.create_task(imc_listener)
        else:
            self._task_mc = asyncio.ensure_future(multicast_listener)
            self._task_imc = asyncio.ensure_future(imc_listener)

    def _setup_event_loop(self):
        # Add event loop to instance
        if not self._loop:
            self._loop = asyncio.get_event_loop()

        decorated = [(name, method) for name, method in inspect.getmembers(self) if hasattr(method, '_decorators')]
        for name, method in decorated:
            for decorator in method._decorators:
                decorator.add_event(self._loop, self, method)

                if type(decorator) is Subscribe:
                    # Collect subscribed message types for each function
                    for msg_type in decorator.subs:
                        try:
                            self._subs[msg_type].append(method)
                        except (KeyError, AttributeError):
                            self._subs[msg_type] = [method]

        # Subscriptions has been collected from all decorators
        # Add asyncio datagram endpoints to event loop
        self._start_subscriptions()

        #self._loop.set_exception_handler() TODO

    def stop(self):
        """
        Cancels all running tasks and stops the event loop.
        :return:
        """
        logger.info('Stop called by user. Cancelling all running tasks.')
        for task in asyncio.Task.all_tasks():
            task.cancel()

        loop = self._loop
        @asyncio.coroutine
        def exit():
            logger.info('Tasks cancelled. Stopping event loop.')
            loop.stop()

        asyncio.ensure_future(exit())

    def run(self):
        """
        Starts the event loop.
        """
        # Run setup if it hasn't been done yet
        if not self._loop:
            self._setup_event_loop()

        # Start event loop
        try:
            self._loop.run_forever()
        except KeyboardInterrupt:
            pending = asyncio.Task.all_tasks()
            for task in pending:
                task.cancel()
                # Now we should await task to execute it's cancellation.
                # Cancelled task raises asyncio.CancelledError that we can suppress when canceling
                with suppress(asyncio.CancelledError):
                    self._loop.run_until_complete(task)
        finally:
            self._loop.close()


class ActorBase(IMCBase):
    """
    Base actor class. Implements rudimentary bookkeeping of other IMC nodes and exchange of necessary messages.
    """
    def __init__(self):
        super().__init__()
        self.t_start = time.time()

        # Using a map from (imcadr, sys_name) to the nodes
        self.nodes = {}  # type: Dict[Tuple[int, str], IMCNode]

        # Set initial announce details
        self.announce = pyimc.Announce()
        self.announce.src = 0x3334  # imcjava uses 0x3333
        self.announce.sys_name = 'ccu-pyimc-{}'.format(socket.gethostname().lower())
        self.announce.sys_type = pyimc.SystemType.CCU
        self.announce.owner = 0xFFFF
        self.announce.src_ent = 1

        # Set initial entities
        self.entities = {'Daemon': 0, 'Service Announcer': 1}
        self.services = None  # Generated on first announce
        self.heartbeat = []  # type: List[Union[str, int, Tuple[int, str]]]

    def resolve_node_id(self, node_id: Union[int, str, Tuple[int, str], pyimc.Message]) -> IMCNode:
        """
        This function searches the map of connected nodes and returns a match (if unique)

        This function can throw the following exceptions
        KeyError: Node not found (not connected)
        AmbiguousKeyError: Multiple nodes matches the id (e.g multiple nodes announcing the same name)
        ValueError: Id parameter has an unexpected type
        :param node_id: Can be one of the following: imcid(int), imcname(str), node(tuple(int, str)), pyimc.message
        :return: An instance of the IMCNode class
        """

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
        msg.set_timestamp_now()

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
                logger.warning('Multiple nodes are announcing the same IMC address or name: {} and {}'.format(key, key_imcadr))

            # New node
            self.nodes[key] = IMCNode(msg)

        if not self.nodes[key].entities:
            q_ent = pyimc.EntityList()
            q_ent.op = pyimc.EntityList.OperationEnum.QUERY
            self.send(key, q_ent)

    @Subscribe(pyimc.EntityList)
    def recv_entity_list(self, msg):
        OpEnum = pyimc.EntityList.OperationEnum  # type: class
        try:
            node = self.resolve_node_id(msg)
            if msg.op == OpEnum.REPORT:
                node.update_entity_list(msg)
            elif msg.op == OpEnum.QUERY:
                # Format entities into string and send back to node that requested it
                ent_lst_sorted = sorted(self.entities.items(), key=itemgetter(1))  # Sort by value (entity id)
                ent_lst = pyimc.EntityList()
                ent_lst.op = OpEnum.REPORT
                ent_lst.list = ';'.join('{}={}'.format(k, v) for k, v in ent_lst_sorted)
                self.send(node, ent_lst)
        except (AmbiguousKeyError, KeyError):
            errstr = 'receiving' if msg.op == OpEnum.REPORT else 'sending'
            logger.debug('Unable to resolve node when ' + errstr + ' EntityList')
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
        if self._port_imc:  # Port must be ready to build IMC service string
            if not self.services:
                self.services = ['imc+udp://{}:{}/'.format(adr[1], self._port_imc) for adr in get_interfaces()]
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
                logger.info('Connection to node "{}" timed out'.format(node))
                rm_nodes.append(node)

        for node in rm_nodes:
            try:
                key = (node.announce.src, node.announce.sys_name)
                del self.nodes[key]
            except (KeyError, AttributeError) as e:
                logger.exception('Encountered exception when removing node: {}'.format(e.msg))

    @Periodic(10)
    def print_debug(self):
        # Prints connected nodes every 10 seconds (debugging)
        logger.debug('Connected nodes: {}'.format(list(self.nodes.keys())))

    @Subscribe(pyimc.Message)
    def unknown_message(self, msg):
        if type(msg) is pyimc.Message:
            try:
                node = self.resolve_node_id(msg)
            except (KeyError, AmbiguousKeyError):
                node = 'Unknown'

            logger.warning('Unknown message received: {} ({}) from {}'.format(msg.name, msg.id, node))


if __name__ == '__main__':
    pass

