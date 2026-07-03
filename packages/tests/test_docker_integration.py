"""End-to-end container-management tests on REAL Docker via the fake-sim image.

These prove the backend + manager + ports + labels + cache + concurrency work
against a live runtime. The heavy amd64 sim only adds Gazebo boot time (validated
on PACE); every lifecycle mechanism our code owns is exercised here for real.
"""
import json

import pytest

from tests.conftest import requires_docker
from deepracer_gym.service.manager import SimulationManager


AGENT = {
    'action_space': [{'steering_angle': 30, 'speed': 0.6},
                     {'steering_angle': -30, 'speed': 0.6}],
    'sensor': ['STEREO_CAMERAS', 'LIDAR'],
    'action_space_type': 'discrete', 'version': '6',
}
TRACK = {'WORLD_NAME': 'reInvent2019_track', 'NUMBER_OF_OBSTACLES': '0'}

pytestmark = requires_docker
SMALL = dict(cpus=1.0, memory='256m')


def _mgr(docker_backend, user, **kw):
    return SimulationManager(backend=docker_backend, user=user, ready_timeout=30, **kw)


def _exec(handle, backend, cmd):
    return backend._get(handle).exec_run(cmd).output.decode()


def test_start_alive_logs_materialize_stop(fake_image, docker_backend, cleanup_managed):
    mgr = _mgr(docker_backend, 'pytest-life')
    handle = mgr.acquire(agent_config=AGENT, track_config=TRACK, image=fake_image, **SMALL)
    try:
        assert docker_backend.is_alive(handle)
        assert 'Waiting for gym client' in docker_backend.logs(handle)
        # config was materialized inside the container from env vars (no mount)
        got_agent = json.loads(_exec(handle, docker_backend, 'cat /configs/agent_params.json'))
        assert got_agent == AGENT
        got_track = _exec(handle, docker_backend, 'cat /configs/environment_params.yaml')
        assert json.loads(got_track) == TRACK
        # GYM_PORT inside is the INTERNAL port; host maps identity.port -> it
        gym_port = _exec(handle, docker_backend, ['printenv', 'GYM_PORT']).strip()
        assert gym_port == '8888'
    finally:
        mgr.release(handle, cache=False)
    assert not docker_backend.is_alive(handle)


def test_no_bind_mount_present(fake_image, docker_backend, cleanup_managed):
    mgr = _mgr(docker_backend, 'pytest-mount')
    handle = mgr.acquire(agent_config=AGENT, track_config=TRACK, image=fake_image, **SMALL)
    try:
        mounts = docker_backend._get(handle).attrs['Mounts']
        assert mounts == []          # config travels as env vars, not a mount
    finally:
        mgr.release(handle, cache=False)


def test_concurrent_distinct_configs_and_cap(fake_image, docker_backend, cleanup_managed):
    mgr = _mgr(docker_backend, 'pytest-cap', max_envs=2)
    handles = []
    try:
        for world in ('reInvent2019_track', 'Austin'):
            handles.append(mgr.acquire(
                agent_config=AGENT, track_config={'WORLD_NAME': world},
                image=fake_image, **SMALL))
        # two independent, alive, on distinct host ports
        assert all(docker_backend.is_alive(h) for h in handles)
        assert len({h.port for h in handles}) == 2
        assert len({h.name for h in handles}) == 2
        # third exceeds MAX_ENVS=2 -> clear error
        with pytest.raises(RuntimeError, match='slots are in use'):
            mgr.acquire(agent_config=AGENT, track_config={'WORLD_NAME': 'Monaco'},
                        image=fake_image, **SMALL)
    finally:
        for h in handles:
            mgr.release(h, cache=False)


def test_cache_reuses_warm_container(fake_image, docker_backend, cleanup_managed):
    mgr = _mgr(docker_backend, 'pytest-cache')
    h1 = mgr.acquire(agent_config=AGENT, track_config=TRACK, image=fake_image,
                     cache=True, **SMALL)
    name1, port1 = h1.name, h1.port
    # release WITH cache -> container stays alive
    mgr.release(h1, cache=True)
    assert docker_backend.is_alive(h1)
    # re-acquire same config -> the SAME warm container, no new start
    h2 = mgr.acquire(agent_config=AGENT, track_config=TRACK, image=fake_image,
                     cache=True, **SMALL)
    try:
        assert h2.name == name1 and h2.port == port1
    finally:
        mgr.release(h2, cache=False)     # force-stop
    assert not docker_backend.is_alive(h2)


def test_cache_different_config_starts_fresh(fake_image, docker_backend, cleanup_managed):
    mgr = _mgr(docker_backend, 'pytest-cache2')
    h1 = mgr.acquire(agent_config=AGENT, track_config={'WORLD_NAME': 'Austin'},
                     image=fake_image, cache=True, **SMALL)
    mgr.release(h1, cache=True)
    h2 = mgr.acquire(agent_config=AGENT, track_config={'WORLD_NAME': 'Monaco'},
                     image=fake_image, cache=True, **SMALL)
    try:
        assert h2.name != h1.name         # different fingerprint -> different container
    finally:
        mgr.shutdown_all(include_cached=True)
    assert not docker_backend.is_alive(h1)
    assert not docker_backend.is_alive(h2)


def test_readiness_surfaces_fatal_on_crash(fake_image, docker_backend, cleanup_managed,
                                           monkeypatch):
    # FAKE_CRASH makes the container exit 1 with a FATAL line; acquire must raise
    # with that line instead of hanging on the readiness timeout.
    mgr = _mgr(docker_backend, 'pytest-crash')

    import deepracer_gym.service.backends as backends_mod
    orig = backends_mod.spec_to_env

    def crashing_env(spec, gym_port=None):
        env = orig(spec, gym_port=gym_port)
        env['FAKE_CRASH'] = '1'
        return env
    monkeypatch.setattr(backends_mod, 'spec_to_env', crashing_env)

    with pytest.raises(RuntimeError, match='FATAL'):
        mgr.acquire(agent_config=AGENT, track_config=TRACK, image=fake_image, **SMALL)
