#   encoding: utf8
#   filename: rpc.py

from dataclasses import dataclass
from socket import socket
from typing import Optional, Tuple
from typing.io import IO


class ParsingError(Exception):

    pass


@dataclass
class Request:

    content_length: int

    content_type: Optional[bytes]

    content: bytes


class RequestReader:

    def __init__(self, file: IO):
        self.file = file
        self.stop = False
        self.req: Request
        self.err: ParsingError

    def __iter__(self):
        return self

    def __next__(self) -> Request:
        if req := self.read():
            return req
        else:
            raise StopIteration

    def read(self) -> Optional[Request]:
        try:
            self.req = Request(0, None, b'')
            self._read_headers()
            self._read_content()
            return self.req
        except StopIteration:
            self.stop = True
        except ParsingError as e:
            self.err = e

    def _read_content(self):
        if self.req.content_length == 0:
            return

        self.req.content = self.file.read(self.req.content_length)

        if len(self.req.content) != self.req.content_length:
            raise ParsingError('failed to read request content')

    def _read_headers(self):
        while (line := self._read_until_eol()):
            split = line.decode('ascii').split(':', 1)
            if len(split) != 2:
                raise ParsingError('there is no colon in header')

            key, val = split
            key = key.lower()

            if key == 'content-type':
                self.req.content_type = val.strip()
            elif key == 'content-length':
                self.req.content_length = int(val)

    def _read_until_eol(self):
        if len(line := self.file.read(2)) == 0:
            raise StopIteration
        elif len(line) != 2:
            raise ParsingError('request header is corrupted')

        while line[-2:] != b'\r\n':
            if byte := self.file.read(1):
                line += byte
            else:
                raise ParsingError('failed to read request header')

        return line[:-2]


class ResponseWriter:

    def __init__(self, file: IO):
        self.file = file

    def write(self, content: bytes):
        self._write_headers([
            ('Content-Length', str(len(content))),
        ])
        self.file.write(content)
        self.file.flush()

    def _write_headers(self, headers):
        for key, val in headers:
            self._write_header(key, val)
        self.file.write(b'\r\n')

    def _write_header(self, name: str, value: str):
        self.file.write(name.encode('ascii'))
        self.file.write(b': ')
        self.file.write(value.encode('ascii'))
        self.file.write(b'\r\n')


def make_transport_pair(sock: socket) -> Tuple[RequestReader, ResponseWriter]:
    file = sock.makefile('rwb')
    reader = RequestReader(file)
    writer = ResponseWriter(file)
    return reader, writer


__all__ = (
    ParsingError,
    Request,
    RequestReader,
    ResponseWriter,
    make_transport_pair,
)
