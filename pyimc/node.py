from urllib.parse import urlparse

import pyimc
from pyimc.udp import IMCSenderUDP


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
    def __init__(self, announce=None):
        self.announce = None  # Updated by Announce
        self.services = {}  # Updated by Announce
        self.entities = {}  # Updated by EntityList message
        self.state = None  # Updated by EntityState message
        self.heartbeat = None  # Updated by heartbeat message (timestamp)

        if announce:
            self.update_announce(announce)

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
        # TODO: Verify that UDP service exists, add TCP
        imc_service = self.services['imc+udp'][0]  # TODO: How to select interface if multiple imc services announced?
        node_ip, node_port = imc_service.ip, imc_service.port
        with IMCSenderUDP(node_ip) as s:
            s.send(message=msg, port=node_port)

    def __str__(self):
        return 'IMCNode(0x{:X}, {})'.format(self.announce.src, self.announce.sys_name)

    def __repr__(self):
        return 'IMCNode(0x{:X}, {})'.format(self.announce.src, self.announce.sys_name)


if __name__ == '__main__':
    # Test service parsing
    x = 'dune://0.0.0.0/uid/431358805411;dune://0.0.0.0/version/2017.01.0;ftp://192.168.1.3:30021/;http://192.168.1.3:8080/dune;imc+info://0.0.0.0/version/5.4.11;imc+udp://192.168.1.3:6002/'
    s = [IMCService(y) for y in x.split(';')]
    print(s[-1].ip, s[-1].port)