import socket, struct, asyncio, logging
import pyimc
from pyimc.common import multicast_ip

logger = logging.getLogger('pyimc.udp')


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
        if message.__module__ == '_pyimc':
            b = pyimc.Packet.serialize(message)
            self.sock.sendto(b, (self.dst, port))
        else:
            raise TypeError('Unknown message passed ({})'.format(type(message)))


class IMCProtocolUDP(asyncio.DatagramProtocol):
    def __init__(self, instance, is_multicast=False, static_port=None):
        """
        Sets up an datagram listener for IMC messages
        :param instance: The parent object (derived from IMCBase)
        :param is_multicast: If true, the protocol listens for messages over multicast (e.g. Announce messages)
        :param static_port: Optional static port to listen on. RuntimeError is raised if port is in use.
        """
        self.transport = None
        self.instance = instance
        self.is_multicast = is_multicast
        self.static_port = static_port

    def connection_made(self, transport):
        self.transport = transport
        sock = self.transport.get_extra_info('socket')

        # Set the selected port in the IMCBase instance
        if self.is_multicast:
            sock = get_multicast_socket(sock)
            self.instance._port_mc = sock.getsockname()[1]
        else:
            sock = get_imc_socket(sock, self.static_port)
            self.instance._port_imc = sock.getsockname()[1]

            # Send an announce immediately after socket is ready (possible speedup in transports)
            try:
                self.instance._send_announce()
            except AttributeError:
                pass

    def datagram_received(self, data, addr):
        try:
            p = pyimc.Packet.deserialize(data)

            if p is not None:
                self.instance.post_message(p)
        except RuntimeError as e:
            logger.error('Exception raised when deserializing message: {}'.format(e))

    def error_received(self, exc):
        logger.error('Error received: {}'.format(exc))

    def connection_lost(self, exc):
        # TODO: Reestablish connection?
        logger.debug('Lost connection {}'.format(exc))


def get_multicast_socket(sock=None, static_port=None):
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
    try:
        mreq = struct.pack('4sL', socket.inet_aton(multicast_ip), socket.INADDR_ANY)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

        # Do not loop back own messages
        sock.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_LOOP, 0)
    except OSError as e:
        logger.error('Unable to obtain socket with multicast enabled.')
        raise e

    if static_port is not None:
        port = static_port
        try:
            sock.bind(('0.0.0.0', static_port))
        except OSError:
            # Socket already in use without SO_REUSEADDR enabled
            raise RuntimeError('The IMC multicast port specified is already in use ({}).'.format(port))
    else:
        port = None
        for i in range(30100, 30105):
            try:
                sock.bind(('0.0.0.0', i))
                port = i
                break
            except OSError:
                # Socket already in use without SO_REUSEADDR enabled
                continue

    if not port:
        raise RuntimeError('No IMC multicast ports free on local interface.')

    return sock


def get_imc_socket(sock=None, static_port=None):
    if not sock:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    sock.settimeout(0.001)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    if static_port is not None:
        # Use specific port
        try:
            sock.bind(('0.0.0.0', static_port))
        except OSError:
            # Socket already in use without SO_REUSEADDR enabled
            raise RuntimeError('The IMC port specified is already in use ({}).'.format(port))
    else:
        # Try ports in the typical IMC/DUNE range
        port = None
        for i in range(6001, 6030):
            try:
                sock.bind(('0.0.0.0', i))
                port = i
                break
            except OSError:
                # Socket already in use without SO_REUSEADDR enabled
                continue

        if not port:
            raise RuntimeError('No IMC ports free on local interface (6001-6030).')

    return sock
