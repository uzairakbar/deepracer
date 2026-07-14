import os
import abc
import json
import glob
import shutil
import hashlib
import subprocess
from dataclasses import dataclass

from loguru import logger

from deepracer.service.spec import (
    SimSpec, spec_to_env, spec_labels, INTERNAL_PORT, LABEL_NS,
)


# Shown only when the image is missing locally so a slow first-run pull is visible.
PULL_HINT: str = (
    'Pulling simulator image {image} (first run) — this can take several minutes '
    'on a slow connection; your kernel is not frozen, please wait.'
)


@dataclass
class SimHandle:
    '''Opaque reference to one running sim, returned by a backend's start/attach.'''
    id: str                 # container id, or Apptainer instance name
    name: str
    port: int
    backend: str
    fingerprint: str
    env_id: int
    overlay: str | None=None   # Apptainer per-instance overlay dir (cleaned on stop)


class SimBackend(abc.ABC):
    '''Runtime-agnostic container control. OCI engines (Docker, Podman) give each
    container its own netns; Apptainer shares the host netns.'''
    name: str = 'abstract'
    # OCI readiness must use logs because the userland proxy can answer TCP
    # before the app binds. Apptainer binds the host port directly.
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

    def managed_containers(self) -> list[str]:
        '''Names of this backend's managed DeepRacer containers currently on the
        host (any process). Best-effort; used only for the startup hint about
        leftovers from an ungracefully-killed session.'''
        return []

    def pause(self, handle: SimHandle) -> None:
        '''Freeze an idle warm container (SIGSTOP via the runtime) so it stops
        burning CPU while parked in the idle pool. Best-effort; no-op for runtimes
        that cannot pause instances (e.g. Apptainer). Overridden by OCI backends.'''
        return None

    def unpause(self, handle: SimHandle) -> None:
        '''Resume a paused warm container before it is re-attached for reuse.
        Best-effort; the paired no-op default for non-pausing runtimes.'''
        return None


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

    def _log_if_pulling(self, image: str) -> None:
        '''containers.run() auto-pulls a missing image; warn first so a slow
        first-run pull isn't mistaken for a hung kernel. Only when truly absent.'''
        try:
            self._client.images.get(image)
        except self._docker.errors.ImageNotFound:
            logger.info(PULL_HINT.format(image=image))
        except Exception:
            pass                         # unknown cache state; stay quiet

    def start(self, spec: SimSpec) -> SimHandle:
        self._remove_if_exists(spec.identity.name)
        self._log_if_pulling(spec.image)
        container = self._client.containers.run(
            spec.image,
            detach=True,
            remove=False,               # preserve crash logs for readiness errors
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
            return                       # already gone
        try:
            container.unpause()          # thaw a paused (idle warm) container so
        except Exception:                # stop/remove is not blocked by the freeze
            pass
        try:
            container.stop(timeout=10)
        except Exception:
            pass
        try:
            container.remove(force=True)
        except Exception:
            pass

    def pause(self, handle: SimHandle) -> None:
        try:
            self._get(handle).pause()
        except Exception:
            pass

    def unpause(self, handle: SimHandle) -> None:
        try:
            self._get(handle).unpause()
        except Exception:
            pass

    def is_alive(self, handle: SimHandle) -> bool:
        try:
            container = self._get(handle)
            container.reload()
            # 'paused' counts as alive: an idle warm container we froze is still
            # a reusable sim (unpaused before reuse). Podman's is_alive already
            # treats it so (a paused container keeps State.Running=true).
            return container.status in ('running', 'paused')
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

    def managed_containers(self) -> list[str]:
        try:
            containers = self._client.containers.list(
                filters={'label': f'{LABEL_NS}.managed=true'}
            )
            return [c.name for c in containers]
        except Exception:
            return []


def _run(argv: list[str], executor=subprocess.run, **kwargs):
    return executor(argv, capture_output=True, text=True, **kwargs)


def qualify_image(image: str) -> str:
    '''Fully qualify a bare Docker short name with the `docker.io` registry.

    Podman can run with enforcing short-name resolution, which prompts for a
    registry and fails in a non-TTY kernel. Docker resolves docker.io implicitly
    and Apptainer gets docker:// elsewhere, so only Podman needs this helper.

    A reference is already qualified if its first path component looks like a
    registry host (contains `.` or `:`, or is `localhost`); a `.sif`/`docker://`
    /absolute reference is not a Docker short name and is left alone.'''
    if image.endswith('.sif') or image.startswith(('docker://', '/', './')):
        return image
    first = image.split('/', 1)[0]
    if '/' in image and ('.' in first or ':' in first or first == 'localhost'):
        return image                       # already registry-qualified
    return f'docker.io/{image}'


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
    argv.append(qualify_image(spec.image))
    return argv


def apptainer_env(spec: SimSpec) -> dict[str, str]:
    '''Container env for Apptainer, passed via `APPTAINERENV_*` host variables
    (apptainer strips the prefix and injects `KEY=VALUE`). This is robust to
    values containing commas/quotes — our `DEEPRACER_*` specs are JSON — unlike a
    single `--env KEY=v,KEY2=v` CSV, whose commas the JSON would break.'''
    return {f'APPTAINERENV_{k}': v for k, v in spec_to_env(spec).items()}


def apptainer_run_argv(spec: SimSpec, sif: str, binary: str='apptainer') -> list[str]:
    '''`apptainer instance run` argv. Shared netns → the sim binds identity.port
    directly via `APPTAINERENV_GYM_PORT`. No `--pwd`, no config mount, and a
    per-instance overlay. `sif` is resolved by ApptainerBackend._resolve_sif;
    env travels in the process env, not argv.'''
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

    def _log_if_pulling(self, image: str) -> None:
        '''`podman run` auto-pulls a missing image; warn first so a slow first-run
        pull isn't mistaken for a hung kernel. Only when truly absent.'''
        result = _run([self.binary, 'image', 'exists', image], self._exec)
        if result.returncode != 0:
            logger.info(PULL_HINT.format(image=image))

    def start(self, spec: SimSpec) -> SimHandle:
        _run([self.binary, 'rm', '-f', spec.identity.name], self._exec)  # clear leftover
        self._log_if_pulling(qualify_image(spec.image))
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
        # Thaw first so `rm -f` is not blocked by a paused (idle warm) container;
        # unpause of a non-paused container just errors harmlessly (ignored).
        _run([self.binary, 'unpause', handle.name], self._exec)
        _run([self.binary, 'rm', '-f', handle.name], self._exec)

    def pause(self, handle: SimHandle) -> None:
        _run([self.binary, 'pause', handle.name], self._exec)

    def unpause(self, handle: SimHandle) -> None:
        _run([self.binary, 'unpause', handle.name], self._exec)

    def is_alive(self, handle: SimHandle) -> bool:
        result = _run(
            [self.binary, 'inspect', '-f', '{{.State.Running}}', handle.name],
            self._exec,
        )
        return result.returncode == 0 and result.stdout.strip() == 'true'

    def managed_containers(self) -> list[str]:
        result = _run([
            self.binary, 'ps', '--filter', f'label={LABEL_NS}.managed=true',
            '--format', '{{.Names}}',
        ], self._exec)
        return [n for n in (result.stdout or '').split() if n]


class ApptainerBackend(_CliBackend):
    name = 'apptainer'
    binary = 'apptainer'
    readiness = 'tcp'          # shared netns, so a TCP probe reaches the app

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
            logger.info(f'[apptainer] pulling {ref} -> {sif} (one-time) — this can '
                        f'take several minutes on a slow connection; your kernel is '
                        f'not frozen, please wait.')
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
        # Stop only an instance that is actually listed. An unconditional
        # no-op stop can race with the following instance run and kill it.
        if self._instance_exists(spec.identity.name):
            _run([self.binary, 'instance', 'stop', spec.identity.name], self._exec)
        # Apptainer appends to per-name logs. Clear them so stale FATAL lines
        # cannot fail readiness for a new instance with the same name.
        for path in self._log_paths(spec.identity.name):
            try:
                os.remove(path)
            except OSError:
                pass
        sif = self._resolve_sif(spec.image)
        os.makedirs(spec.identity.overlay, exist_ok=True)
        # APPTAINERENV_* preserves JSON values that a single --env CSV would split.
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
        <host>/<user>/<name>.{out,err} and appends to the same files on later
        runs of the same name. `start()` clears them before launch so stale
        FATAL markers cannot poison readiness checks for a new instance.'''
        base = os.path.expanduser('~/.apptainer/instances/logs')
        return glob.glob(os.path.join(base, '*', '*', f'{name}.out')) + \
            glob.glob(os.path.join(base, '*', '*', f'{name}.err'))

    def logs(self, handle: SimHandle) -> str:
        '''Read the instance's stdout/stderr logs for readiness diagnostics.'''
        text = ''
        for path in self._log_paths(handle.name):
            try:
                text += open(path).read()
            except OSError:
                pass
        return text

    def managed_containers(self) -> list[str]:
        result = _run([self.binary, 'instance', 'list', '--json'], self._exec)
        try:
            instances = json.loads(result.stdout).get('instances', [])
        except Exception:
            return []
        return [i['instance'] for i in instances
                if str(i.get('instance', '')).startswith('deepracer-')]

    # Warm reuse is in-process only (the manager's idle pool) and uniform across
    # all backends; no backend does cross-process container adoption, so there is
    # no idle/busy discovery label to maintain.


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
