"""Test harness for src/ utilities.

Unit tests are runtime-agnostic. The sim-backed smokes reuse the client's
lightweight ZMQ fake-sim image (deepracer/client/tests/fixtures/fakesim) so
demo()/evaluate_track() run end-to-end on real containers in seconds, and are
skipped cleanly where Docker is unavailable.
"""
import os
import pathlib

# headless-safe matplotlib before src.utils imports pyplot
os.environ.setdefault('MPLBACKEND', 'Agg')

import pytest


FAKE_IMAGE = 'deepracer-fake-sim:test'
FIXTURE_DIR = (
    pathlib.Path(__file__).resolve().parent.parent
    / 'deepracer' / 'client' / 'tests' / 'fixtures' / 'fakesim'
)


def _docker_available() -> bool:
    try:
        import docker
        docker.from_env().ping()
        return True
    except Exception:
        return False


requires_docker = pytest.mark.skipif(
    not _docker_available(), reason='Docker daemon not available',
)


@pytest.fixture(scope='session')
def fake_image():
    """Build the lightweight fake-sim image once per session."""
    import docker
    client = docker.from_env()
    client.images.build(path=str(FIXTURE_DIR), tag=FAKE_IMAGE, rm=True)
    return FAKE_IMAGE


@pytest.fixture
def sim_env(fake_image, monkeypatch):
    """Point the env at the fast fake-sim (via the env module's DEFAULT_IMAGE) and
    guarantee container cleanup after the test."""
    import deepracer_gym.envs.deepracer_gym as env_mod
    from deepracer_gym.service.manager import SimulationManager
    monkeypatch.setattr(env_mod, 'DEFAULT_IMAGE', fake_image)
    SimulationManager._instance = None
    yield
    import deepracer_gym
    try:
        deepracer_gym.shutdown_all()
    except Exception:
        pass
    SimulationManager._instance = None
