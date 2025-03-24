import numpy as np
import gymnasium as gym
from gymnasium import spaces
from typing import TypeAlias
import matplotlib.pyplot as plt

from deepracer_gym.gym_adapter import DeepracerGymAdapter
from deepracer_gym.envs.utils import (
    make_action_space, make_observation_space, num_channels
)


PORT: int=8888
HOST: str='127.0.0.1'
ActionType: TypeAlias=(int | np.ndarray | list[float])

class DeepracerGymEnv(gym.Env):
    metadata = {
        'render_modes': ['rgb_array', 'human'],
        'render_fps': 30
    }
    def __init__(
            self,
            host: str=HOST,
            port: int=PORT,
            render_mode: str='rgb_array',
            **kwargs
        ):
        super().__init__(**kwargs)
        self.render_mode = render_mode
        self.action_space, self._action_metadata = make_action_space()
        self.observation_space, self._observation_metadata = make_observation_space()
        
        if isinstance(self.action_space, spaces.Discrete):
            action_space_type='discrete'
        elif isinstance(self.action_space, spaces.Box):
            action_space_type = 'continuous'
        self.deepracer_gym_adapter = DeepracerGymAdapter(
            action_space_type, host=host, port=port
        )
    
    def reset(self, **kwargs):
        super().reset(**kwargs)
        observation, info = self.deepracer_gym_adapter.env_reset()
        return observation, info
    
    def step(self, action: ActionType):
        observation, reward, terminated, truncated, info = (
            self.deepracer_gym_adapter.send_action(action)
        )
        return observation, reward, terminated, truncated, info
    
    def render(self, mode='rgb_array'):
        observation, _, _, _, _ = self.deepracer_gym_adapter._parse_response(
            self.deepracer_gym_adapter.response
        )
        measurement = None
        for sensor in observation:
            if 'CAMERA' in sensor:
                measurement = observation[sensor]
        
        if measurement is None:
            raise ValueError(
                f'Cannot render output of sensors {list(observation.keys())}.'
            )
        
        channels = num_channels(measurement)
        if channels == 2:
            # stereo camera
            measurement = np.hstack((
                measurement[0, :, :], measurement[1, :, :]
            ))
        
        channels = num_channels(measurement)
        if channels == 1:
            # greyscale image
            measurement = np.stack(
                3 * (measurement,), axis=-1
            )
        elif channels == 3:
            # front facing camera
            measurement = measurement.transpose(1, 2, 0)
        
        if mode == 'human':
            plt.imshow(np.asarray(measurement))
            plt.axis('off')
        elif mode == 'rgb_array':
            return np.asarray(measurement)
