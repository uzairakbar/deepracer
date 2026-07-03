import abc
import shutil
import subprocess
from dataclasses import dataclass

from loguru import logger

from deepracer_gym.service.spec import (
    SimSpec, spec_to_env, spec_labels, INTERNAL_PORT, LABEL_NS,
)


@dataclass
class SimHandle:
    '''Opaque reference to one running sim, returned by a backend's start/attach.'''
    id: str                 # container id (docker/podman) or instance name (apptainer)
    name: str
    port: int
    backend: str
    fingerprint: str
    env_id: int


class SimBackend(abc.ABC):
    '''Runtime-agnostic container control. OCI engines (Docker, Podman) give each
    container its own netns; Apptainer shares the host netns (needs §4.4).'''
    name: str = 'abstract'
    # How the manager decides "ready": 'logs' watches for the server's bound
    # marker (OCI — the userland proxy makes a bare TCP probe answer too early),
    # 'tcp' probes the port directly (Apptainer — no proxy, binds host port).
    readiness: str = 'logs'

    @staticmethod
    @abc.abstractmethod
    def available() -> bool:
        ...

    @abc.abstractmethod
    def start(self, spec: SimSpec) -> SimHandle:
        ...

    @abc.abstractmethod
    def stop(self, handle: SimHandle) -> None:
        ...

    @abc.abstractmethod
    def is_alive(self, handle: SimHandle) -> bool:
        ...

    @abc.abstractmethod
    def logs(self, handle: SimHandle) -> str:
        ...

    # --- cache support (OCI backends override; others no-op / None) ---------
    def find_idle(self, fingerprint: str) -> SimHandle | None:
        '''Return an idle cached container matching the fingerprint, else None.'''
        return None

    def set_state(self, handle: SimHandle, state: str) -> None:
        '''Flip the idle/busy discovery label (no-op where labels don't exist).'''
        return None


# --------------------------------------------------------------------------- #
# Docker — official Python SDK
# --------------------------------------------------------------------------- #
class DockerBackend(SimBackend):
    name = 'docker'

    def __init__(self, client=None):
        import docker
        self._docker = docker
        self._client = client or docker.from_env()

    @staticmethod
    def available() -> bool:
        try:
            import docker
            docker.from_env().ping()
            return True
        except Exception:
            return False

    def _remove_if_exists(self, name: str) -> None:
        try:
            old = self._client.containers.get(name)
            old.remove(force=True)
        except Exception:
            pass

    def start(self, spec: SimSpec) -> SimHandle:
        self._remove_if_exists(spec.identity.name)
        container = self._client.containers.run(
            spec.image,
            detach=True,
            remove=False,               # keep after exit so logs() survives a crash
            name=spec.identity.name,
            hostname=spec.identity.name,
            ports={f'{INTERNAL_PORT}/tcp': ('127.0.0.1', spec.identity.port)},
            environment=spec_to_env(spec, gym_port=INTERNAL_PORT),
            labels=spec_labels(spec),
            nano_cpus=int(spec.cpus * 1e9),
            mem_limit=spec.memory,
        )
        logger.info(
            f'[docker] started {spec.identity.name} '
            f'(port {spec.identity.port}, fp {spec.fingerprint})'
        )
        return SimHandle(
            id=container.id, name=spec.identity.name, port=spec.identity.port,
            backend=self.name, fingerprint=spec.fingerprint,
            env_id=spec.identity.env_id,
        )

    def _get(self, handle: SimHandle):
        return self._client.containers.get(handle.id)

    def stop(self, handle: SimHandle) -> None:
        try:
            container = self._get(handle)
        except Exception:
            return                       # already gone — idempotent
        try:
            container.stop(timeout=10)
        except Exception:
            pass
        try:
            container.remove(force=True)
        except Exception:
            pass

    def is_alive(self, handle: SimHandle) -> bool:
        try:
            container = self._get(handle)
            container.reload()
            return container.status == 'running'
        except Exception:
            return False

    def logs(self, handle: SimHandle) -> str:
        try:
            return self._get(handle).logs().decode('utf-8', 'replace')
        except Exception:
            return ''

    def exit_code(self, handle: SimHandle) -> int | None:
        try:
            container = self._get(handle)
            container.reload()
            return container.attrs.get('State', {}).get('ExitCode')
        except Exception:
            return None

    def find_idle(self, fingerprint: str) -> SimHandle | None:
        '''Any *running* managed container of this fingerprint (a cross-process
        reuse candidate). The manager probe-before-claims it (§4.11).'''
        filters = {'label': [
            f'{LABEL_NS}.managed=true',
            f'{LABEL_NS}.fingerprint={fingerprint}',
        ], 'status': 'running'}
        for container in self._client.containers.list(filters=filters):
            ports = container.attrs['NetworkSettings']['Ports'].get(
                f'{INTERNAL_PORT}/tcp'
            )
            if not ports:
                continue
            return SimHandle(
                id=container.id, name=container.name,
                port=int(ports[0]['HostPort']), backend=self.name,
                fingerprint=fingerprint,
                env_id=int(container.labels.get(f'{LABEL_NS}.env_id', -1)),
            )
        return None


