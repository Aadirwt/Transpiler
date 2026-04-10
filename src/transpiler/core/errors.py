class TranspilerError(Exception):
    """Base error for all compiler pipeline stages."""


class FrontendError(TranspilerError):
    """Raised when lexing/parsing frontend fails."""


class SemanticError(TranspilerError):
    """Raised when semantic validation fails."""


class TACGenerationError(TranspilerError):
    """Raised when TAC conversion fails."""


class BackendError(TranspilerError):
    """Raised when backend code emission fails."""
