#   encoding: utf8
#   filename: cli.py
"""A language model as a Language Server Protocol (aka LSP) service.
"""

import logging
import inspect

from argparse import ArgumentParser, ArgumentTypeError, FileType
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from json import loads, dumps
from os import getppid
from pathlib import Path
from socket import AF_INET, SOCK_STREAM, SO_REUSEADDR, SOL_SOCKET, socket
from string import ascii_letters
from sys import stderr
from typing import Dict, List, Optional, Tuple
from typing.io import IO
from urllib.parse import parse_qs, urlparse

from .completion import get_completor
from .corpus import Corpus
from .lsp import \
    Dispatcher, ErrorCode, LanguageServerProtocol, LSPError, Router
from .rpc import PacketReader, PacketWriter
from .version import version


LOG_LEVELS = {
    'debug': logging.DEBUG,
    'info': logging.INFO,
    'warn': logging.WARN,
    'error': logging.ERROR,
}


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


class Proto(Enum):

    STDIO = 'stdio'

    TCP = 'tcp'

    TCP4 = 'tcp4'

    TCP6 = 'tcp6'

    UNIX = 'unix'


@dataclass
class Addr:

    proto: Proto

    host: Optional[str] = None

    port: Optional[int] = None

    path: Optional[str] = None

    opts: Dict[str, List[str]] = field(default_factory=dict)

    def update(self, *, host: Optional[str] = None,
               port: Optional[int] = None, path: Optional[str] = None):
        if host:
            self.host = host
        if port:
            self.port = port
        if path:
            self.path = path

    def __str__(self) -> str:
        if self.proto == Proto.STDIO:
            return f'{self.proto.value}:'
        elif self.proto in (Proto.TCP, Proto.TCP4, Proto.TCP6):
            return f'{self.proto.value}://{self.host}:{self.port}'
        elif self.proto == Proto.UNIX:
            return f'{self.proto.value}://{self.path}'
        else:
            raise RuntimeError('Unexpected execution path.')


class AddrType:

    def __call__(self, value: str) -> Addr:
        # If addres is just a dash then exits with suitable address.
        if value == '-':
            return Addr(proto=Proto.STDIO,
                        host=None,
                        port=None,
                        path=None,
                        opts={})

        uri = urlparse(value)

        # Parse and validate proto.
        if not uri.scheme:
            raise ArgumentTypeError(f'no scheme is specified: {value}')
        try:
            proto = Proto(uri.scheme)
        except ValueError:
            raise ArgumentTypeError(f'unknown scheme: {value}')

        return Addr(proto=proto,
                    host=uri.hostname,
                    port=uri.port,
                    path=uri.path,
                    opts=parse_qs(uri.query))


class PathType:

    def __init__(self, exists=False, not_dir=False, not_file=False):
        self.exists = exists
        self.check_dir = not_dir
        self.check_file = not_file

    def __call__(self, value: str) -> Path:
        path = Path(value)

        # If there is no check for path existance then exit.
        if not self.exists:
            return path

        # Check that path exists.
        if not path.exists():
            raise ArgumentTypeError(f'path does not exist: {path}')

        # Check type of a filesystem object referenced by path.
        if self.check_dir and path.is_dir():
            raise ArgumentTypeError(f'directory is not allowed: {path}')

        if self.check_file and path.is_file():
            raise ArgumentTypeError(f'file is not allowed: {path}')

        return path


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


