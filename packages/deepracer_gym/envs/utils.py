import json
import numpy as np
from gymnasium import spaces


LIDAR_SHAPE: tuple[int, ...]=(64,)
CAMERA_SHAPE: tuple[int, ...]=(120, 160)                        # H x W
STEREO_CAMERA_SHAPE: tuple[int, ...]=(2,)+CAMERA_SHAPE          # C x H x W
FRONT_FACING_CAMERA_SHAPE: tuple[int, ...]=(3,)+CAMERA_SHAPE    # C x H x W
SENSOR_SPACE: dict[str, spaces.Box]={
    'LIDAR': spaces.Box(
        low=0.15, high=float('inf'), shape=LIDAR_SHAPE, dtype=np.float64
    ),
    'STEREO_CAMERAS': spaces.Box(
        low=0, high=255, shape=STEREO_CAMERA_SHAPE, dtype=np.uint8
    ),
    'FRONT_FACING_CAMERA': spaces.Box(
        low=0, high=255, shape=FRONT_FACING_CAMERA_SHAPE, dtype=np.uint8
    ),
    # TODO: Look into implementing these!
    'SECTOR_LIDAR': None,
    'LEFT_CAMERA': None
}


def make_action_space(config_path: str='configs/model_metadata.json'):
    with open(config_path, 'r') as file:
        config = json.load(file)
    _action_space: list[dict[str, float]]=config['action_space']
    if 'action_space_type' in config:
        if config['action_space_type'] == 'discrete':
            action_space = spaces.Discrete(
                len(_action_space)
            )
        elif config['action_space_type'] == 'continuous':
            raise NotImplementedError
        else:
            raise NotImplementedError
    else:
        if isinstance(_action_space, list):
            # assuming discrete
            action_space = spaces.Discrete(
                len(_action_space)
            )
        elif isinstance(_action_space, dict):
            # assuming continuous
            raise NotImplementedError
        else:
            raise NotImplementedError
    
    return action_space, _action_space


def make_observation_space(config_path: str='configs/model_metadata.json'):
    with open(config_path, 'r') as file:
        config = json.load(file)
    sensors: list[str]=config['sensor']
    
    for sensor in sensors:
        assert (
            (sensor in SENSOR_SPACE) 
            and 
            (SENSOR_SPACE[sensor] is not None)
        ), f'Sensor {sensor} not supported!'

    return spaces.Dict({
        sensor: SENSOR_SPACE[sensor] for sensor in sensors
    }), sensors


def num_channels(measurement: np.array):
    dimensions = len(measurement.shape)
    if dimensions == 2:
        channels = 1
    elif dimensions == 3:
        channels = measurement.shape[0]
    return channels