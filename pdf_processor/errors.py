"""
PDF Processor Error Types and Result Handling.

This module defines custom exceptions and result types for the PDF processor.
Following the Result pattern from Rust for better error handling.
"""

from dataclasses import dataclass
from typing import Generic, TypeVar, Union
from pathlib import Path


class PDFProcessorError(Exception):
    """Base exception for all PDF processor errors."""
    pass


class FileError(PDFProcessorError):
    """Errors related to file operations."""
    def __init__(self, path: Union[str, Path], message: str):
        self.path = Path(path)
        self.message = message
        super().__init__(f"{message}: {self.path}")


class PDFError(PDFProcessorError):
    """Errors related to PDF processing."""
    pass


class ExternalToolError(PDFProcessorError):
    """Errors related to external tool execution."""
    def __init__(self, tool: str, message: str, exit_code: int = None):
        self.tool = tool
        self.exit_code = exit_code
        self.message = message
        msg = f"{tool} error: {message}"
        if exit_code is not None:
            msg += f" (exit code: {exit_code})"
        super().__init__(msg)


class ValidationError(PDFProcessorError):
    """Errors related to input validation."""
    pass


T = TypeVar('T')
E = TypeVar('E', bound=Exception)


@dataclass
class Result(Generic[T, E]):
    """
    A Result type inspired by Rust's Result.
    
    Attributes:
        value: The success value if successful
        error: The error if failed
        is_ok: Whether the result is successful
    """
    _value: T | None
    _error: E | None
    is_ok: bool

    @staticmethod
    def Ok(value: T) -> 'Result[T, E]':
        """Create a successful result."""
        return Result(value, None, True)

    @staticmethod
    def Err(error: E) -> 'Result[T, E]':
        """Create a failed result."""
        return Result(None, error, False)

    @property
    def value(self) -> T:
        """Get the success value, raising the error if failed."""
        if not self.is_ok:
            raise self._error
        return self._value

    @property
    def error(self) -> E:
        """Get the error, raising ValueError if successful."""
        if self.is_ok:
            raise ValueError("Result is Ok")
        return self._error

    def unwrap(self) -> T:
        """Get the success value or raise the error."""
        return self.value

    def unwrap_or(self, default: T) -> T:
        """Get the success value or return a default."""
        return self.value if self.is_ok else default

    def map(self, f: callable) -> 'Result[T, E]':
        """Apply a function to the success value."""
        if self.is_ok:
            return Result.Ok(f(self.value))
        return self