class Protocol(LanguageServerProtocol):

    def __init__(self, session):
        super().__init__()
        self.session = session

    def watch_pid(self, pid: int):
        logging.info('watch for process with pid %d', pid)

    def initialize(self, params):
        logging.info('handle initialize() procedure call')

        logging.info('instantiate corpus manager')
        self.corpus = Corpus()

        logging.info('instantiate completor')
        with open('vocab.txt') as fin:
            vocab = fin.read().splitlines()[:10]
        self.completor = get_completor(vocab)

        pid = params.get('processId')
        if pid and not isinstance(pid, int):
            raise LSPError(ErrorCode.InvalidParams)
        elif pid is None:
            pid = getppid()

        return {
            'capabilities': {
                'textDocumentSync': {
                    'change': 2,
                    'openClose': True,
                    'save': True,
                },
                'completionProvider': {
                    'triggerCharacters': list(ascii_letters.split()),
                    'allCommtCharacters': list(' !?:;,.'),
                    'resolveProvider': False,
                },
            },
            'serverInfo': {
                'name': 'lsp-lm',
                'version': version,
            },
        }

    def initialized(self, params):
        logging.info('handle initialized() notification')

    def shutdown(self, params):
        logging.info('handle shutdown() procedure call')

    def exit(self, params):
        logging.info('handle exit() notification')

    def completion(self, params):
        logging.info('handle completion() procedure call')
        uri = params['textDocument']['uri']
        line = params['position']['line']
        char = params['position']['character']

        logging.info('complete at %d:%d for document %s', line, char, uri)
        doc = self.corpus.get(uri)
        labels = []
        for item in self.completor.complete(doc, line, char):
            labels.append({'label': item})

        return labels

    def did_change(self, params):
        logging.info('handle did_change() notification')
        uri = params['textDocument']['uri']
        ver = params['textDocument']['version']
        changes = params['contentChanges']
        logging.info('apply %d changes to %s:%d', len(changes), uri, ver)
        for change in changes:
            if change.get('range'):
                logging.warning('lsp does not support incremental changes')
            else:
                self.corpus.set(uri, change['text'])

    def did_close(self, params):
        logging.info('handle did_close() notification')

    def did_open(self, params):
        logging.info('handle did_open() notification')
        self.corpus.open(params['textDocument']['uri'],
                         params['textDocument']['text'])

    def did_save(self, params):
        logging.info('handle did_save() notification')


class Server:
    """Class Server manages LSP session (session per connection) and underlying
    communication transport (e.g. standard IO, UNIX or TCP sockets).

    :param addr: Specification of communication channel.
    :param protocol: Factory which produce and object to handle session
                     (aka connection).
    """

    def __init__(self, addr: Addr, protocol):
        self.addr = addr
        self.protocol = protocol
        self.pool = ThreadPoolExecutor(4, '[lsp]')
        self.sessions = []

    def start(self):
        """Method start runs server in blocking way. In order to stop serving
        one should call method stop().
        """
        logging.info('serve client on %s', self.addr)

        if self.addr.proto == Proto.STDIO:
            logging.error('serving with stdio/stdout is not implemented yet')
        elif self.addr.proto in (Proto.TCP, Proto.TCP4, Proto.TCP6):
            self._accept_tcp_connections(self.addr)
        elif self.addr.proto == Proto.UNIX:
            logging.error('serving with unix sockets is not implemented yet')

    def stop(self, timeout=None):
        """Method stop does gracefull shutdown of server.
        """
        raise NotImplementedError

    def _accept_tcp_connections(self, addr: Addr):
        with socket(AF_INET, SOCK_STREAM) as sock:
            sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
            sock.bind((addr.host, addr.port))
            sock.listen(1)

            # TODO: Accept incomming connections forever and handle each one in
            # a separate thread.
            while True:
                conn = sock.accept()
                future = self.pool.submit(self._handle_tcp_connection, *conn)
                future.add_done_callback(self._handle_tcp_connection_close)

    def _handle_tcp_connection(self, sock: socket, addr: Tuple[str, int]):
        logging.info('accept connection from %s:%d', *addr)
        try:
            with sock:
                fileobj = sock.makefile('rwb')
                session = Session(fileobj, fileobj, self, self.protocol)
                self.sessions.append(session)
                session.start()
        except Exception:
            logging.exception('loose connection from %s:%d', *addr)
        else:
            logging.info('close connection from %s:%d', *addr)

    def _handle_tcp_connection_close(self, future: Future):
        # TODO: Remove from session index.
        if (exc := future.exception()):
            logging.error('connection handler raise an exception: %s', exc)


