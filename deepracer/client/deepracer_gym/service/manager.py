import os
import time
import atexit
import socket
import threading

from loguru import logger

from deepracer_gym.service.identity import (
    current_user, free_env_id, fingerprint,
)
from deepracer_gym.service.spec import SimSpec, DEFAULT_IMAGE
from deepracer_gym.service.backends import SimBackend, SimHandle, detect_backend


DEFAULT_MAX_ENVS: int=int(os.environ.get('DEEPRACER_MAX_ENVS', '4'))
# Generous readiness budget: the real sim takes ~1 min to boot; fake-sim is instant.
DEFAULT_READY_TIMEOUT: float=float(os.environ.get('DEEPRACER_READY_TIMEOUT', '300'))
# The sim exits non-zero with this line on genuine launch death (simapp 93443ac).
FATAL_MARKER: str='FATAL:'
# gym_agent.py prints this once its ZMQ server has bound (readiness for OCI, where
# the docker/podman userland proxy makes a bare TCP probe answer too early).
READY_MARKER: str='Waiting for gym client'


def _tcp_open(host: str, port: int, timeout: float=0.5) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(timeout)
        try:
            probe.connect((host, port))
            return True
        except OSError:
            return False


def _zmq_reserves(port: int, timeout: float=5.0) -> bool:
    '''True if a ZMQ gym server is live on the port and re-serves a fresh client
    (sends an observation in response to a `ready`). Used before attaching to a
    cached container so cache degrades to a fresh start instead of hanging on a
    sim that did not survive the previous client's disconnect (§4.11 safety
    valve). A bare TCP probe is not enough under Docker/Podman (the userland
    proxy answers even when the app is dead).'''
    try:
        import zmq
        import msgpack
    except Exception:
        return _tcp_open('127.0.0.1', port)      # no zmq here; best-effort
    ctx = zmq.Context.instance()
    sock = ctx.socket(zmq.REQ)
    sock.setsockopt(zmq.LINGER, 0)
    sock.setsockopt(zmq.RCVTIMEO, int(timeout * 1000))
    sock.setsockopt(zmq.SNDTIMEO, int(timeout * 1000))
    sock.connect(f'tcp://127.0.0.1:{port}')
    try:
        sock.send(msgpack.packb({'ready': 1}))
        sock.recv()                              # any reply => server re-served
        return True
    except Exception:
        return False
    finally:
        sock.close()


def _tail(text: str, lines: int=25) -> str:
    return '\n'.join(text.splitlines()[-lines:])


