from enum import Enum


class ErrorCode(str, Enum):
    INPUT_REQUIRED = "INPUT_REQUIRED"
    INVALID_FILE_TYPE = "INVALID_FILE_TYPE"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    EMPTY_INPUT = "EMPTY_INPUT"
    # D-001 的严格三选一方案尚未决策，当前仅保留错误码，不启用行为。
    INPUT_CONFLICT = "INPUT_CONFLICT"
    PARSE_FAILED = "PARSE_FAILED"
    MODEL_NOT_READY = "MODEL_NOT_READY"
    BLACKLIST_INVALID = "BLACKLIST_INVALID"
    RECORD_NOT_FOUND = "RECORD_NOT_FOUND"
    DUPLICATE_INDICATOR = "DUPLICATE_INDICATOR"
    NETWORK_ACCESS_NOT_SUPPORTED = "NETWORK_ACCESS_NOT_SUPPORTED"
    INVALID_PAGINATION = "INVALID_PAGINATION"
    INVALID_FEEDBACK = "INVALID_FEEDBACK"
    INVALID_DATE_RANGE = "INVALID_DATE_RANGE"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class DomainError(Exception):
    def __init__(self, code: ErrorCode, message: str, status_code: int):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
