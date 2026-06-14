"""Pluggable secret storage seam.

Plan 2 ships PlaintextSecretBox (a no-op marker). A future DpapiSecretBox (or
an OS-keyring box) can be dropped in without touching SettingsStore or the
schema: stored values are prefix-marked so the format is self-describing and a
migration can re-wrap legacy values.
"""
from typing import Protocol, runtime_checkable


@runtime_checkable
class SecretBox(Protocol):
    def protect(self, plaintext: str) -> str:
        """Return the stored form of a secret."""
        ...

    def unprotect(self, stored: str) -> str:
        """Return the plaintext from a stored form."""
        ...


class PlaintextSecretBox:
    """Default seam: stores secrets in plaintext, prefix-marked.

    Same exposure as the previous plaintext .env on a single-user machine; the
    SQLite DB lives in %APPDATA% (gitignored) and never leaves the machine.
    """

    PREFIX = "plain:"

    def protect(self, plaintext: str) -> str:
        return f"{self.PREFIX}{plaintext}"

    def unprotect(self, stored: str) -> str:
        if stored.startswith(self.PREFIX):
            return stored[len(self.PREFIX):]
        return stored