def connect(addr: Addr):
    logging.info('connect to %s', addr)
    if addr.proto == Proto.STDIO:
        logging.error('connecting via stdio/stdout is not implemented yet')
    elif addr.proto in (Proto.TCP, Proto.TCP4, Proto.TCP6):
        with socket(AF_INET, SOCK_STREAM) as sock:
            sock.connect((addr.host, addr.port))
            file = sock.makefile('rwb')
            disp = Dispatcher(file, file, True)
            disp.request('initialize', {
                'processId': None,
                'clientInfo': {
                    'name': 'lsp',
                    'version': version,
                },
            })
            sock.recv(1024)
    elif addr.proto == Proto.UNIX:
        logging.error('connecting via unix sockets is not implemented yet')


def serve(model: Path, vocab: Path, context_size: int, num_results: int,
          addr: Addr, host: str, port: int):
    addr.update(host=host, port=port)

    # TODO: Collect all options to a container and construct closed factory for
    # serving.
    protocol = Protocol

    server = Server(addr, protocol)
    server.start()


def help_():
    parser.print_help()


def version_():
    print(f'lsp-lm version {version}')


def main():
    # Parse command line arguments. If no subcommand were run then show usage
    # and exit. We assume that only main parser (super command) has valid value
    # in func attribute.
    args = parser.parse_args()
    if args.func is None:
        parser.print_usage()
        return

    # Find CLI option or argument by parameter name of handling function.
    kwargs = {}
    spec = inspect.getfullargspec(args.func)
    for name in spec.args:
        kwargs[name] = getattr(args, name)

    # Set up basic logging configuration.
    if (stream := args.log_output) is None:
        stream = stderr

    logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s',
                        level=LOG_LEVELS[args.log_level],
                        stream=stream)

    # Invoke CLI command handler.
    args.func(**kwargs)


# Parser for connectivity options.
parser_opt_connection = ArgumentParser(add_help=False)
parser_opt_connection.add_argument('-P', '--protocol', default=Proto.TCP, type=Proto, choices=sorted(x.value for x in Proto), help='Communication protocol to use.')  # noqa: E501
parser_opt_connection.add_argument('-H', '--host', type=str, help='Address to listen.')  # noqa: E501
parser_opt_connection.add_argument('-p', '--port', type=int, help='Port to listen.')  # noqa: E501
parser_opt_connection.add_argument('addr', default=Addr(Proto.STDIO), nargs='?', type=AddrType(), help='LSP address as URI to communicate (valid schemes are tcp[46] and unix).')  # noqa: E501

# Root parser for the tool.
parser = ArgumentParser(description=__doc__)
parser.set_defaults(func=None)
parser.add_argument('--log-level', default='info', choices=sorted(LOG_LEVELS.keys()), help='set logger verbosity level')  # noqa: E501
parser.add_argument('--log-output', default=stderr, metavar='FILENAME', type=FileType('w'), help='set output file or stderr (-) for logging')  # noqa: E501

subparsers = parser.add_subparsers()

parser_connect = subparsers.add_parser('connect', parents=[parser_opt_connection], help='Connect to language server.')  # noqa: E501
parser_connect.set_defaults(func=connect)

parser_help = subparsers.add_parser('help', add_help=False, help='Show this message and exit.')  # noqa: E501
parser_help.set_defaults(func=help_)

parser_serve = subparsers.add_parser('serve', parents=[parser_opt_connection], help='Run language server.')  # noqa: E501
parser_serve.set_defaults(func=serve)
parser_serve.add_argument('-c', '--context-size', default=3, type=int, help='Size of context used to make predictions.')  # noqa: E501
parser_serve.add_argument('-n', '--num-results', default=10, type=int, help='Number of completion items in response.')  # noqa: E501
parser_serve.add_argument('-M', '--model', type=PathType(True, not_file=True), help='Path to model file or directory.')  # noqa: E501
parser_serve.add_argument('-V', '--vocab', type=PathType(True, not_dir=True), help='Path to vocabulary file.')  # noqa: E501

parser_version = subparsers.add_parser('version', add_help=False, help='Show version information.')  # noqa: E501
parser_version.set_defaults(func=version_)

__all__ = (
    main,
)
