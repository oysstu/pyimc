import logging
import ipaddress as ip
from urllib.parse import urlparse

from pyimc.udp import IMCSenderUDP
from pyimc.network_utils import get_interfaces

logger = logging.getLogger('pyimc.node')


class IMCService:
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
    def __init__(self, announce=None, service_filter=('imc+udp',)):
        """

        :param announce:
        :param services:
        """
        self.announce = None  # type: pyimc.Announce
        self.services = {}  # type: Dict[str, IMCService]
        self.entities = {}  # type: Dict[str, int]
        self.heartbeat = None  # type: float

        if announce:
            self.update_announce(announce)

    @property
    def name(self):
        return self.announce.sys_name if self.announce else None

    @property
    def id(self):
        return self.announce.src if self.announce else None

    def update_announce(self, msg):
        self.announce = msg
        if msg:
            self.update_services()

    def update_heartbeat(self, msg):
        self.heartbeat = msg.timestamp

    def update_services(self):
        self.services = {}
        for svc in self.announce.services.split(';'):
            s = IMCService(svc)
            try:
                self.services[s.scheme].append(s)
            except KeyError as e:
                self.services[s.scheme] = [s]

    def update_entity_list(self, msg):
        self.entities = {k: int(v) for k, v in (x.split('=') for x in msg.list.split(';'))}

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
        return 'IMCNode(0x{:X}, {})'.format(self.announce.src, self.announce.sys_name)

    def __repr__(self):
        return 'IMCNode(0x{:X}, {})'.format(self.announce.src, self.announce.sys_name)


if __name__ == '__main__':
    pass