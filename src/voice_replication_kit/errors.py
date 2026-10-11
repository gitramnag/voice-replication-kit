"""Public command failures that are safe to classify without revealing data."""


class UserValidationError(ValueError):
    """An expected validation or policy failure caused by supplied input."""


class PrivateInputError(FileNotFoundError, UserValidationError):
    """A required private input is absent or unreadable."""


class ImmutableOutputError(FileExistsError, UserValidationError):
    """An immutable private output would be replaced."""
