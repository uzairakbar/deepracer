import json
from dataclasses import dataclass

from deepracer_gym.service.identity import Identity, fingerprint


# The pinned simulation image (kept as deepracer-test:v0, rebuilt in place while
# in testing — REFACTOR_DESIGN.md §8).
DEFAULT_IMAGE: str='uzairakbar/deepracer-test:v0'
# The container's internal ZMQ bind; OCI backends publish it to identity.port.
INTERNAL_PORT: int=8888
# Discovery-label namespace (docker/podman labels; used by cache + clean).
LABEL_NS: str='deepracer'


@dataclass
class SimSpec:
    '''Everything one sim needs to start — no files, all env-var transported.'''
    identity: Identity
    agent_config: dict
    track_config: dict
    image: str=DEFAULT_IMAGE
    cpus: float=3.0
    memory: str='6g'
    evaluation: bool=False
    world_name: str | None=None

    @property
    def fingerprint(self) -> str:
        return fingerprint(
            self.image, self.agent_config, self.track_config,
            self.evaluation, self.world_name,
        )


def spec_to_env(spec: SimSpec, gym_port: int | None=None) -> dict[str, str]:
    '''The env-var dict handed to a backend (§4.3). Specs travel as JSON; the
    entrypoint materializes /configs from these. Reward is NOT sent.

    `gym_port` is the port the sim binds *inside* the container: OCI backends
    (Docker/Podman) publish host:identity.port -> container:INTERNAL_PORT, so
    they pass `gym_port=INTERNAL_PORT`; Apptainer shares the host netns and binds
    identity.port directly (the default).'''
    env = {
        'GYM_PORT': str(gym_port if gym_port is not None else spec.identity.port),
        'ENV_ID': str(spec.identity.env_id),
        'ROS_DOMAIN_ID': str(spec.identity.ros_domain_id),
        'GZ_PARTITION': spec.identity.gz_partition,
        'DISPLAY': spec.identity.display,
        'DEEPRACER_AGENT_PARAMS': json.dumps(
            spec.agent_config, separators=(',', ':'), sort_keys=True
        ),
        'DEEPRACER_ENVIRONMENT_PARAMS': json.dumps(
            spec.track_config, separators=(',', ':'), sort_keys=True
        ),
    }
    if spec.evaluation:
        env['EVALUATION'] = 'true'
        if spec.world_name:
            env['EVAL_WORLD_NAME'] = spec.world_name
    return env


def spec_labels(spec: SimSpec) -> dict[str, str]:
    '''Discovery labels stamped on OCI containers so cache/clean can find them by
    querying the runtime (the runtime IS the registry, §4.11). Note: OCI labels
    are immutable after create, so there is no mutable idle/busy label — the
    manager tracks busy/idle in-process and probe-before-claims a discovered
    container (§4.11 safety valve).'''
    return {
        f'{LABEL_NS}.managed': 'true',
        f'{LABEL_NS}.fingerprint': spec.fingerprint,
        f'{LABEL_NS}.env_id': str(spec.identity.env_id),
    }
