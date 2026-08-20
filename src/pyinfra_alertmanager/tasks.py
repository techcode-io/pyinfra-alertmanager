from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path
from types import MappingProxyType
from typing import Final

from pyinfra.api import deploy
from pyinfra.context import host
from pyinfra.operations import files, server, systemd

from pyinfra_alertmanager.facts import BINARY_PATH, AlertmanagerVersion

UNIT_PATH: Final[str] = "/etc/systemd/system/alertmanager.service"
AMTOOL_BINARY_PATH: Final[str] = "/usr/local/bin/amtool"
CONFIG_DIR: Final[str] = "/etc/alertmanager"
CONFIG_PATH: Final[str] = f"{CONFIG_DIR}/config.yml"
STORAGE_DIR: Final[str] = "/var/lib/alertmanager"
DOWNLOAD_DIR: Final[str] = "/tmp/alertmanager"

DEFAULT_VERSION: Final[str] = "0.34.0"
DEFAULT_SYSTEM_USER: Final[str] = "alertmanager"
DEFAULT_SYSTEM_GROUP: Final[str] = "alertmanager"
DEFAULT_SERVICE_ARGS = MappingProxyType(
    {
        "web.listen-address": "127.0.0.1:9093",
        "config.file": CONFIG_PATH,
        "storage.path": STORAGE_DIR,
    }
)
DEFAULT_CONFIG_TEMPLATE: Final[str] = str(
    resources.files("pyinfra_alertmanager") / "templates" / "config.yml.j2"
)

_TEMPLATE: Final[Traversable] = (
    resources.files("pyinfra_alertmanager") / "templates" / "alertmanager.service.j2"
)


@deploy("Install alertmanager")
def install(
    version: str = DEFAULT_VERSION,
    system_user: str = DEFAULT_SYSTEM_USER,
    system_group: str = DEFAULT_SYSTEM_GROUP,
    service_args: dict | None = None,
    config_template: str | Path = DEFAULT_CONFIG_TEMPLATE,
    config_context: dict | None = None,
):
    server.group(
        name="Create alertmanager system group",
        group=system_group,
    )

    server.user(
        name="Create alertmanager system user",
        user=system_user,
        group=system_group,
        system=True,
        create_home=False,
        shell="/usr/sbin/nologin",
    )

    files.directory(
        name="Create alertmanager storage directory",
        path=STORAGE_DIR,
        user=system_user,
        group=system_group,
        mode=755,
        present=True,
    )

    files.directory(
        name="Create alertmanager configuration directory",
        path=CONFIG_DIR,
        user=system_user,
        group=system_group,
        mode=755,
        present=True,
    )

    config = files.template(
        name="Render alertmanager configuration",
        src=str(config_template),
        dest=CONFIG_PATH,
        user=system_user,
        group=system_group,
        **(config_context if config_context is not None else {}),
    )

    binary_changed = host.get_fact(AlertmanagerVersion) != version
    if binary_changed:
        files.directory(
            name="Prepare local download path",
            path=DOWNLOAD_DIR,
            mode=755,
            present=True,
        )

        archive = f"alertmanager-{version}.linux-amd64.tar.gz"

        files.download(
            name="Download alertmanager release binary",
            src=f"https://github.com/prometheus/alertmanager/releases/download/v{version}/{archive}",
            dest=f"{DOWNLOAD_DIR}/{archive}",
        )

        release_dir = f"/tmp/alertmanager-{version}.linux-amd64"

        # dest is "/tmp" (not DOWNLOAD_DIR): files.unarchive checks the dest
        # directory exists at operation-prepare time, which runs before the
        # "Prepare local download path" op above has actually created
        # DOWNLOAD_DIR on the remote. "/tmp" always exists already, so it
        # sidesteps that ordering issue.
        files.unarchive(
            name="Unarchive alertmanager release binary",
            src=f"{DOWNLOAD_DIR}/{archive}",
            dest="/tmp",
            remote_src=True,
        )

        files.move(
            name="Move alertmanager binary",
            src=f"{release_dir}/alertmanager",
            dest="/usr/local/bin",
        )

        files.move(
            name="Move amtool binary",
            src=f"{release_dir}/amtool",
            dest="/usr/local/bin",
        )

        files.directory(name="Clear download path", path=DOWNLOAD_DIR, present=False)
        files.directory(
            name="Clear extracted release directory", path=release_dir, present=False
        )

    unit = files.template(
        name="Copy alertmanager systemd unit file",
        src=str(_TEMPLATE),
        dest=UNIT_PATH,
        alertmanager_system_user=system_user,
        alertmanager_system_group=system_group,
        alertmanager_service_args=service_args
        if service_args is not None
        else DEFAULT_SERVICE_ARGS,
    )

    if unit.changed:
        systemd.daemon_reload(name="Reload systemd daemon")

    systemd.service(
        name="Restart and enable the alertmanager service",
        service="alertmanager.service",
        running=True,
        restarted=config.changed or binary_changed or unit.changed,
        enabled=True,
    )


@deploy("Uninstall alertmanager")
def uninstall(
    system_user: str = DEFAULT_SYSTEM_USER,
    system_group: str = DEFAULT_SYSTEM_GROUP,
):
    systemd.service(
        name="Stop and disable the alertmanager service",
        service="alertmanager.service",
        running=False,
        enabled=False,
    )

    unit = files.file(
        name="Remove alertmanager systemd unit file",
        path=UNIT_PATH,
        present=False,
    )

    if unit.changed:
        systemd.daemon_reload(name="Reload systemd daemon")

    files.file(
        name="Remove alertmanager binary",
        path=BINARY_PATH,
        present=False,
    )

    files.file(
        name="Remove amtool binary",
        path=AMTOOL_BINARY_PATH,
        present=False,
    )

    files.directory(
        name="Remove alertmanager configuration directory",
        path=CONFIG_DIR,
        present=False,
    )

    files.directory(
        name="Remove alertmanager storage directory",
        path=STORAGE_DIR,
        present=False,
    )

    server.user(
        name="Remove alertmanager system user",
        user=system_user,
        present=False,
    )

    server.group(
        name="Remove alertmanager system group",
        group=system_group,
        present=False,
    )