# --------------------------------------------------------------------------- #
# Podman / Apptainer — CLI wrappers (argv built purely, so it is unit-testable)
# --------------------------------------------------------------------------- #
def _run(argv: list[str], executor=subprocess.run, **kwargs):
    return executor(argv, capture_output=True, text=True, **kwargs)


def podman_run_argv(spec: SimSpec, binary: str='podman') -> list[str]:
    '''`podman run` argv — Docker-compatible flags; own netns → publish port.'''
    argv = [
        binary, 'run', '--detach', '--name', spec.identity.name,
        '-p', f'127.0.0.1:{spec.identity.port}:{INTERNAL_PORT}',
        '--cpus', str(spec.cpus), '--memory', spec.memory,
    ]
    for key, value in spec_labels(spec).items():
        argv += ['--label', f'{key}={value}']
    for key, value in spec_to_env(spec, gym_port=INTERNAL_PORT).items():
        argv += ['--env', f'{key}={value}']
    argv.append(spec.image)
    return argv


def apptainer_run_argv(spec: SimSpec, binary: str='apptainer') -> list[str]:
    '''`apptainer instance run` argv — shared netns (needs §4.4 identity), no
    `--pwd`, no config mount, per-instance overlay. Assumes a pulled SIF path is
    the image (resolved by the backend); here `spec.image` is the SIF/URI.'''
    env = spec_to_env(spec)
    env_csv = ','.join(f'{k}={v}' for k, v in env.items())
    return [
        binary, 'instance', 'run',
        '--no-mount', 'home,tmp,/dev,/etc/hosts,/etc/localtime,/proc,/sys,/var/tmp',
        '--overlay', spec.identity.overlay,
        '--env', env_csv,
        spec.image, spec.identity.name,
    ]


class _CliBackend(SimBackend):
    '''Shared logic for CLI-driven runtimes; `executor` is injectable for tests.'''
    binary: str = ''

    def __init__(self, executor=subprocess.run):
        self._exec = executor

    def logs(self, handle: SimHandle) -> str:
        result = _run([self.binary, 'logs', handle.name], self._exec)
        return (result.stdout or '') + (result.stderr or '')


