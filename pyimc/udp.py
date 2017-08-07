import socket, struct, asyncio, logging
import pyimc
from pyimc.common import multicast_ip


class IMCSenderUDP:
    def __init__(self, ip_dst, local_port=None):
        self.dst = ip_dst
        self.local_port = local_port

    def __enter__(self):
        # Set up socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self.sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 10)

        if self.local_port:
            # Bind the socket to a local interface
            self.sock.bind(('', self.local_port))

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.sock.close()

    def send(self, message, port):
        if message.__module__ == 'imc':
            b = message.serialize()
            self.sock.sendto(b, (self.dst, port))
        else:
            raise TypeError('Unknown message passed ({})'.format(type(message)))


class IMCProtocolUDP(asyncio.DatagramProtocol):
    def __init__(self, instance, is_multicast=False):
        self.transport = None
        self.parser = pyimc.Parser()
        self.instance = instance
        self.is_multicast = is_multicast

    def connection_made(self, transport):
        self.transport = transport
        sock = self.transport.get_extra_info('socket')

        # Set the selected port in the IMCBase instance
        if self.is_multicast:
            sock = get_multicast_socket(sock)
            self.instance._port_mc = sock.getsockname()[1]
        else:
            sock = get_imc_socket(sock)
            self.instance._port_imc = sock.getsockname()[1]


    def datagram_received(self, data, addr):
        self.parser.reset()
        p = self.parser.parse(data)
        if pyimc.Message in type(p).__bases__:
            try:
                for fn in self.instance._subs[type(p)]:
                    fn(p)
                for fn in self.instance._subs[pyimc.Message]:
                    fn(p)
            except KeyError:
                pass
        elif type(p) is pyimc.Message:
            # Subscriptions to pyimc.Message receives all messages
            try:
                for fn in self.instance._subs[pyimc.Message]:
                    fn(p)
            except KeyError:
                pass
        else:
            logging.warning('Received IMC message that was not a subclass of pyimc.Message')

    def error_received(self, exc):
        logging.error('Error received: {}'.format(exc))

    def connection_lost(self, exc):
        # TODO: Reestablish connection?
        logging.debug('Lost connection {}'.format(exc))


def get_multicast_socket(sock=None):
    if not sock:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    sock.settimeout(0.001)

    # set multicast interface to any local interface
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton('0.0.0.0'))

    # Enable multicast, TTL should be <32 (local network)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 5)

    # Allow reuse of addresses
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # Allow receiving multicast broadcasts (subscribe to multicast group)
    mreq = struct.pack('4sL', socket.inet_aton(multicast_ip), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

    # Do not loop back own messages
    sock.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_LOOP, 0)

    port = None
    for i in range(30100, 30105):
        try:
            # Binding to 0.0.0.0 results in multiple messages if there is multiple interfaces available
            # Kept as-is to avoid losing messages
            sock.bind(('0.0.0.0', i))
            port = i
            break
        except OSError as e:
            # Socket already in use without SO_REUSEADDR enabled
            continue

    if not port:
        raise RuntimeError('No IMC multicast ports free on local interface.')

    return sock


def get_imc_socket(sock=None):
    if not sock:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    sock.settimeout(0.001)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    port = None
    for i in range(6001, 6030):
        try:
            sock.bind(('0.0.0.0', i))
            port = i
            break
        except OSError as e:
            # Socket already in use without SO_REUSEADDR enabled
            continue

    if not port:
        raise RuntimeError('No IMC ports free on local interface.')

    return sock