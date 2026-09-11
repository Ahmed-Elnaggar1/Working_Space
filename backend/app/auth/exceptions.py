class AuthError(Exception):
    """Base exception for authentication application errors."""

    pass

class InvalidCredentialsError(AuthError):
    """Raised when email or password verification fails."""
    pass


class UserAlreadyExistsError(AuthError):
    """Raised during registration if the email is already in use."""
    pass


class TokenExpiredError(AuthError):
    """Raised when an access or refresh token has expired."""
    pass


class TokenReuseDetectedError(AuthError):
    """Raised when a revoked/replayed refresh token is used."""
    pass


class InvalidTokenError(AuthError):
    """Raised when token signature, claims, or structure are malformed."""
    pass


class UserNotFoundError(AuthError):
    """Raised when an authenticated user no longer exists."""

    pass