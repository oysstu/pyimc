import logging
import ipaddress as ip
from urllib.parse import urlparse

from pyimc.network.udp import IMCSenderUDP
from pyimc.network.utils import get_interfaces

logger = logging.getLogger('pyimc.node')


class IMCService:
    """
    IMC service consisting of an ip/port and service specifier
    """
    def __init__(self, service_string):
        p = urlparse(service_string)
        self.ip = p.hostname
        self.port = p.port
        self.scheme = p.scheme

        if p.path is not '/':
            self.param = tuple(filter(None, p.path.split('/')))
        else:
            self.param = None

    def __str__(self):
        param = '{}/{}'.format(*self.param) if self.param else ''
        port = ':{}'.format(self.port) if self.port else ''
        return '{}://{}{}/{}'.format(self.scheme, self.ip, port, param)


class IMCNode:
    """
    An IMC node consisting of it's address, services and entities.
    """
    def __init__(self, announce=None, service_filter=('imc+udp',)):
        """

        :param announce: Initialize the node with the contents of an Announce message
        :param service_filter: Only use the services specified in order of priority (TODO IMPLEMENT)
        """
        # Node data
        self.sys_name = None  # type: str
        self.src = None  # type: int
        self.last_announce = None  # type: float
        self.services_string = None  # type: str

        # Parsed services
        self.services = {}  # type: Dict[str, IMCService]
        # Parsed entities
        self.entities = {}  # type: Dict[str, int]
        # Time of last heartbeat
        self.heartbeat = None  # type: float

        # Node arguments
        self.service_filter = service_filter

        if announce:
            self.update_announce(announce)

    @property
    def name(self):
        return self.sys_name

    @property
    def id(self):
        return self.src

    def update_announce(self, msg):
        self.sys_name = msg.sys_name
        self.src = msg.src
        self.last_announce = msg.timestamp

        # Update the services
        if self.services_string != msg.services:
            self.update_services(msg.services)
            self.services_string = msg.services

    def update_heartbeat(self, msg):
        self.heartbeat = msg.timestamp

    def update_services(self, service_string: str):
        self.services = {}
        for svc in service_string.split(';'):
            s = IMCService(svc)
            try:
                self.services[s.scheme].append(s)
            except KeyError as e:
                self.services[s.scheme] = [s]

    def update_entity_list(self, msg):
        self.entities = {k: int(v) for k, v in (x.split('=') for x in msg.list.split(';'))}

    def update_entity_id(self, ent_id, ent_label):
        self.entities[ent_label] = ent_id

    def send(self, msg):
        """
        Sends the IMC message to the node, filling in the destination
        :param msg: The IMC message to send
        :return: 
        """

        imcudp_services = self.services['imc+udp']
        if not imcudp_services:
            logger.error('{} does not expose an imc+udp service'.format(self))
            return

        # Determine which service to send to based on ip/netmask
        # Note: this might not account for funky ip routing
        networks = [ip.ip_interface(x[1] + '/' + x[2]).network for x in get_interfaces()]
        for svc in imcudp_services:
            svc_ip = ip.ip_address(svc.ip)
            if any([svc_ip in network for network in networks]):
                with IMCSenderUDP(svc.ip) as s:
                    s.send(message=msg, port=svc.port)
                return

        # If this point is reached no local interfaces has the target system in its netmask
        # Could be running on same system with no available interfaces
        # Send on loopback
        ports = [svc.port for svc in imcudp_services]
        with IMCSenderUDP('127.0.0.1') as s:
            for port in ports:
                s.send(message=msg, port=port)

    def __str__(self):
        return 'IMCNode(0x{:X}, {})'.format(self.src, self.sys_name)

    def __repr__(self):
        return 'IMCNode(0x{:X}, {})'.format(self.src, self.sys_name)


if __name__ == '__main__':
    pass