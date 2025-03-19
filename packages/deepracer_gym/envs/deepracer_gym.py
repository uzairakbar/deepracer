import json
import numpy as np
import gymnasium as gym
from gymnasium import spaces
import matplotlib.pyplot as plt
from deepracer_gym.envs.utils import (
    make_action_space, make_observation_space
)
from deepracer_gym.gym_adapter import DeepracerGymAdapter


PORT: int=8888
HOST: str='127.0.0.1'


class DeepracerGymEnv(gym.Env):
    metadata = {
        'render_modes': ['rgb_array', 'human']
    }
    def __init__(
            self, port: str=PORT, render_mode='rgb_array', **kwargs
        ):
        self.action_space = make_action_space()
        self.observation_space = make_observation_space()
        self.deepracer_gym_adapter = DeepracerGymAdapter(port=port)
        self.render_mode = render_mode

    def reset(self, **kwargs):
        observation, info = self.deepracer_gym_adapter.env_reset()
        return observation, info
    
    def step(self, action: int):
        observation, reward, terminated, truncated, info = (
            self.deepracer_gym_adapter.send_action(action)
        )
        return observation, reward, terminated, truncated, info
    
    def render(self, mode='rgb_array', close=False):
        observation, _, _, _, _ = self.deepracer_gym_adapter._parse_response(
            self.deepracer_gym_adapter.response
        )
        stereo = observation["STEREO_CAMERAS"]
        stereo = np.hstack((stereo[:, :, 0], stereo[:, :, 1]))

        im = np.stack(
            3 * (stereo,), axis=-1
        )
        if mode == 'human':
            plt.imshow(np.asarray(im))
            plt.axis('off')
        elif mode == 'rgb_array':
            return np.asarray(im)
