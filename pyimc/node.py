import logging
import ipaddress as ip
from urllib.parse import urlparse
import time
from typing import Dict

from pyimc.network.udp import IMCSenderUDP
from pyimc.network.utils import get_interfaces

logger = logging.getLogger('pyimc.node')


class IMCService:
    """
    IMC service consisting of an ip/port and service specifier
    """
    @staticmethod
    def from_url(service_url):
        p = urlparse(service_url)

        if p.path is not '/':
            param = tuple(filter(None, p.path.split('/')))
        else:
            param = None

        return IMCService(ip=p.hostname, port=p.port, scheme=p.scheme, param=param)

    def __init__(self, ip, port, scheme, param=None):
        self.ip = ip
        self.port = port
        self.scheme = scheme
        self.param = param

    def __str__(self):
        param = '/'.join(self.param) if self.param else ''
        port = ':{}'.format(self.port) if self.port else ''
        return '{}://{}{}/{}'.format(self.scheme, self.ip, port, param)


class IMCNode:
    """
    An IMC node consisting of it's address, services and entities.
    """
    @staticmethod
    def from_announce(msg, service_filter=None, is_fixed=False):
        node = IMCNode(src=msg.src, sys_name=msg.sys_name, service_filter=service_filter, is_fixed=is_fixed)
        node.update_announce(msg)
        return node

    def __init__(self, src, sys_name, service_filter=None, is_fixed=False):
        """
        :param src: The IMC source address
        :param sys_name: The system name of the node
        :param announce: Initialize the node with the contents of an Announce message
        :param service_filter: Only use the services specified in order of priority (TODO IMPLEMENT)
        :param is_fixed: Nodes that are fixed has been added manually and is not pruned when comms are lost
        """
        if service_filter is None:
            service_filter = ('imc+udp',)

        #
        # Args
        #

        # System imc id
        self.src = src  # type: int
        # System imc name
        self.sys_name = sys_name  # type: str
        # Unparsed services string
        self.services_string = ''  # type: str
        # Parsed services
        self.services = {}  # type: Dict[str, IMCService]
        # Parsed entities
        self.entities = {}  # type: Dict[str, int]
        # Node arguments
        self.service_filter = service_filter
        # Fixed nodes are never removed from the node map (no timeout)
        self.is_fixed = is_fixed

        #
        # State
        #

        # Time of last heartbeat
        self.t_last_heartbeat = None  # type: float
        # Time of last announce
        self.t_last_announce = None  # type: float

    @property
    def name(self):
        return self.sys_name

    @property
    def id(self):
        return self.src

    def update_announce(self, msg):
        """
        Update the node data based on a new announce message.
        """

        # Use local time in case remote system has a different time-zone
        self.t_last_announce = time.time()

        # Update the services
        if self.services_string != msg.services:
            self.update_services(msg.services)
            self.services_string = msg.services

    def update_heartbeat(self):
        """
        Update the connection status from an heartbeat message
        """
        # Use local time in case remote system has a different time-zone
        self.t_last_heartbeat = time.time()

    def update_services(self, service_string: str):
        """
        Parse the service string from an announce message to IMCService objects
        :param service_string: The service string from an announce message (protocols/ips/ports)
       """
        self.services = {}
        for svc in service_string.split(';'):
            s = IMCService.from_url(svc)
            try:
                self.services[s.scheme].append(s)
            except KeyError:
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
        
        msg.dst = self.src

        try:
            imcudp_services = self.services['imc+udp']
        except KeyError:
            if not self.is_fixed:
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