class SimulationManager:
    '''Owns the container lifecycle for this process. Default path: fresh
    container per acquire, stop on release. cache=True: warm attach-or-start with
    an in-process idle pool keyed by config fingerprint (§4.5, §4.11).'''

    _instance: 'SimulationManager | None'=None
    _instance_lock = threading.Lock()

    def __init__(
            self,
            backend: SimBackend | None=None,
            max_envs: int=DEFAULT_MAX_ENVS,
            user: str | None=None,
            ready_timeout: float=DEFAULT_READY_TIMEOUT,
        ):
        self.backend = backend or detect_backend()
        self.max_envs = max_envs
        self.user = user or current_user()
        self.ready_timeout = ready_timeout
        self._live: dict[str, SimHandle]={}                 # name -> busy handle we own
        self._idle: dict[str, list[SimHandle]]={}           # fingerprint -> idle handles
        self._lock = threading.RLock()
        atexit.register(self.shutdown_all)

    @classmethod
    def instance(cls, **kwargs) -> 'SimulationManager':
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = cls(**kwargs)
            return cls._instance

    # -- internal helpers -----------------------------------------------------
    def _taken_env_ids(self) -> set[int]:
        ids = {h.env_id for h in self._live.values()}
        for handles in self._idle.values():
            ids |= {h.env_id for h in handles}
        return ids

    def _take_idle(self, fp: str) -> SimHandle | None:
        '''Pop a live idle container for this fingerprint (in-process pool),
        dropping any that have died. Cross-process discovery falls through.'''
        pool = self._idle.get(fp, [])
        while pool:
            handle = pool.pop()
            if self.backend.is_alive(handle) and _zmq_reserves(handle.port):
                self._live[handle.name] = handle
                logger.info(f'[cache] re-attached warm {handle.name} (fp {fp})')
                return handle
            self.backend.stop(handle)      # dead or won't re-serve; reap
        # cross-process: a container left running by another kernel
        found = self.backend.find_idle(fp)
        if found and self.backend.is_alive(found) and _zmq_reserves(found.port):
            self._live[found.name] = found
            logger.info(f'[cache] adopted running {found.name} (fp {fp})')
            return found
        return None

    def _reap_one_idle(self) -> bool:
        for fp, handles in self._idle.items():
            if handles:
                self.backend.stop(handles.pop())
                return True
        return False

    def _is_ready(self, handle: SimHandle, logs: str) -> bool:
        '''Ready signal, per backend. OCI: the server's bound marker in the logs
        (a bare TCP probe answers via the proxy before the app binds). Apptainer:
        a direct TCP probe (no proxy, binds the host port).'''
        if self.backend.readiness == 'logs':
            return READY_MARKER in logs
        return _tcp_open('127.0.0.1', handle.port)

    def _wait_ready(self, handle: SimHandle) -> None:
        deadline = time.time() + self.ready_timeout
        while time.time() < deadline:
            logs = self.backend.logs(handle)
            alive = self.backend.is_alive(handle)
            fatal = [l for l in logs.splitlines() if FATAL_MARKER in l]
            if fatal or not alive:
                self._force_stop(handle)
                raise RuntimeError(
                    f'Simulation {handle.name} exited during startup.\n'
                    + ('\n'.join(fatal) if fatal else _tail(logs))
                )
            if self._is_ready(handle, logs):
                return
            time.sleep(0.5)
        logs = self.backend.logs(handle)
        self._force_stop(handle)
        raise TimeoutError(
            f'Simulation {handle.name} not ready in {self.ready_timeout:.0f}s.\n'
            + _tail(logs)
        )

    def _force_stop(self, handle: SimHandle) -> None:
        with self._lock:
            self._live.pop(handle.name, None)
        try:
            self.backend.stop(handle)
        except Exception:
            pass

    # -- public API -----------------------------------------------------------
    def acquire(
            self,
            *,
            agent_config: dict,
            track_config: dict,
            image: str=DEFAULT_IMAGE,
            cpus: float=3.0,
            memory: str='6g',
            evaluation: bool=False,
            world_name: str | None=None,
            cache: bool=False,
        ) -> SimHandle:
        fp = fingerprint(image, agent_config, track_config, evaluation, world_name)
        with self._lock:
            if cache:
                warm = self._take_idle(fp)
                if warm is not None:
                    return warm
            try:
                identity = free_env_id(self.user, self.max_envs, self._taken_env_ids())
            except RuntimeError:
                if not self._reap_one_idle():
                    raise
                identity = free_env_id(self.user, self.max_envs, self._taken_env_ids())
            spec = SimSpec(
                identity=identity, agent_config=agent_config, track_config=track_config,
                image=image, cpus=cpus, memory=memory, evaluation=evaluation,
                world_name=world_name,
            )
            handle = self.backend.start(spec)
            self._live[handle.name] = handle
        self._wait_ready(handle)
        return handle

    def release(self, handle: SimHandle, cache: bool=False) -> None:
        with self._lock:
            self._live.pop(handle.name, None)
            if cache and self.backend.is_alive(handle):
                self._idle.setdefault(handle.fingerprint, []).append(handle)
                logger.info(f'[cache] kept {handle.name} warm (fp {handle.fingerprint})')
                return
        try:
            self.backend.stop(handle)
        except Exception:
            pass

    def shutdown_all(self, include_cached: bool=False) -> None:
        '''Stop everything this process owns. Idle-cached containers persist by
        default (cross-kernel reuse, §4.11) unless include_cached=True (clean).'''
        with self._lock:
            handles = list(self._live.values())
            if include_cached:
                for pool in self._idle.values():
                    handles.extend(pool)
                self._idle.clear()
            self._live.clear()
        for handle in handles:
            try:
                self.backend.stop(handle)
            except Exception:
                pass
