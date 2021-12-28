#   encoding: utf8
#   filename: corpus.py

from typing import Dict, Optional

__all__ = ('Document', 'Corpus')


def locate(text: str, line: int, char: int) -> Optional[int]:
    """Function locate find position in text by line and character from the
    line beginning.
    """
    pos = 0

    # Find line first.
    cur_line = 0
    while pos < len(text) and cur_line != line:
        pos = text.index('\n', pos) + 1
        cur_line += 1

    # Find character in the line.
    for cur_char, c in enumerate(text[pos:pos + char]):
        pos += 1
        if c in '\r\n':
            return None
    if cur_char + 1 != char:
        return None

    return pos


class Document:

    def __init__(self, content: str):
        self.content = content
        self.version = 0

    @property
    def text(self) -> str:
        return self.content

    def set(self, content: str):
        self.content = content

    def window(self, line: int, char: int, window: int = 128):
        """Method window returns text preceding to and succeeding cursor
        position at line:char. Length of prefix and suffix are bounded.
        """
        pos = locate(self.content, line, char)
        begin, end = max(0, pos - window), min(pos + window, len(self.content))
        prefix = self.content[begin:pos]
        suffix = self.content[pos + 1:end]
        return prefix, suffix


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
