#   encoding: utf8
#   filename: corpus.py

from typing import Dict


class Document:

    def __init__(self, content: str):
        self.content = content
        self.version = 0

    @property
    def text(self) -> str:
        return self.content

    def set(self, content: str):
        self.content = content


class Corpus:

    def __init__(self):
        self.docs: Dict[str, Document] = {}

    def __str__(self) -> str:
        return f'Corpus(nodocs={len(self.docs)})'

    def get(self, uri: str) -> Document:
        return self.docs[uri]

    def open(self, uri: str, text: str):
        self.docs[uri] = Document(text)

    def set(self, uri: str, text: str):
        self.docs[uri].set(text)
