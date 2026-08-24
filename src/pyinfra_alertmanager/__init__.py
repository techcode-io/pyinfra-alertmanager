from pyinfra_alertmanager.facts import AlertManagerVersion
from pyinfra_alertmanager.tasks import (
    DEFAULT_CONFIG_TEMPLATE,
    DEFAULT_SERVICE_ARGS,
    DEFAULT_SYSTEM_GROUP,
    DEFAULT_SYSTEM_USER,
    DEFAULT_VERSION,
    install,
    uninstall,
)

__all__ = [
    "DEFAULT_CONFIG_TEMPLATE",
    "DEFAULT_SERVICE_ARGS",
    "DEFAULT_SYSTEM_GROUP",
    "DEFAULT_SYSTEM_USER",
    "DEFAULT_VERSION",
    "AlertManagerVersion",
    "install",
    "uninstall",
]
