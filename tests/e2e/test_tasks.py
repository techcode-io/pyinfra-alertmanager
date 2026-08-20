import platform
from typing import Final

from tests.e2e.conftest import podman_exec, run_pyinfra

# alertmanager binaries are only downloaded for linux-amd64 (matching upstream releases), so the
# service can only actually run to completion on an amd64 host; under emulation on other
# architectures (e.g. Podman on Apple Silicon) the Go runtime crashes for reasons unrelated to
# this library. Structural checks (files, user/group, systemd wiring) still run everywhere.
_IS_NATIVE_AMD64: Final[bool] = platform.machine() in ("x86_64", "amd64")


def assert_podman_exec(container: str, command: str, expected: int = 0) -> None:
    assert podman_exec(container, command).returncode == expected


def test_install_then_uninstall(systemd_container: str) -> None:
    install_result = run_pyinfra(systemd_container, "tasks_install.py")
    assert install_result.returncode == 0, install_result.stdout + install_result.stderr

    assert_podman_exec(systemd_container, "test -f /usr/local/bin/alertmanager")
    assert_podman_exec(systemd_container, "test -f /usr/local/bin/amtool")
    assert_podman_exec(systemd_container, "test -f /etc/alertmanager/config.yml")
    assert_podman_exec(systemd_container, "test -d /var/lib/alertmanager")
    assert_podman_exec(
        systemd_container, "test -f /etc/systemd/system/alertmanager.service"
    )
    assert_podman_exec(systemd_container, "id alertmanager")
    assert (
        podman_exec(
            systemd_container, "systemctl is-enabled alertmanager"
        ).stdout.strip()
        == "enabled"
    )

    if _IS_NATIVE_AMD64:
        assert (
            podman_exec(
                systemd_container, "systemctl is-active alertmanager"
            ).stdout.strip()
            == "active"
        )
        metrics = podman_exec(systemd_container, "curl -sf 127.0.0.1:9093/metrics")
        assert metrics.returncode == 0
        assert "alertmanager_build_info" in metrics.stdout

        # Reinstalling the same version should skip the download entirely: the
        # AlertmanagerVersion fact detects the binary already matches, so the download
        # operations are never even added to the operation graph. This only runs
        # natively (see _IS_NATIVE_AMD64 above): the version fact itself runs the
        # (amd64-only) binary, which also crashes under emulation.
        reinstall_result = run_pyinfra(systemd_container, "tasks_install.py")
        assert reinstall_result.returncode == 0, (
            reinstall_result.stdout + reinstall_result.stderr
        )
        assert "Download alertmanager release binary" not in reinstall_result.stdout

    uninstall_result = run_pyinfra(systemd_container, "tasks_uninstall.py")
    assert uninstall_result.returncode == 0, (
        uninstall_result.stdout + uninstall_result.stderr
    )

    assert_podman_exec(
        systemd_container, "test -f /usr/local/bin/alertmanager", expected=1
    )
    assert_podman_exec(systemd_container, "test -f /usr/local/bin/amtool", expected=1)
    assert_podman_exec(systemd_container, "test -d /etc/alertmanager", expected=1)
    assert_podman_exec(systemd_container, "test -d /var/lib/alertmanager", expected=1)
    assert_podman_exec(
        systemd_container,
        "test -f /etc/systemd/system/alertmanager.service",
        expected=1,
    )
    assert_podman_exec(systemd_container, "id alertmanager", expected=1)
