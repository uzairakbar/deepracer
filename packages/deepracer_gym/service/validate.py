import difflib
import importlib.resources as resources

from deepracer_gym.envs.utils import (
    SENSOR_SPACE,
    action_space_type,
    validate_action_space_config,
)


# Sensors the client can actually build an observation space for (envs.utils
# marks SECTOR_LIDAR / LEFT_CAMERA as unimplemented -> None).
SUPPORTED_SENSORS: set[str]={
    name for name, space in SENSOR_SPACE.items() if space is not None
}
# DeepRacer race types accepted by the simulator (entrypoint default HEAD_TO_BOT).
RACE_TYPES: set[str]={
    'TIME_TRIAL', 'OBJECT_AVOIDANCE', 'HEAD_TO_BOT', 'HEAD_TO_MODEL',
}
# track_config keys expected to be non-negative integers (quoted-string form).
_INT_KEYS: tuple[str, ...]=('NUMBER_OF_OBSTACLES', 'NUMBER_OF_BOT_CARS')
# ... and floats.
_FLOAT_KEYS: tuple[str, ...]=(
    'LOWER_LANE_CHANGE_TIME', 'UPPER_LANE_CHANGE_TIME',
    'LANE_CHANGE_DISTANCE', 'MIN_DISTANCE_BETWEEN_BOT_CARS', 'BOT_CAR_SPEED',
)


def known_tracks() -> set[str]:
    '''The frozen list of loadable worlds (packaged copy of tracks.txt).'''
    text = resources.files('deepracer_gym.defaults').joinpath(
        'tracks.txt'
    ).read_text()
    return {line.strip() for line in text.splitlines() if line.strip()}


def _validate_world(world_name: str):
    tracks = known_tracks()
    if world_name in tracks:
        return
    suggestions = difflib.get_close_matches(world_name, tracks, n=3, cutoff=0.5)
    hint = f' Did you mean: {", ".join(suggestions)}?' if suggestions else ''
    raise ValueError(
        f'Unknown WORLD_NAME {world_name!r}.{hint} '
        f'See deepracer_gym/defaults/tracks.txt for the full list.'
    )


def _validate_sensors(agent_config: dict):
    sensors = agent_config.get('sensor')
    if not isinstance(sensors, list) or not sensors:
        raise ValueError(
            f"agent_config['sensor'] must be a non-empty list, got {sensors!r}."
        )
    for sensor in sensors:
        if sensor not in SUPPORTED_SENSORS:
            raise ValueError(
                f'Unsupported sensor {sensor!r}. '
                f'Supported: {sorted(SUPPORTED_SENSORS)}.'
            )
    cameras = [s for s in sensors if 'CAMERA' in s]
    if len(cameras) > 1:
        raise ValueError(
            f'At most one camera sensor is allowed, got {cameras}.'
        )
    if sensors == ['LIDAR']:
        raise ValueError(
            'LIDAR cannot be the only sensor; pair it with a camera.'
        )


def _validate_track(track_config: dict, world_name: str):
    _validate_world(world_name)
    for key in _INT_KEYS:
        if key in track_config:
            try:
                value = int(str(track_config[key]))
            except (TypeError, ValueError):
                raise ValueError(f'{key} must be an integer, got {track_config[key]!r}.')
            if value < 0:
                raise ValueError(f'{key} must be >= 0, got {value}.')
    for key in _FLOAT_KEYS:
        if key in track_config:
            try:
                float(str(track_config[key]))
            except (TypeError, ValueError):
                raise ValueError(f'{key} must be a number, got {track_config[key]!r}.')
    if 'RACE_TYPE' in track_config and track_config['RACE_TYPE'] not in RACE_TYPES:
        raise ValueError(
            f'Unknown RACE_TYPE {track_config["RACE_TYPE"]!r}. '
            f'Allowed: {sorted(RACE_TYPES)}.'
        )


def effective_world(
        track_config: dict,
        world_name: str | None,
        evaluation: bool,
    ) -> str:
    '''The world the simulator will actually load (mirrors entrypoint EVAL_MODE).

    Eval mode uses EVAL_WORLD_NAME (the world_name arg); otherwise the
    track_config WORLD_NAME. The world_name arg also overrides WORLD_NAME in the
    non-eval case (§4.6 routing).
    '''
    if evaluation and world_name:
        return world_name
    if world_name:
        return world_name
    world = track_config.get('WORLD_NAME')
    if not world:
        raise ValueError(
            "No world specified: set track_config['WORLD_NAME'] or pass world_name=."
        )
    return world


def validate_configs(
        agent_config: dict,
        track_config: dict,
        world_name: str | None=None,
        evaluation: bool=False,
    ):
    '''Client-side, pre-launch validation. Raises ValueError with an actionable
    message so a bad config fails in milliseconds instead of silently crashing
    the sim after a ~1 min boot (§4.8).'''
    # action space (reuse the existing validators)
    if 'action_space' not in agent_config:
        raise ValueError("agent_config must define 'action_space'.")
    validate_action_space_config(agent_config, action_space_type(agent_config))
    _validate_sensors(agent_config)
    _validate_track(track_config, effective_world(track_config, world_name, evaluation))
