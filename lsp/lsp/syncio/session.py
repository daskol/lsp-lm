#   encoding: utf8
#   filename: session.py

import logging

from concurrent.futures import Future, ThreadPoolExecutor
from json import dumps, loads
from os import unlink
from socket import AF_INET, AF_UNIX, SOCK_STREAM, SO_REUSEADDR, SOL_SOCKET, \
    socket
from sys import stdin, stdout
from typing import IO, List, Tuple

from .lsp import Router
from .rpc import PacketReader, PacketWriter
from ..types import Addr, Proto


def parse_mediatype(value: str):
    if not value:
        return 'application/vscode-jsonrpc', 'utf-8'

    splits = value.lower().split(';', 1)
    mediatype = splits[0]
    charset = 'utf-8'

    if len(splits) == 2:
        if splits[1].startswith('charset='):
            charset = splits[1][8:]

        if charset == 'utf8':
            charset = 'utf-8'

    return mediatype, charset


class Session:
    """Processing pipeline is the following.

        bytes
        Frame
        Packet
        Request/Notification
        Response/Error
        Packet
        Frame
        bytes
    """

    def __init__(self, sin: IO, sout: IO, server: 'Server', factory):
        self.server = server
        self.reader = PacketReader(sin)
        self.writer = PacketWriter(sout)
        self.router = Router()

        # Fabricate language protocol and register handlers.
        self.protocol = factory(self)
        self.router.register(self.protocol)

    def start(self):
        logging.info('enter into communication loop')
        for iframe in self.reader:
            ipacket, charset = self.read_packet(iframe)
            if (opacket := self.route(ipacket)):
                oframe = self.write_packet(opacket, charset)
                self.writer.write(oframe)
        logging.info('leave communication loop')

    def stop(self, timeout=None):
        raise NotImplementedError

    def read_packet(self, iframe):
        logging.info('read a packet from a frame')
        mediatype, charset = parse_mediatype(iframe.content_type)
        packet = loads(iframe.content.decode(charset))
        logging.debug('ipacket is the following\n%s',
                      dumps(obj=packet, ensure_ascii=False, indent=2))
        return packet, charset

    def write_packet(self, opacket, charset):
        logging.info('write a packet to a frame')
        logging.debug('opacket is the following\n%s',
                      dumps(obj=opacket, ensure_ascii=False, indent=2))
        return dumps(opacket).encode(charset)

    def route(self, ipacket):
        if (version := ipacket.get('jsonrpc')) != '2.0':
            logging.warning('unsupported json rpc version: %s', version)

        if not (method := ipacket.get('method')):
            logging.error('no method to call')
            return  # TODO: Return an error.
        elif not isinstance(method, str):
            logging.error('field method is not a string')
            return  # TODO: Return an error.

        params = ipacket.get('params')

        if (request_id := ipacket.get('id')) is None:
            self.handle_notification(method, params)
            return
        elif isinstance(request_id, (str, int)):
            result = self.handle_request(method, params)
        else:
            logging.error('wrong type of request identifier')
            return  # TODO: Return an error.

        # Construct output packet.
        opacket = {
            'jsonrpc': '2.0',
            'id': request_id,
            'result': result,
        }

        return opacket

    def handle_notification(self, method: str, params):
        logging.info('handle notification %s', method)
        self.router.invoke(method, params)

    def handle_request(self, method: str, params):
        logging.info('handle request %s', method)
        return self.router.invoke(method, params)


class Server:
    """Class Server manages LSP session (session per connection) and underlying
    communication transport (e.g. standard IO, UNIX or TCP sockets).

    :param addr: Specification of communication channel.
    :param protocol: Factory which produce and object to handle session
                     (aka connection).
    """

    def __init__(self, addr: Addr, protocol, tls_context=None):
        self.addr = addr
        self.protocol = protocol
        self.pool = ThreadPoolExecutor(4, '[lsp]')
        self.sessions: List[Session] = []
        self.tls_context = tls_context

    def start(self):
        """Method start runs server in blocking way. In order to stop serving
        one should call method stop().
        """
        logging.info('serve client on %s', self.addr)

        if self.addr.proto == Proto.STDIO:
            self._accept_std_connections()
        elif self.addr.proto in (Proto.TCP, Proto.TCP4, Proto.TCP6):
            self._accept_tcp_connections(self.addr)
        elif self.addr.proto == Proto.UNIX:
            self._accept_ipc_connections(self.addr)

    def stop(self, timeout=None):
        """Method stop does gracefull shutdown of server.
        """
        raise NotImplementedError

    def _accept_ipc_connections(self, addr: Addr):
        if (path := addr.path) is None:
            raise ValueError('Unix socket address should be specified.')

        with socket(AF_UNIX, SOCK_STREAM) as sock:
            sock.bind(path)
            sock.listen(1)

            unlink(path)

            while True:
                conn, _ = sock.accept()

                # Handle connection in a separate thread in thread pool. Also,
                # set up finalizer to remove connection fron an index.
                future = self.pool.submit(self._open_ipc_connection, conn)
                future.add_done_callback(self._close_ipc_connection)

    def _accept_std_connections(self):
        logging.info('accept stdio connection')
        try:
            sin = stdin.buffer
            sout = stdout.buffer
            session = Session(sin, sout, self, self.protocol)
            self.sessions.append(session)
            session.start()
        except Exception:
            logging.exception('loose stdio connection')
        else:
            logging.info('close stdio connection')

    def _accept_tcp_connections(self, addr: Addr):
        with socket(AF_INET, SOCK_STREAM) as sock:
            sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
            sock.bind((addr.host, addr.port))
            sock.listen(1)

            # Accept incomming connections forever and handle each one in a
            # separate thread.
            while True:
                conn = sock.accept()

                # Handle connection in a separate thread in thread pool. Also,
                # set up finalizer to remove connection fron an index.
                future = self.pool.submit(self._open_tcp_connection, *conn)
                future.add_done_callback(self._close_tcp_connection)

    def _close_connection(self, future: Future):
        # TODO: Remove from session index.
        if (exc := future.exception()):
            logging.error('connection handler raise an exception: %s', exc)

    def _close_ipc_connection(self, future: Future):
        self._close_connection(future)

    def _close_tcp_connection(self, future: Future):
        self._close_connection(future)

    def _open_ipc_connection(self, sock: socket):
        logging.info('accept ipc connection')
        try:
            with sock:
                fileobj = sock.makefile('rwb')
                session = Session(fileobj, fileobj, self, self.protocol)
                self.sessions.append(session)
                session.start()
        except Exception:
            logging.exception('loose ipc connection')
        else:
            logging.info('close connection')

    def _open_tcp_connection(self, sock: socket, addr: Tuple[str, int]):
        logging.info('accept connection from %s:%d', *addr)
        try:
            # If there is a SSL context than we should wrap socket in the
            # SSL context.
            if self.tls_context:
                conn = self.tls_context.wrap_socket(sock, True)
            else:
                conn = sock

            with conn:
                fileobj = conn.makefile('rwb')
                session = Session(fileobj, fileobj, self, self.protocol)
                self.sessions.append(session)
                session.start()
        except Exception:
            logging.exception('loose connection from %s:%d', *addr)
        else:
            logging.info('close connection from %s:%d', *addr)
