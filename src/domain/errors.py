from enum import Enum


class ErrorCode(str, Enum):
    INPUT_REQUIRED = "INPUT_REQUIRED"
    INVALID_FILE_TYPE = "INVALID_FILE_TYPE"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    EMPTY_INPUT = "EMPTY_INPUT"
    PARSE_FAILED = "PARSE_FAILED"
    MODEL_NOT_READY = "MODEL_NOT_READY"
    BLACKLIST_INVALID = "BLACKLIST_INVALID"
    RECORD_NOT_FOUND = "RECORD_NOT_FOUND"
    DUPLICATE_INDICATOR = "DUPLICATE_INDICATOR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class DomainError(Exception):
    def __init__(self, code: ErrorCode, message: str, status_code: int):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code