class PodmanBackend(_CliBackend):
    name = 'podman'
    binary = 'podman'

    @staticmethod
    def available() -> bool:
        return shutil.which('podman') is not None

    def start(self, spec: SimSpec) -> SimHandle:
        _run([self.binary, 'rm', '-f', spec.identity.name], self._exec)  # clear leftover
        result = _run(podman_run_argv(spec, self.binary), self._exec)
        if result.returncode != 0:
            raise RuntimeError(f'podman run failed: {result.stderr.strip()}')
        logger.info(f'[podman] started {spec.identity.name} (port {spec.identity.port})')
        return SimHandle(
            id=result.stdout.strip(), name=spec.identity.name,
            port=spec.identity.port, backend=self.name,
            fingerprint=spec.fingerprint, env_id=spec.identity.env_id,
        )

    def stop(self, handle: SimHandle) -> None:
        _run([self.binary, 'rm', '-f', handle.name], self._exec)

    def is_alive(self, handle: SimHandle) -> bool:
        result = _run(
            [self.binary, 'inspect', '-f', '{{.State.Running}}', handle.name],
            self._exec,
        )
        return result.returncode == 0 and result.stdout.strip() == 'true'

    def find_idle(self, fingerprint: str) -> SimHandle | None:
        result = _run([
            self.binary, 'ps', '--filter',
            f'label={LABEL_NS}.fingerprint={fingerprint}',
            '--format', '{{.Names}}',
        ], self._exec)
        names = [n for n in (result.stdout or '').split() if n]
        if not names:
            return None
        # port from the running container's identity (name encodes env_id)
        name = names[0]
        env_id = int(name.rsplit('-', 1)[-1])
        from deepracer_gym.service.identity import make_identity, current_user
        port = make_identity(current_user(), env_id).port
        return SimHandle(id=name, name=name, port=port, backend=self.name,
                         fingerprint=fingerprint, env_id=env_id)


class ApptainerBackend(_CliBackend):
    name = 'apptainer'
    binary = 'apptainer'
    readiness = 'tcp'          # shared netns, no proxy → TCP probe is reliable

    @staticmethod
    def available() -> bool:
        return shutil.which('apptainer') is not None

    def start(self, spec: SimSpec) -> SimHandle:
        _run([self.binary, 'instance', 'stop', spec.identity.name], self._exec)
        result = _run(apptainer_run_argv(spec, self.binary), self._exec)
        if result.returncode != 0:
            raise RuntimeError(f'apptainer instance run failed: {result.stderr.strip()}')
        logger.info(f'[apptainer] started {spec.identity.name} (port {spec.identity.port})')
        return SimHandle(
            id=spec.identity.name, name=spec.identity.name,
            port=spec.identity.port, backend=self.name,
            fingerprint=spec.fingerprint, env_id=spec.identity.env_id,
        )

    def stop(self, handle: SimHandle) -> None:
        _run([self.binary, 'instance', 'stop', handle.name], self._exec)

    def is_alive(self, handle: SimHandle) -> bool:
        result = _run(
            [self.binary, 'instance', 'list', '--json'], self._exec,
        )
        if result.returncode != 0:
            return False
        import json
        try:
            instances = json.loads(result.stdout).get('instances', [])
        except Exception:
            return False
        return any(i.get('instance') == handle.name for i in instances)

    def logs(self, handle: SimHandle) -> str:
        # apptainer writes instance logs under ~/.apptainer; best-effort empty.
        return ''

    # Apptainer has no label store; cache reuse is disabled for the first cut
    # (find_idle -> None inherited), so it always starts fresh (§4.2 note).


BACKENDS: list[type[SimBackend]] = [DockerBackend, PodmanBackend, ApptainerBackend]


def detect_backend(prefer: str | None=None) -> SimBackend:
    '''Pick a runtime: explicit `prefer`, else Docker → Podman → Apptainer.'''
    by_name = {b.name: b for b in BACKENDS}
    if prefer:
        cls = by_name.get(prefer)
        if cls is None:
            raise ValueError(f'Unknown backend {prefer!r}; have {list(by_name)}.')
        if not cls.available():
            raise RuntimeError(f'Requested backend {prefer!r} is not available here.')
        return cls()
    for cls in BACKENDS:
        if cls.available():
            return cls()
    raise RuntimeError(
        'No container runtime found. Install Docker or Podman (or Apptainer).'
    )
