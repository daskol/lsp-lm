#   encoding: utf8
#   filename: lsp.py
#
# TODO: Support request (and notification) direction.

import logging

from dataclasses import dataclass
from enum import IntEnum
from functools import wraps
from inspect import ismethod, getmembers, getmro
from itertools import count
from json import dumps
from os.path import join
from typing import Any, Callable, Dict, Optional, Union
from typing.io import IO

from .rpc import PacketReader, PacketWriter


HandlerOrString = Union[Callable[..., Any], Optional[str]]


def extract_routing_table(obj):
    routes = {}
    for name, func in getmembers(obj, ishandler):
        routes[func.endpoint] = func
    return routes


def ishandler(obj) -> bool:
    return ismethod(obj) and hasattr(obj, 'endpoint')


def to_camel_case(name: str) -> str:
    capitalize = False
    result = name[0].lower()
    for char in name[1:]:
        if char == '_':
            capitalize = True
        elif capitalize:
            capitalize = False
            result += char.upper()
        else:
            result += char
    return result


def protocol(cls_or_scope: Union['Base', str], suffix: str = 'Protocol'):
    """Class decorator protocol is aimed to collect and populate functions
    which are suppose to handle requests and notifications from a side. It puts
    all methods to the same root (or scope) if no root was specified.

    >>> @protocol
    ... class ExampleProtocol:
    ...     pass
    """
    # Switch between simple decorator and parametrized decorator.
    if type(cls_or_scope) != str:
        cls, scope = cls_or_scope, None
    else:
        cls, scope = None, cls_or_scope

    def decorator(cls):
        # Infer root from class name.
        if cls.__name__.endswith(suffix):
            class_name = cls.__name__[:-8]
        else:
            class_name = cls.__name__

        class_name = to_camel_case(class_name)

        for name, func in cls.__dict__.items():
            # No metadata for routing.
            if not hasattr(func, 'endpoint'):
                continue

            # Adjust scope value.
            if scope is not None:
                func.scope = scope
            elif not func.scope:
                func.scope = class_name

            func.endpoint = join(func.scope, func.name)

        return cls

    return decorator(cls) if cls else decorator


def handler(func_or_name: HandlerOrString,
            scope: Optional[str] = None,
            reqres: bool = True):
    """Method decorator handlers wraps a class method and append meta
    information (like RPC method name or scope).

    >>> @handler
    ... def example_handler(*args, **kwargs):
    ...     pass
    """
    # Switch between simple and parametrized decorator.
    if callable(func_or_name):
        func, name = func_or_name, None
    else:
        func, name = None, func_or_name

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        wrapper.reqres = reqres
        wrapper.scope = scope
        wrapper.name = name or to_camel_case(func.__name__)
        wrapper.endpoint = None
        return wrapper

    return decorator(func) if func else decorator


def request(func_or_name: HandlerOrString,
            scope: Optional[str] = None):
    """Method decorator request is specialization of decorator handler in case
    if resulting value is expected.
    """
    return handler(func_or_name, scope, True)


def notification(func_or_name: HandlerOrString,
                 scope: Optional[str] = None):
    """Method decorator notification is specialization of decorator handler in
    case if no resulting value is expected.
    """
    return handler(func_or_name, scope, False)


class Base:
    """Class Base enables automatic routings machinery to register handler for
    a remote procedure call.
    """

    PROPERTIES = ('reqres', 'scope', 'name', 'endpoint')

    def __init_subclass__(cls, *args, **kwargs):
        # Get parents as Method Resolution Order (MRO). Assume that there is
        # not rare user-defined classes which brokes the order.
        mro = getmro(cls)
        parents = mro[1:-1]

        def find_attr(name):
            for parent in parents:
                if (proto := getattr(parent, name, None)):
                    return proto

        def dup_attrs(*, src, dst):
            for prop in Base.PROPERTIES:
                value = getattr(src, prop)
                setattr(dst, prop, value)

        # Clone attributes to override methods.
        for name, attr in cls.__dict__.items():
            # Skip all attributes prefixed with underscore.
            if name.startswith('_'):
                continue

            # Check whether an item has routing information.
            if hasattr(attr, 'endpoint'):
                continue

            # Copy attributes if we find overriden method.
            if proto := find_attr(name):
                dup_attrs(src=proto, dst=attr)


@protocol(cls_or_scope='')
class GeneralProtocol(Base):

    @request
    def initialize(self, *args, **kwargs):
        raise NotImplementedError

    @notification
    def initialized(self, *args, **kwargs):
        raise NotImplementedError

    @notification
    def exit(self, **kwargs):
        raise NotImplementedError

    @notification
    def log_trace(self, **kwargs):
        raise NotImplementedError

    @notification
    def set_trace(self, **kwargs):
        raise NotImplementedError

    @request
    def shutdown(self, **kwargs):
        raise NotImplementedError


