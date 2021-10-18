#   encoding: utf-8
#   filename: types.py

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

__all__ = (
    'Addr',
    'Proto',
)


class Proto(Enum):

    STDIO = 'stdio'

    TCP = 'tcp'

    TCP4 = 'tcp4'

    TCP6 = 'tcp6'

    UNIX = 'unix'

    def __str__(self):
        return self.name.lower()


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
