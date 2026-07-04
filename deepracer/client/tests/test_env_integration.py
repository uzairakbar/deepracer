"""Full client path on real Docker: gym env -> manager -> container -> ZMQ.

Exercises DeepracerGymEnv.__init__/reset/step/close wired to SimulationManager,
against the ZMQ fake-sim (real container, real msgpack protocol). The heavy sim
only adds Gazebo boot; the whole client integration is proven here.
"""
import numpy as np
import pytest

from tests.conftest import requires_docker


AGENT = {
    'action_space': [{'steering_angle': 30, 'speed': 0.6},
                     {'steering_angle': 0, 'speed': 0.6},
                     {'steering_angle': -30, 'speed': 0.6}],
    'sensor': ['STEREO_CAMERAS', 'LIDAR'],
    'action_space_type': 'discrete', 'version': '6',
}
TRACK = {'WORLD_NAME': 'reInvent2019_track', 'NUMBER_OF_OBSTACLES': '0'}

pytestmark = requires_docker
SMALL = dict(image=None, cpus=1.0, memory='512m')   # image filled per-test


@pytest.fixture
def fake_manager(docker_backend):
    """Install a test SimulationManager as the process singleton."""
    from deepracer_gym.service.manager import SimulationManager
    mgr = SimulationManager(backend=docker_backend, user='pytest-env',
                            ready_timeout=45, max_envs=4)
    SimulationManager._instance = mgr
    yield mgr
    mgr.shutdown_all(include_cached=True)
    SimulationManager._instance = None


def _env(fake_image, **kw):
    from deepracer_gym.envs.deepracer_gym import DeepracerGymEnv
    opts = dict(agent_config=AGENT, track_config=TRACK, image=fake_image,
                cpus=1.0, memory='512m')
    opts.update(kw)
    return DeepracerGymEnv(**opts)


def test_make_reset_step_close(fake_image, fake_manager):
    env = _env(fake_image)
    try:
        obs, info = env.reset()
        assert set(obs.keys()) == {'STEREO_CAMERAS', 'LIDAR'}
        assert obs['STEREO_CAMERAS'].shape == (2, 120, 160)   # C, H, W (transposed)
        assert obs['LIDAR'].shape == (64,)
        assert env.action_space.n == 3

        action = env.action_space.sample()
        obs, reward, terminated, truncated, info = env.step(action)
        assert isinstance(reward, float)
        assert 'reward_params' in info and 'episode_status' in info
        assert terminated is False and truncated is False
    finally:
        env.close()
    # container released
    assert fake_manager._live == {}


def test_context_manager_closes(fake_image, fake_manager):
    with _env(fake_image) as env:
        env.reset()
        assert fake_manager._live != {}
    assert fake_manager._live == {}


def test_env_cache_reuses_container(fake_image, fake_manager):
    env1 = _env(fake_image, cache=True)
    handle_name = env1._handle.name
    env1.reset()
    env1.close()                                  # cache=True default -> stays warm
    assert fake_manager.backend.is_alive(env1._handle)

    env2 = _env(fake_image, cache=True)
    try:
        assert env2._handle.name == handle_name   # re-attached the warm container
        env2.reset()
    finally:
        env2.close(cache=False)                    # force-stop
    assert not fake_manager.backend.is_alive(env2._handle)


def test_manage_container_false_starts_nothing(fake_image, fake_manager):
    # connect-only: no container provisioned (attaches to a pre-started sim/port).
    env = _env(fake_image, manage_container=False, port=59999)
    try:
        assert env._handle is None
        assert fake_manager._live == {}
    finally:
        env.close()


def test_gym_make_wrapped_close_and_cache_override(fake_image, fake_manager):
    # gym.make wraps the env; plain close() must work through wrappers, and the
    # cache override must go via the deepracer_gym.close helper (kwargs don't
    # forward through gymnasium Wrapper.close).
    import gymnasium as gym
    import deepracer_gym

    env = gym.make('deepracer-v0', agent_config=AGENT, track_config=TRACK,
                   image=fake_image, cpus=1.0, memory='512m', cache=True)
    handle = env.unwrapped._handle
    env.reset()
    # wrapped close(cache=...) raises (documented limitation)
    with pytest.raises(TypeError):
        env.close(cache=False)
    # helper overrides correctly -> container stopped despite cache=True default
    deepracer_gym.close(env, cache=False)
    assert not fake_manager.backend.is_alive(handle)


def test_shutdown_all_reaps_cached(fake_image, fake_manager):
    import gymnasium as gym
    import deepracer_gym

    env = gym.make('deepracer-v0', agent_config=AGENT, track_config=TRACK,
                   image=fake_image, cpus=1.0, memory='512m', cache=True)
    handle = env.unwrapped._handle
    env.reset()
    env.close()                                  # plain close keeps it warm
    assert fake_manager.backend.is_alive(handle)
    deepracer_gym.shutdown_all()                 # reclaim warm containers
    assert not fake_manager.backend.is_alive(handle)


def test_invalid_world_fails_before_container(fake_image, fake_manager):
    from deepracer_gym.envs.deepracer_gym import DeepracerGymEnv
    with pytest.raises(ValueError, match='Unknown WORLD_NAME'):
        DeepracerGymEnv(agent_config=AGENT,
                        track_config={'WORLD_NAME': 'nope_zzz_typo'},
                        image=fake_image)
    assert fake_manager._live == {}               # nothing started
