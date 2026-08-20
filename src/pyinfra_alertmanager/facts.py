import re
from typing import Final

from pyinfra.api import FactBase

BINARY_PATH: Final[str] = "/usr/local/bin/alertmanager"

_VERSION_MATCHER: Final[re.Pattern] = re.compile(
    r"alertmanager,\s+version\s+(?P<version>\S+)"
)


class AlertmanagerVersion(FactBase):
    """
    Returns the currently installed alertmanager version (eg ``0.30.1``), or ``None`` if
    alertmanager is not installed.
    """

    def command(self) -> str:
        return f"{BINARY_PATH} --version 2>&1"

    def requires_command(self) -> str:
        return BINARY_PATH

    def process(self, output) -> str | None:
        match = _VERSION_MATCHER.search("\n".join(output))
        return match.group("version") if match else None
