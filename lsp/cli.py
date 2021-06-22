#   encoding: utf8
#   filename: cli.py
"""A language model as a Language Server Protocol (aka LSP) service.
"""

import logging
import inspect

from argparse import ArgumentParser, ArgumentTypeError, FileType
from dataclasses import dataclass, field
from enum import Enum
from json import loads, dumps
from os import getppid
from pathlib import Path
from socket import AF_INET, SOCK_STREAM, SO_REUSEADDR, SOL_SOCKET, socket
from string import ascii_letters
from sys import stderr
from typing import Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from .completion import Completor
from .corpus import Corpus
from .lsp import Dispatcher, ErrorCode, LSPError, Router
from .rpc import make_transport_pair
from .version import version


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

    def __str__(self) -> str:
        if self.proto == Proto.STDIO:
            return f'{self.proto.value}:'
        elif self.proto in (Proto.TCP, Proto.TCP4, Proto.TCP6):
            return f'{self.proto.value}://{self.host}:{self.port}'
        elif self.proto == Proto.UNIX:
            return f'{self.proto.value}://{self.path}'
        else:
            raise RuntimeError('Unexpected execution path.')


def watch_pid(pid: int):
    logging.info('watch for process with pid %d', pid)


def initialize(params):
    logging.info('handle initialize() procedure call')

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


def initialized(params):
    logging.info('handle initialized() notification')


def shutdown(params):
    logging.info('handle shutdown() procedure call')


def exit(params):
    logging.info('handle exit() notification')


class TextDocument:

    @staticmethod
    def did_open(params):
        logging.info('handle did_open() notification')
        corpus.open(params['textDocument']['uri'],
                    params['textDocument']['text'])

    @staticmethod
    def did_change(params):
        logging.info('handle did_change() notification')
        uri = params['textDocument']['uri']
        ver = params['textDocument']['version']
        changes = params['contentChanges']
        logging.info('apply %d changes to %s:%d', len(changes), uri, ver)
        for change in changes:
            if change.get('range'):
                logging.warning('lsp does not support incremental changes')
            else:
                corpus.set(uri, change['text'])

    @staticmethod
    def did_close(params):
        logging.info('handle did_close() notification')

    def completion(params):
        logging.info('handle completion() procedure call')
        uri = params['textDocument']['uri']
        line = params['position']['line']
        char = params['position']['character']

        logging.info('complete at %d:%d for document %s', line, char, uri)
        doc = corpus.get(uri)
        labels = []
        for item in completor.complete(doc, line, char):
            labels.append({'label': item})

        return labels


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


def serve_client(conn: socket, addr: str):
    router = Router()
    router.register('initialize', initialize, False)
    router.register('initialized', initialized)
    router.register('shutdown', shutdown, False)
    router.register('exit', exit)
    router.register('textDocument/didOpen', TextDocument.did_open)
    router.register('textDocument/didChange', TextDocument.did_change)
    router.register('textDocument/didClose', TextDocument.did_close)
    router.register('textDocument/completion', TextDocument.completion)

    with conn:
        logging.info('accept connection from %s:%d', *addr)
        reader, writer = make_transport_pair(conn)
        for req in reader:
            logging.info('handle incoming request')
            mediatype, charset = parse_mediatype(req.content_type)
            logging.info('content type is %s and charset is %s',
                         mediatype, charset)
            obj = loads(req.content.decode(charset))
            print(dumps(obj=obj,
                        ensure_ascii=False,
                        indent=2))
            logging.info('process incoming request')
            res = router.handle(obj)
            if res is None:
                continue
            logging.info('write back response (or error)')
            content = dumps(res, ensure_ascii=False, indent=2)
            print(content)
            writer.write(content.encode(charset))

    logging.info('connection is closed for %s:%d', *addr)


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
    global corpus, completor

    logging.info('instantiate corpus manager')
    corpus = Corpus()

    logging.info('instantiate completion provder')
    completor = Completor.load(
        vocab_path=str(vocab),
        model_path=str(model),
        context_size=context_size,
        nosudgests=num_results,
    )

    logging.info('serve client on %s', addr)
    if addr.proto == Proto.STDIO:
        logging.error('serving with stdio/stdout is not implemented yet')
    elif addr.proto in (Proto.TCP, Proto.TCP4, Proto.TCP6):
        with socket(AF_INET, SOCK_STREAM) as sock:
            sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
            sock.bind((addr.host, addr.port))
            sock.listen(1)
            while True:
                serve_client(*sock.accept())
    elif addr.proto == Proto.UNIX:
        logging.error('serving with unix sockets is not implemented yet')


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


LOG_LEVELS = {
    'debug': logging.DEBUG,
    'info': logging.INFO,
    'warn': logging.WARN,
    'error': logging.ERROR,
}


class AddrType:

    def __init__(self):
        pass

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


# Parser for connectivity options.
parser_opt_connection = ArgumentParser(add_help=False)
parser_opt_connection.add_argument('-P', '--protocol', default=Proto.TCP, type=Proto, choices=sorted(x.value for x in Proto), help='Communication protocol to use.')  # noqa: E501
parser_opt_connection.add_argument('-H', '--host', default='127.0.0.1', type=str, help='Address to listen.')  # noqa: E501
parser_opt_connection.add_argument('-p', '--port', default=8080, type=int, help='Port to listen.')  # noqa: E501
parser_opt_connection.add_argument('addr', default=Addr(Proto.STDIO), nargs='?', type=AddrType(), help='LSP address as URI to communicate (valid schemes are tcp[46] and unix).')  # noqa: E501

# Root parser for the tool.
parser = ArgumentParser(description=__doc__)
parser.set_defaults(func=None)
parser.add_argument('-c', '--config', type=PathType(True, not_dir=True), help='path to configuration file to use')
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
