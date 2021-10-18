#   encoding: utf-8
#   filename: error.py

from enum import IntEnum
from typing import Optional


class ErrorCode(IntEnum):
    """Enumeration ErrorCode defines common error codes for JSON RPC as well as
    error code specific to LSP.
    """

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
