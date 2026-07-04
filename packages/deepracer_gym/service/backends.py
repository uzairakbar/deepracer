import os
import abc
import json
import glob
import shutil
import hashlib
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
    overlay: str | None=None   # Apptainer per-instance overlay dir (cleaned on stop)


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


def apptainer_env(spec: SimSpec) -> dict[str, str]:
    '''Container env for Apptainer, passed via `APPTAINERENV_*` host variables
    (apptainer strips the prefix and injects `KEY=VALUE`). This is robust to
    values containing commas/quotes — our `DEEPRACER_*` specs are JSON — unlike a
    single `--env KEY=v,KEY2=v` CSV, whose commas the JSON would break.'''
    return {f'APPTAINERENV_{k}': v for k, v in spec_to_env(spec).items()}


def apptainer_run_argv(spec: SimSpec, sif: str, binary: str='apptainer') -> list[str]:
    '''`apptainer instance run` argv. Shared netns → the sim binds identity.port
    directly (GYM_PORT via `APPTAINERENV_*`, §4.4 identity too). No `--pwd` (PACE
    lacks it), no config mount, per-instance overlay. `sif` is a resolved SIF
    path (see ApptainerBackend._resolve_sif); env travels in the process env, not
    argv.'''
    return [
        binary, 'instance', 'run',
        '--no-mount', 'home,tmp,/dev,/etc/hosts,/etc/localtime,/proc,/sys,/var/tmp',
        '--overlay', spec.identity.overlay,
        sif, spec.identity.name,
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

    @staticmethod
    def _scratch() -> str:
        '''Where cached SIFs live: $SCRATCH, else ~/scratch, else /tmp (mirrors
        the legacy start_deepracer.sh scratch resolution).'''
        if os.environ.get('SCRATCH'):
            return os.environ['SCRATCH']
        home_scratch = os.path.expanduser('~/scratch')
        return home_scratch if os.path.isdir(home_scratch) else '/tmp'

    def _resolve_sif(self, image: str) -> str:
        '''Apptainer needs a `.sif` file or a `docker://` URI, not a bare docker
        name. A `.sif` path is used as-is; anything else is pulled ONCE to a
        cached SIF under $SCRATCH and reused (one-time cost, like the old flow).'''
        if image.endswith('.sif'):
            return image
        ref = image if image.startswith('docker://') else f'docker://{image}'
        digest = hashlib.sha1(image.encode()).hexdigest()[:10]
        sif = os.path.join(self._scratch(), f'deepracer-{digest}.sif')
        if not os.path.exists(sif):
            logger.info(f'[apptainer] pulling {ref} -> {sif} (one-time)')
            result = _run([self.binary, 'pull', '--force', sif, ref], self._exec)
            if result.returncode != 0:
                raise RuntimeError(f'apptainer pull failed: {result.stderr.strip()}')
        return sif

    def _instance_exists(self, name: str) -> bool:
        result = _run([self.binary, 'instance', 'list', '--json'], self._exec)
        if result.returncode != 0:
            return False
        try:
            instances = json.loads(result.stdout).get('instances', [])
        except Exception:
            return False
        return any(i.get('instance') == name for i in instances)

    def start(self, spec: SimSpec) -> SimHandle:
        # Only stop a genuinely pre-existing stale instance of this name (found
        # on PACE, 2026-07-04): calling `instance stop` unconditionally -- even
        # when there is nothing to stop -- races with the `instance run` that
        # follows and can kill the brand-new instance within milliseconds of
        # start (observed as the fresh container's own Python interpreter dying
        # with a SIGINT/rc=130 during its own site-module import). Skipping the
        # no-op stop call removes that race entirely.
        if self._instance_exists(spec.identity.name):
            _run([self.binary, 'instance', 'stop', spec.identity.name], self._exec)
        # Apptainer never rotates its per-name log files (see _log_paths) -- a
        # stale FATAL: line from a PAST run of this same name would otherwise
        # make _wait_ready's health check fail the brand-new container on its
        # very first poll. Clear them so this run starts from a clean slate.
        for path in self._log_paths(spec.identity.name):
            try:
                os.remove(path)
            except OSError:
                pass
        sif = self._resolve_sif(spec.image)
        os.makedirs(spec.identity.overlay, exist_ok=True)
        # config + identity travel via APPTAINERENV_* in the process env, robust
        # to the JSON commas that a single --env CSV would mangle.
        env = {**os.environ, **apptainer_env(spec)}
        result = _run(
            apptainer_run_argv(spec, sif, self.binary), self._exec, env=env,
        )
        if result.returncode != 0:
            shutil.rmtree(spec.identity.overlay, ignore_errors=True)
            raise RuntimeError(f'apptainer instance run failed: {result.stderr.strip()}')
        logger.info(f'[apptainer] started {spec.identity.name} (port {spec.identity.port})')
        return SimHandle(
            id=spec.identity.name, name=spec.identity.name,
            port=spec.identity.port, backend=self.name,
            fingerprint=spec.fingerprint, env_id=spec.identity.env_id,
            overlay=spec.identity.overlay,
        )

    def stop(self, handle: SimHandle) -> None:
        _run([self.binary, 'instance', 'stop', handle.name], self._exec)
        if handle.overlay:
            shutil.rmtree(handle.overlay, ignore_errors=True)

    def is_alive(self, handle: SimHandle) -> bool:
        return self._instance_exists(handle.name)

    @staticmethod
    def _log_paths(name: str) -> list[str]:
        '''Apptainer writes instance logs under ~/.apptainer/instances/logs/
        <host>/<user>/<name>.{out,err} and -- unlike Docker/Podman -- NEVER
        rotates or truncates them: every future `instance run` of the same
        name keeps appending to the same file. Found on PACE, 2026-07-04: a
        past run's `FATAL:` marker (even from an ordinary graceful stop, which
        the entrypoint's TERM/INT trap also logs as "FATAL: ... terminating
        container") permanently poisons `logs()` for every later start of that
        name -- `_wait_ready`'s very first poll sees the stale line and kills
        the brand-new container within milliseconds. `start()` clears these
        before launching so each run gets a clean slate.'''
        base = os.path.expanduser('~/.apptainer/instances/logs')
        return glob.glob(os.path.join(base, '*', '*', f'{name}.out')) + \
            glob.glob(os.path.join(base, '*', '*', f'{name}.err'))

    def logs(self, handle: SimHandle) -> str:
        '''Read the instance's stdout/stderr logs (for FATAL detection + debug).'''
        text = ''
        for path in self._log_paths(handle.name):
            try:
                text += open(path).read()
            except OSError:
                pass
        return text

    # Apptainer instances carry no label store, so cache reuse is disabled for
    # the first cut (find_idle -> None inherited): cache=True simply starts fresh
    # on Apptainer, which is safe. (Podman/Docker get full cache reuse.)


BACKENDS: list[type[SimBackend]] = [DockerBackend, PodmanBackend, ApptainerBackend]


def detect_backend(prefer: str | None=None) -> SimBackend:
    '''Pick a runtime: explicit `prefer` (or the `DEEPRACER_BACKEND` env var),
    else auto-detect Docker → Podman → Apptainer.'''
    prefer = prefer or os.environ.get('DEEPRACER_BACKEND')
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
