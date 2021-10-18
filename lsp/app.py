#   encoding: utf-8
#   filename: app.py

import logging

from io import StringIO
from json import dump
from os import getppid
from string import ascii_letters

from .completion import AbstractCompletor, make_completor_loader
from .corpus import Corpus
from .lsp import Addr, ErrorCode, LSPError
from .lsp.syncio import LanguageServerProtocol, Server
from .version import version


__all__ = (
    'Application',
)


def format_initialize_params(params):
    sio = StringIO()
    print('Parent PID:            ', params.get('processId'), file=sio)
    if (info := params.get('clientInfo', {})):
        name = info.get('name', '')
        version = info.get('version')
        value = f'{name}/{version}' if version else name
        print('Client info:           ', value, file=sio)
    print('Locale:                ', params.get('locale', ''), file=sio)
    rootPath = params.get('rootPath')
    rootUri = params.get('rootUri', rootPath)
    print('Root URI:              ', rootUri, file=sio)
    folders = params.get('WorkspaceFolder', [])
    print('Workspace Folders:', file=sio)
    for i, folder in enumerate(folders, 1):
        uri = folder.get('uri')
        name = folder.get('name')
        print(f'[{i}:2d] {name} -> {uri}', file=sio)
    print('Initialization Options:', end=' ', file=sio)
    if (opts := params.get('initializationOptions')) is None:
        print(file=sio)
    else:
        dump(opts, sio)
        print(file=sio)
    tracing = params.get('trace', 'off')
    print('Tracing:               ', tracing, file=sio)
    print('Client Capabilities:', file=sio)
    caps = params.get('capabilities', {})
    print('[General]', end=' ', file=sio)
    dump(caps.get('general'), sio)
    print(file=sio)
    print('[Document]', end=' ', file=sio)
    dump(caps.get('textDocument'), sio)
    print(file=sio)
    print('[Workspace]', end=' ', file=sio)
    dump(caps.get('workspace'), sio)
    print(file=sio)
    print('[Experimental]', end=' ', file=sio)
    dump(caps.get('experimental'), sio)
    print(file=sio)
    return sio.getvalue()


class CompletionProtocol(LanguageServerProtocol):
    """Class CompletionProtocol implements minimal values part of LSP to
    provide completion. It loads models and initialises document manager on
    initialize() request and maintains its internal state.
    """

    def __init__(self, completor_loader, session):
        super().__init__()

        self.completor: AbstractCompletor
        self.completor_loader = completor_loader
        self.session = session

    def watch_pid(self, pid: int):
        logging.info('watch for process with pid %d', pid)

    def initialize(self, params):
        logging.info('handle initialize() procedure call')
        logging.info('human-readable initialize params are below\n%s',
                     format_initialize_params(params))

        logging.info('instantiate corpus manager')
        self.corpus = Corpus()

        logging.info('instantiate completor')
        try:
            self.completor = self.completor_loader.load()
        except Exception:
            logging.exception('failed to load completor')
            raise LSPError(ErrorCode.InternalError, 'completor loading error')

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
                    'allCommitCharacters': list(' !?:;,.'),
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


class Application:
    """Class Application is a high-level entry point which is the root of
    ownership tree for any runtime resource.
    """

    def __init__(self, addr: Addr, tls_context, ir_opts, lm_opts):
        self.ir_opts = ir_opts
        self.lm_opts = lm_opts
        self.loader = make_completor_loader(self.lm_opts)
        self.server = Server(addr, self.make_protocol, tls_context)

    def make_protocol(self, *args, **kwargs):
        return CompletionProtocol(self.loader, *args, **kwargs)

    def run(self):
        return self.server.start()
