#   encoding: utf8
#   filename: lsp.py

import logging

from dataclasses import dataclass
from enum import IntEnum
from itertools import count
from json import dumps
from typing import Any, Callable, Dict, Optional, Union
from typing.io import IO

from .rpc import RequestReader, ResponseWriter


def make_error(request_id, error):
    return {
        'jsonrpc': '2.0',
        'id': request_id,
        'error': error,
    }


def make_response(request_id, result):
    return {
        'jsonrpc': '2.0',
        'id': request_id,
        'result': result,
    }


class ErrorCode(IntEnum):

    # JSON RPC specific error codes.

    ParseError = -32700

    InvalidRequest = -32600

    MethodNotFound = -32601

    InvalidParams = -32602

    InternalError = -32603

    # JSON RPC specific (backward compatible) error codes.

    ServerErrorStart = -32099

    ServerNotInitialized = -32002

    UnknownErrorCode = -32001

    # LSP specific error codes.

    ServerCancelled = -32802

    ContentModified = -32801

    RequestCancelled = -32800


class LSPError(Exception):

    def __init__(self, code: ErrorCode, desc: Optional[str] = None):
        self.code = code
        self.desc = desc


@dataclass
class Route:

    endpoint: str

    procedure: Callable[[Dict[str, Any]], Union[None, Dict[str, Any]]]

    notification: bool = True


class Router:

    def __init__(self):
        self.routes: Dict[str, Route] = {}

    def register(self, endpoint: str, procedure, notification: bool = True):
        self.routes[endpoint] = Route(endpoint, procedure, notification)

    def invoke(self, route, params):
        try:
            return route.procedure(params), None
        except Exception as e:
            logging.exception('failed to run route handler: %s', route.method)
            return None,  {
                'code': ErrorCode.InternalError,
                'message': 'internal error',
                'data': str(e),
            }

    def handle_notification(self, notif):
        method = notif['method']
        params = notif.get('params', {})

        if (route := self.routes.get(method)) is None:
            logging.warning('unsupported notification: %s', method)
            return

        self.invoke(route, params)

    def handle_request(self, req):
        request_id = req['id']
        method = req['method']
        params = req.get('params', {})

        if (route := self.routes.get(method)) is None:
            logging.warning('unsupported method to call: %s', method)
            return {
                'jsonrpc': '2.0',
                'id': request_id,
                'error': {
                    'code': ErrorCode.MethodNotFound,
                    'message': 'method not found',
                },
            }

        result, error = self.invoke(route, params)
        if error:
            return make_error(request_id, error)
        else:
            return make_response(request_id, result)

    def handle(self, obj):
        if (version := obj.get('jsonrpc')) != '2.0':
            logging.warning('unsupported json rpc version: %s', version)

        if obj.get('method') is None:
            logging.error('no method to call')
            return

        if (request_id := obj.get('id')) is None:
            return self.handle_notification(obj)
        elif isinstance(request_id, (str, int)):
            return self.handle_request(obj)
        else:
            logging.error('wrong type of request identifier')
            return


class Dispatcher:

    def __init__(self, fin: IO, fout: IO, pretty: bool = False):
        self.reader = RequestReader(fin)
        self.writer = ResponseWriter(fout)
        self.indent = 2 if pretty else None
        self.request_id = count()

    def write(self, res):
        content = dumps(res, ensure_ascii=False, indent=self.indent)
        content_bytes = content.encode('utf-8')
        self.writer.write(content_bytes)

    def request(self, method: str, *args):
        req = {
            'jsonrpc': '2.0',
            'id': next(self.request_id),
            'method': method,
            'params': args[0] if len(args) == 1 else args,
        }

        json = dumps(obj=req, ensure_ascii=False, indent=self.indent)
        body = json.encode('utf8')

        self.writer.write(body)


__all__ = (
    Dispatcher,
    ErrorCode,
    LSPError,
    Router,
)