@protocol
class ClientProtocol(Base):

    @request
    def register_capability(self, *args, **kwargs):
        raise NotImplementedError

    @request
    def unregister_capability(self, *args, **kwargs):
        raise NotImplementedError


@protocol
class DiagnosticsProtocol(Base):

    @notification
    def publish_diagnostics(self, **kwargs):
        raise NotImplementedError


@protocol
class TelemetryProtocol:

    @notification
    def event(self, **kwargs):
        raise NotImplementedError


@protocol
class TextDocumentProtocol:

    @request
    def completion(self, *args, **kwargs):
        raise NotImplementedError

    @notification
    def did_change(self, *args, **kwargs):
        raise NotImplementedError

    @notification
    def did_close(self, *args, **kwargs):
        raise NotImplementedError

    @notification
    def did_open(self, *args, **kwargs):
        raise NotImplementedError

    @notification
    def did_save(self, *args, **kwargs):
        raise NotImplementedError

    @request
    def hover(self, *args, **kwargs):
        raise NotImplementedError

    @notification
    def will_save(self, *args, **kwargs):
        raise NotImplementedError

    @notification
    def will_save_wait_until(self, *args, **kwargs):
        raise NotImplementedError


@protocol
class WindowProtocol(Base):

    @notification
    def log_message(self, **kwargs):
        raise NotImplementedError

    @request
    def show_document(self, **kwargs):
        raise NotImplementedError

    @notification
    def show_message(self, **kwargs):
        raise NotImplementedError

    @request
    def show_message_request(self, **kwargs):
        raise NotImplementedError


@protocol
class WorkspaceProtocol(Base):

    @request
    def apply_edit(self, *args, **kwargs):
        raise NotImplementedError

    @request
    def configuration(self, *args, **kwargs):
        raise NotImplementedError

    @notification
    def did_change_configuration(self, *args, **kwargs):
        raise NotImplementedError

    @notification
    def did_change_watched_files(self, *args, **kwargs):
        raise NotImplementedError

    @notification
    def did_change_workspace_folders(self, *args, **kwargs):
        raise NotImplementedError

    @notification
    def did_create_files(self, *args, **kwargs):
        raise NotImplementedError

    @notification
    def did_delete_files(self, *args, **kwargs):
        raise NotImplementedError

    @notification
    def did_rename_files(self, *args, **kwargs):
        raise NotImplementedError

    @request
    def execute_command(self, *args, **kwargs):
        raise NotImplementedError

    @request
    def symbol(self, *args, **kwargs):
        raise NotImplementedError

    @notification
    def will_create_files(self, *args, **kwargs):
        raise NotImplementedError

    @notification
    def will_rename_files(self, *args, **kwargs):
        raise NotImplementedError

    @notification
    def will_delete_files(self, *args, **kwargs):
        raise NotImplementedError

    @request
    def workspace_folders(self, *args, **kwargs):
        raise NotImplementedError


class LanguageServerProtocol(GeneralProtocol,
                             ClientProtocol,
                             DiagnosticsProtocol,
                             TelemetryProtocol,
                             TextDocumentProtocol,
                             WindowProtocol,
                             WorkspaceProtocol):
    """Class LanguageServerProtocol combines all parts of LSP specification
    togeter.
    """


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

    func: Callable[[Dict[str, Any]], Union[None, Dict[str, Any]]]

    reqres: bool = True


class Router:

    def __init__(self):
        self.routes: Dict[str, Route] = {}

    def invoke(self, method, *args, **kwargs):
        if not (route := self.routes.get(method)):
            raise ValueError(f'Method not found: {method}.')

        try:
            return route.func(*args, **kwargs)
        except NotImplementedError:
            logging.error('method %s is not implemented', method)
            raise
        except Exception:
            logging.exception('failed to invoke method %s', method)
            raise

    def register(self, method_or_protocol, handler=None):
        if handler:
            # If handler is specified then register it by its name.
            return self.register_method(method_or_protocol, handler)
        else:
            # If handler is not specified then we should register methods of an
            # object.
            return self.register_protocol(method_or_protocol)

    def register_method(self, method, handler):
        if method in self.routes:
            logging.warning('duplicated route %s: replacing', method)
        self.routes[method] = Route(method, handler, handler.reqres)

    def register_protocol(self, protocol: Base):
        for name, func in getmembers(protocol, ishandler):
            self.register(func.endpoint, func)

    def unregister(self, method):
        if method not in self.routes:
            logging.warning('no route %s in table: skipping', method)
        self.routes.pop(method, None)


class Dispatcher:

    def __init__(self, fin: IO, fout: IO, pretty: bool = False):
        self.reader = PacketReader(fin)
        self.writer = PacketWriter(fout)
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
    Base,
    Dispatcher,
    ErrorCode,
    LSPError,
    LanguageServerProtocol,
    Router,
    notification,
    protocol,
    request,
)
