import json
import socket
import hashlib
import getpass
from dataclasses import dataclass


# unprivileged TCP band (mirrors the bash string_to_port and envs.utils)
PORT_LO: int=1024
PORT_HI: int=32767
# Xvfb display base: high enough to dodge a real desktop's :0 on a shared node.
DISPLAY_BASE: int=90
# ROS 2 safe domain range is 1..101 (0 is the shared default).
ROS_DOMAIN_SPAN: int=101


def _sha_int(string: str) -> int:
    '''First 4 bytes of sha256(string) as a big-endian int (matches entrypoint.sh).'''
    return int.from_bytes(
        hashlib.sha256(string.encode()).digest()[:4], byteorder='big'
    )


def string_to_port(string: str) -> int:
    '''Deterministic port in [PORT_LO, PORT_HI]. Same mapping as envs.utils and the bash.'''
    return PORT_LO + (_sha_int(string) % (PORT_HI - PORT_LO + 1))


def current_user() -> str:
    '''Username, robust across platforms (os.environ['USER'] is unset on Windows).'''
    try:
        return getpass.getuser()
    except Exception:
        return 'deepracer'


@dataclass(frozen=True)
class Identity:
    '''All per-instance identity derived from a single (user, env_id) seed.

    Ports/display/domain/partition/overlay are keyed on env_id so N concurrent
    sims for one user never collide. Only Apptainer (shared host netns) actually
    needs the ROS/GZ/display/overlay fields; Docker and Podman get isolation for
    free from their own network namespace, but we still pass them (harmless).
    '''
    user: str
    env_id: int
    name: str
    port: int
    ros_domain_id: int
    gz_partition: str
    display: str
    overlay: str


def make_identity(user: str, env_id: int) -> Identity:
    seed = f'{user}_{env_id}'
    return Identity(
        user=user,
        env_id=env_id,
        name=f'deepracer-{user}-{env_id}',
        port=string_to_port(seed),
        ros_domain_id=1 + (_sha_int(f'ROS_{seed}') % ROS_DOMAIN_SPAN),
        gz_partition=seed,
        display=f':{DISPLAY_BASE + env_id}',
        overlay=f'/tmp/deepracer_{seed}',
    )


def port_is_free(port: int, host: str='127.0.0.1') -> bool:
    '''True if nothing is currently bound to host:port.

    Probes by binding WITHOUT SO_REUSEADDR so an active listener (a running sim,
    ours or another kernel's / user's) is detected as busy. This is the
    hash-then-PROBE step: hashing alone can't tell whether a port is already
    taken on a shared node (the MinIO lesson, REFACTOR_DESIGN.md §9).
    '''
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind((host, port))
            return True
        except OSError:
            return False


def free_env_id(
        user: str,
        max_envs: int,
        taken: set[int]=frozenset(),
    ) -> Identity:
    '''First env_id in [0, max_envs) whose port is free and not already owned.

    Raises RuntimeError if all slots are busy (the MAX_ENVS cap, §6.1).
    '''
    for env_id in range(max_envs):
        if env_id in taken:
            continue
        candidate = make_identity(user, env_id)
        if port_is_free(candidate.port):
            return candidate
    raise RuntimeError(
        f'All {max_envs} DeepRacer environment slots are in use '
        f'(MAX_ENVS={max_envs}). Close an existing environment first, '
        f'or raise DEEPRACER_MAX_ENVS.'
    )


def fingerprint(
        image: str,
        agent_config: dict,
        track_config: dict,
        evaluation: bool=False,
        world_name: str | None=None,
    ) -> str:
    '''Stable short hash identifying a reusable sim configuration (§4.11).

    Excludes the reward function (computed client-side) and per-instance identity
    (fresh each start). Two envs with the same fingerprint may reuse one warm
    container when cache=True.
    '''
    payload = {
        'image': image,
        'agent': agent_config,
        'track': track_config,
        'evaluation': bool(evaluation),
        'world': world_name,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(blob.encode()).hexdigest()[:16]
