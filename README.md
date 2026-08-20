<h1 align="center">Pyinfra Alertmanager</h1>

<p align="center">
  <i align="center">Install and uninstall Prometheus alertmanager with pyinfra.</i>
</p>

<h4 align="center">
  <a href="https://github.com/techcode-io/pyinfra-alertmanager/actions/workflows/ci.yml">
    <img src="https://img.shields.io/github/actions/workflow/status/techcode-io/pyinfra-alertmanager/ci.yml?branch=main&label=ci&style=flat-square" alt="continuous integration" style="height: 20px;">
  </a>
  <a href="https://github.com/techcode-io/pyinfra-alertmanager/graphs/contributors">
    <img src="https://img.shields.io/github/contributors-anon/techcode-io/pyinfra-alertmanager?color=yellow&style=flat-square" alt="contributors" style="height: 20px;">
  </a>
  <a href="https://opensource.org/licenses/Apache-2.0">
    <img src="https://img.shields.io/badge/apache%202.0-blue.svg?style=flat-square&label=license" alt="license" style="height: 20px;">
  </a>
  <br>
</h4>

- [Source](https://github.com/techcode-io/pyinfra-alertmanager)
- [Issues](https://github.com/techcode-io/pyinfra-alertmanager/issues)
- [Contact](mailto:adrien.mannocci@gmail.com)
- [Maintained by techcode.io](https://techcode.io)

## :package: Prerequisites

- [uv](https://docs.astral.sh/uv/) for development.
- [Podman](https://podman.io/docs) to run the end-to-end tests.

## :sparkles: Features

- Idempotent `install()`: system user/group, storage/config directories, alerting config, binary,
  systemd unit and running service in one call.
- Skips re-downloading the binary when the installed version already matches, using a pyinfra
  fact.
- `uninstall()` reverses everything: service, unit file, binaries, config/storage directories,
  user and group.
- Deploy functions only, no CLI: import it into any [pyinfra](https://pyinfra.com) project.

## :dart: Motivation

- We needed to manage `alertmanager` the same way across every server we operate.
- The solution should be reusable across pyinfra projects instead of copy-pasted between deploy
  scripts.
- The solution should be idempotent and skip work that has already been done.

## :hammer: Workflow

### Setup

The following steps will ensure your project is cloned properly.

1. Clone repository:
   ```shell
   git clone https://github.com/techcode-io/pyinfra-alertmanager
   cd pyinfra-alertmanager
   ```
2. Install dependencies and setup environment:
   ```shell
   uv sync
   uv run poe env:configure
   ```

### Lint

- To lint you have to use the workflow.

```bash
uv run poe lint
```

### Format

- To format you have to use the workflow.

```bash
uv run poe fmt
```

- It will format the project code using `ruff`.

### Test

- To test you have to use the workflow.
- Tests are based on `pytest` and run the deploy functions against a real systemd container via
  Podman.

```bash
uv run poe test
```

## 📖 Usage

### How it works

- `install()` and `uninstall()` are [pyinfra](https://pyinfra.com) deploy functions, wrapped with
  `@deploy(...)` from `pyinfra.api`.
- They take explicit keyword arguments instead of reading `host.data`, so any inventory can use
  them.
- `install()` creates the system user/group, the storage (`/var/lib/alertmanager`) and config
  (`/etc/alertmanager`) directories, renders the alerting configuration from a Jinja2 template,
  downloads the `alertmanager`/`amtool` release binaries, renders the systemd unit from a bundled
  template, then enables and starts the service.
- Before downloading, it checks the currently installed version using a pyinfra fact and skips the
  download entirely if it already matches.
- `uninstall()` stops and disables the service, then removes the unit file, binaries, config and
  storage directories, user and group.

### How to install alertmanager

- This project isn't published to PyPI yet, so add it as a git dependency pinned to a commit.
- Find the commit you want to pin to on
  the [commit history](https://github.com/techcode-io/pyinfra-alertmanager/commits/main), then add
  it to your pyinfra project.

```bash
uv add git+https://github.com/techcode-io/pyinfra-alertmanager --rev <commit-sha>
# or
pip install git+https://github.com/techcode-io/pyinfra-alertmanager@<commit-sha>
```

- This adds the following to your `pyproject.toml`, which you can also edit directly.

```toml
[project]
dependencies = ["pyinfra-alertmanager"]

[tool.uv.sources]
pyinfra-alertmanager = { git = "https://github.com/techcode-io/pyinfra-alertmanager", rev = "<commit-sha>" }
```

- Then call `install()` from a deploy script.

```python
from pyinfra_alertmanager import install

install()
```

### How to uninstall alertmanager

- Call `uninstall()` from a deploy script.

```python
from pyinfra_alertmanager import uninstall

uninstall()
```

### How to customize the install

- All functions accept keyword arguments; defaults match the upstream alertmanager release layout
  for `linux-amd64`.
- `config_template` is the path to a local Jinja2 template rendered to
  `/etc/alertmanager/config.yml` (via pyinfra's `files.template`); `config_context` supplies the
  variables used inside it. The bundled `DEFAULT_CONFIG_TEMPLATE` is a minimal valid config with a
  no-op `default` receiver, so pass your own template (and context) to actually deliver alerts —
  this lets you use Jinja conditionals, loops, or secrets pulled from your own vault/templating
  setup, same as the systemd unit is rendered.

```python
from pyinfra_alertmanager import DEFAULT_SERVICE_ARGS, install

install(
    version="0.34.0",
    system_user="alertmanager",
    system_group="alertmanager",
    service_args={
        **DEFAULT_SERVICE_ARGS,
        "web.listen-address": "0.0.0.0:9093",
    },
    config_template="files/alertmanager/config.yml.j2",
    config_context={
        "discord_webhook_url": "https://discord.com/api/webhooks/...",
    },
)
```

- `files/alertmanager/config.yml.j2` (relative to your deploy script, like any other pyinfra
  template):

```yaml
route:
  receiver: discord

receivers:
  - name: discord
    discord_configs:
      - webhook_url: {{ discord_webhook_url }}
```

| Function               | Parameter          | Default                    | Description                                                                |
|------------------------|---------------------|-----------------------------|-----------------------------------------------------------------------------|
| `install`, `uninstall` | `system_user`       | `alertmanager`              | System user running the service                                             |
| `install`, `uninstall` | `system_group`      | `alertmanager`              | System group running the service                                            |
| `install`              | `version`           | `0.34.0`                    | alertmanager release version to download                                    |
| `install`              | `service_args`      | `DEFAULT_SERVICE_ARGS`      | Dict of `--flag: value` (or `None` for a bare flag) passed to `alertmanager` |
| `install`              | `config_template`   | `DEFAULT_CONFIG_TEMPLATE`   | Path to a Jinja2 template rendered to `/etc/alertmanager/config.yml`         |
| `install`              | `config_context`    | `None`                      | Dict of variables passed to `config_template` when rendering                |

## :heart: Contributing

If you find this project useful here's how you can help, please click the :eye: **Watch** button
to avoid missing notifications about new versions, and give it a :star2: **GitHub Star**!

You can also contribute by:

- Sending a [Pull Request](https://github.com/techcode-io/pyinfra-alertmanager/pulls) with your
  awesome new features and bug fixed.
- Be part of the community and help resolve
  [Issues](https://github.com/techcode-io/pyinfra-alertmanager/issues).

## 🧾 License

The `pyinfra-alertmanager` project is free and open-source software licensed under the Apache-2.0
license.
