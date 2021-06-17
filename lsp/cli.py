#   encoding: utf8
#   filename: cli.py

import click
import logging

from json import loads, dumps
from os import getppid
from socket import AF_INET, SOCK_STREAM, SO_REUSEADDR, SOL_SOCKET, socket
from string import ascii_letters

from .lsp import Dispatcher, ErrorCode, LSPError, Router
from .rpc import make_transport_pair
from .version import version


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

    @staticmethod
    def did_change(params):
        logging.info('handle did_change() notification')

    @staticmethod
    def did_close(params):
        logging.info('handle did_close() notification')

    def completion(params):
        logging.info('handle completion() procedure call')
        return [
            {'label': 'he'},
            {'label': 'hello'},
            {'label': 'world'},
            {'label': 'London'},
            {'label': 'is'},
            {'label': 'the'},
            {'label': 'capital'},
            {'label': 'of'},
            {'label': 'Great'},
            {'label': 'Britain'},
        ]


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
            logging.info('write back response or error')
            content = dumps(res, ensure_ascii=False, indent=2)
            print(content)
            writer.write(content.encode(charset))

    logging.info('connection is closed for %s:%d', *addr)


@click.group()
def main():
    logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s',
                        level=logging.INFO)


@main.command()
@click.argument('addr', default='127.0.0.1:8080')
def connect(addr: str):
    if len(splits := addr.rsplit(':', 1)) != 2:
        logging.error('wrong address format: %s', addr)
        return
    else:
        host = splits[0]
        port = int(splits[1])

    logging.info('connecting to %s:%d', host, port)
    with socket(AF_INET, SOCK_STREAM) as sock:
        sock.connect((host, port))
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


@main.command()
@click.option('-h', '--host', default='127.0.0.1')
@click.option('-p', '--port', default=8080)
def serve(host: str, port: int):
    with socket(AF_INET, SOCK_STREAM) as sock:
        sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        sock.bind((host, port))
        sock.listen(1)
        while True:
            serve_client(*sock.accept())
