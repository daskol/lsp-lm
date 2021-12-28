#   encoding: utf8
#   filename: cli.py
"""A language model as a Language Server Protocol (aka LSP) service.
"""

import logging
import inspect

from argparse import ArgumentParser, ArgumentTypeError, FileType
from pathlib import Path
from socket import AF_INET, SOCK_STREAM, socket
from ssl import SSLContext
from sys import stderr
from typing import Optional
from urllib.parse import parse_qs, urlparse

from .lsp import Addr, Proto
from .lsp.syncio import Dispatcher
from .version import version

__all__ = ('main', )


LOG_LEVELS = {
    'debug': logging.DEBUG,
    'info': logging.INFO,
    'warn': logging.WARN,
    'error': logging.ERROR,
}


def read_password(path: Path) -> str:
    with open(path) as fin:
        return fin.read().strip()


def make_password_reader(path: Optional[Path]):
    if path is None:
        return None
    else:
        return lambda: read_password(path)


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


def serve(context_size: int, model: Path, model_type: str, vocab: Path,
          num_results: int, hf_model: str, addr: Addr, host: str, port: int,
          tls_cert: Optional[Path], tls_key: Optional[Path],
          tls_pass: Optional[Path]):
    # Resolve address components.
    addr.update(host=host, port=port)

    # Combine all ranking (IR) related options together.
    ir_opts = {
        'num_results': num_results,
    }

    # Combine all language model related options together.
    lm_opts = {
        'context_size': context_size,
        'model_path': model,
        'model_type': model_type,
        'num_results': num_results,
        'vocab_path': vocab,
    }

    # Create TLS context if posssible.
    if tls_cert is None:
        tls_context = None
    else:
        logging.info('create TLS context from %s', tls_cert)
        tls_context = SSLContext()
        tls_context.load_cert_chain(certfile=tls_cert,
                                    keyfile=tls_key,
                                    password=make_password_reader(tls_pass))

    # Load lazily application controller and run application in blocking mode.
    from .app import Application
    app = Application(addr, tls_context, ir_opts, lm_opts)
    app.run()


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
parser_opt_connection.add_argument('-P', '--protocol', default=Proto.TCP, type=Proto, choices=Proto, help='Communication protocol to use.')  # noqa: E501
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
parser_serve.add_argument('-m', '--model-type', type=str, help='Type of language model to use (e.g. hf or vocab).')  # noqa: E501
parser_serve.add_argument('-n', '--num-results', default=10, type=int, help='Number of completion items in response.')  # noqa: E501
parser_serve.add_argument('-M', '--model', type=PathType(True, not_file=True), help='Path to model file or directory.')  # noqa: E501
parser_serve.add_argument('-V', '--vocab', type=PathType(True, not_dir=True), help='Path to vocabulary file.')  # noqa: E501
parser_serve.add_argument('--hf-model', type=str, help='HuggingFace model.')
parser_serve.add_argument('--tls-cert', type=PathType(True, not_dir=True), help='Path to TLS certificate.')  # noqa: E501
parser_serve.add_argument('--tls-key', type=PathType(True, not_dir=True), help='Path to private key.')  # noqa: E501
parser_serve.add_argument('--tls-pass', type=PathType(True, not_dir=True), help='Path to password to decrypt private key.')  # noqa: E501

parser_version = subparsers.add_parser('version', add_help=False, help='Show version information.')  # noqa: E501
parser_version.set_defaults(func=version_)
