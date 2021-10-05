#   encoding: utf8
#   filename: rpc.py
#
# TODO: Rename Packet to Frame.
# TODO: Rename req and res to frame.
# TODO: Rename content to payload?
# TODO: Parse content type "in-place".

from dataclasses import dataclass
from typing import IO, Optional


class PacketError(Exception):
    """Class PacketError inherited from Exception class. The type and its
    derived subtypes represents any error occurs during frame processing.
    """


@dataclass
class Packet:
    """Class Packet represents a messaging unit. It consists of headers like
    content length and content type as well as content itself.
    """

    content_length: int

    content_type: Optional[bytes]

    content: bytes


class PacketReader:

    def __init__(self, fin: IO):
        self.fin = fin
        self.stop = False
        self.req: Packet
        self.err: PacketError

    def __iter__(self):
        return self

    def __next__(self) -> Packet:
        if req := self.read():
            return req
        else:
            raise StopIteration

    def read(self) -> Optional[Packet]:
        try:
            self.req = Packet(0, None, b'')
            self._read_headers()
            self._read_content()
            return self.req
        except StopIteration:
            self.stop = True
            return None
        except PacketError as e:
            self.err = e
            return None

    def _read_content(self):
        if self.req.content_length == 0:
            return

        self.req.content = self.fin.read(self.req.content_length)

        if len(self.req.content) != self.req.content_length:
            raise PacketError('failed to read request content')

    def _read_headers(self):
        while (line := self._read_until_eol()):
            split = line.decode('ascii').split(':', 1)
            if len(split) != 2:
                raise PacketError('there is no colon in header')

            key, val = split
            key = key.lower()

            if key == 'content-type':
                self.req.content_type = val.strip()
            elif key == 'content-length':
                self.req.content_length = int(val)

    def _read_until_eol(self):
        if len(line := self.fin.read(2)) == 0:
            raise StopIteration
        elif len(line) != 2:
            raise PacketError('request header is corrupted')

        while line[-2:] != b'\r\n':
            if byte := self.fin.read(1):
                line += byte
            else:
                raise PacketError('failed to read request header')

        return line[:-2]


class PacketWriter:

    def __init__(self, fout: IO):
        self.fout = fout

    def write(self, content: bytes):
        self._write_headers([
            ('Content-Length', str(len(content))),
        ])
        self.fout.write(content)
        self.fout.flush()

    def _write_headers(self, headers):
        for key, val in headers:
            self._write_header(key, val)
        self.fout.write(b'\r\n')

    def _write_header(self, name: str, value: str):
        self.fout.write(name.encode('ascii'))
        self.fout.write(b': ')
        self.fout.write(value.encode('ascii'))
        self.fout.write(b'\r\n')


__all__ = (
    'Packet',
    'PacketError',
    'PacketReader',
    'PacketWriter',
)
