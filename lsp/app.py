#   encoding: utf-8
#   filename: app.py

import logging

from os import getppid
from string import ascii_letters

from .completion import get_completor
from .corpus import Corpus
from .syncio.lsp import ErrorCode, LanguageServerProtocol, LSPError
from .version import version


__all__ = (
    'Protocol',
)


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
