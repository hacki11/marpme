"""Application errors whose messages are safe to show to users."""


class MarpmeError(Exception):
    """Base class for expected failures."""


class RepositoryNotFoundError(MarpmeError):
    pass


class GitMissingError(MarpmeError):
    pass


class InvalidRepositoryStateError(MarpmeError):
    pass


class NotInitializedError(MarpmeError):
    pass


class InvalidDeckNameError(MarpmeError):
    pass


class DeckExistsError(MarpmeError):
    pass


class InvalidConfigError(MarpmeError):
    pass


class TemplateUnavailableError(MarpmeError):
    pass


class CopierFailureError(MarpmeError):
    pass


class InstallationNotOwnedError(MarpmeError):
    pass


class ReleaseError(MarpmeError):
    pass
