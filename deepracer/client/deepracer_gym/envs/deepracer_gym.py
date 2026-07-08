import os
import weakref
import numpy as np
import gymnasium as gym
from loguru import logger
from gymnasium import spaces
from typing import TypeAlias, Callable
import matplotlib.pyplot as plt

from deepracer_gym.gym_adapter import DeepracerGymAdapter
from deepracer_gym.envs.utils import (
    make_action_space,
    make_observation_space,
    num_channels,
)
from deepracer_gym.defaults import (
    default_reward_function, resolve_agent_config, resolve_track_config,
)
from deepracer_gym.service.spec import DEFAULT_IMAGE
# validate_configs is imported lazily in __init__ to avoid an import cycle
# (service.validate -> envs.utils -> envs.__init__ -> this module).


ActionType: TypeAlias=(int | np.ndarray | list[float])
HOST: str='127.0.0.1'
DEFAULT_PORT: int=8888


def _default_port() -> int:
    '''Port for the connect-only (manage_container=False) path: GYM_PORT env, else
    a per-user hash (back-compat with the bash scripts), else DEFAULT_PORT.'''
    if 'GYM_PORT' in os.environ:
        try:
            return int(os.environ['GYM_PORT'])
        except ValueError:
            pass
    try:
        from deepracer_gym.service.identity import string_to_port, current_user
        return string_to_port(current_user())
    except Exception:
        return DEFAULT_PORT


def _release(manager, handle, keep_warm):
    '''Module-level finalizer target (must not hold a ref to the env instance).
    Honors the env's cache flag: a forgotten close() / GC on a cache=True env
    keeps it warm (reaped at process exit by shutdown_all), else stops+removes.'''
    try:
        manager.release(handle, keep_warm=keep_warm)
    except Exception:
        pass


class DeepracerGymEnv(gym.Env):
    metadata = {
        'render_modes': ['rgb_array', 'human'],
        'render_fps': 30
    }
    def __init__(
            self,
            agent_config: dict | None=None,
            track_config: dict | None=None,
            reward_function: Callable | None=None,
            world_name: str | None=None,
            evaluation: bool=False,
            render_mode: str='rgb_array',
            image: str | None=None,
            cpus: float=3.0,
            memory: str='6g',
            cache: bool=False,
            manage_container: bool=True,
            host: str=HOST,
            port: int | None=None,
            **kwargs
        ):
        super().__init__(**kwargs)
        self.render_mode = render_mode

        agent_config = resolve_agent_config(agent_config)
        track_config = resolve_track_config(track_config)
        # Non-eval world_name replaces WORLD_NAME; eval mode passes EVAL_WORLD_NAME.
        if world_name and not evaluation:
            track_config = {**track_config, 'WORLD_NAME': world_name}
        from deepracer_gym.service.validate import validate_configs
        validate_configs(
            agent_config, track_config, world_name=world_name, evaluation=evaluation,
        )

        self.action_space, self._action_metadata = make_action_space(agent_config)
        self.observation_space, self._observation_metadata = make_observation_space(agent_config)
        self.reward_function = (
            reward_function if reward_function is not None
            else default_reward_function()
        )

        self._cache = cache
        self._manager = None
        self._handle = None
        self._finalizer = None
        self._closed = False

        if manage_container:
            from deepracer_gym.service.manager import SimulationManager
            self._manager = SimulationManager.instance()
            self._handle = self._manager.acquire(
                agent_config=agent_config, track_config=track_config,
                image=image or DEFAULT_IMAGE, cpus=cpus, memory=memory,
                evaluation=evaluation, world_name=world_name,
            )
            connect_port = self._handle.port
            # Safety net for a forgotten close(); the documented API is close().
            self._finalizer = weakref.finalize(
                self, _release, self._manager, self._handle, self._cache,
            )
        else:
            connect_port = port if port is not None else _default_port()

        logger.info(f'Using port {connect_port} for deepracer server.')

        if isinstance(self.action_space, spaces.Discrete):
            action_space_type='discrete'
        elif isinstance(self.action_space, spaces.Box):
            action_space_type = 'continuous'
        self.deepracer_gym_adapter = DeepracerGymAdapter(
            action_space_type, host=host, port=connect_port
        )
    
    def reset(self, **kwargs):
        super().reset(**kwargs)
        observation, info = self.deepracer_gym_adapter.env_reset()
        return observation, info
    
    def step(self, action: ActionType):
        assert self.action_space.contains(action), \
            f'Infeasible action. Action space does not containr {action}.'
        
        observation, terminated, truncated, info = (
            self.deepracer_gym_adapter.send_action(action)
        )
        reward = self.reward_function(info['reward_params'])
        return observation, reward, terminated, truncated, info
    
    def render(self, mode='rgb_array'):
        observation, _, _, _ = self.deepracer_gym_adapter._parse_response(
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

    def close(self, cache: bool | None=None):
        '''Close the ZMQ client and release the sim container. Idempotent.

        The container's fate is the env's `cache` flag (set at gym.make): with
        cache=True it is kept warm so a later env in *this same process* with a
        matching config re-attaches (faster boot); with cache=False (default) it
        is stopped and removed. A warm container does NOT survive process exit.
        Pass cache=… here only to override the constructor value at close time.

        Because `cache` is a constructor argument, gym.make forwards it, so a
        plain `env.close()` (through the gym.make wrapper) honors it — no
        `.unwrapped` needed. The override path still needs the unwrapped env:
        `deepracer_gym.close(env, cache=False)` or `env.unwrapped.close(cache=…)`.
        '''
        if self._closed:
            return
        self._closed = True
        try:
            self.deepracer_gym_adapter.zmq_client.socket.close()
        except Exception:
            pass
        if self._manager is not None and self._handle is not None:
            use_cache = self._cache if cache is None else cache
            if self._finalizer is not None:
                self._finalizer.detach()
            self._manager.release(self._handle, keep_warm=use_cache)
        super().close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
