import pathlib

import pytest


FAKE_IMAGE = 'deepracer-fake-sim:test'
FIXTURE_DIR = pathlib.Path(__file__).parent / 'fixtures' / 'fakesim'


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
    """Build the lightweight fake-sim image once per test session."""
    import docker
    client = docker.from_env()
    client.images.build(path=str(FIXTURE_DIR), tag=FAKE_IMAGE, rm=True)
    return FAKE_IMAGE


@pytest.fixture
def docker_backend():
    from deepracer.service.backends import DockerBackend
    return DockerBackend()


@pytest.fixture
def cleanup_managed():
    """Remove any leftover deepracer-* fake containers after a test."""
    yield
    try:
        import docker
        client = docker.from_env()
        for c in client.containers.list(all=True,
                                        filters={'label': 'deepracer.managed=true'}):
            try:
                c.remove(force=True)
            except Exception:
                pass
    except Exception:
        pass
