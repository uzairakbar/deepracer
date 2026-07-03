"""Backend command-construction tests — no real Podman/Apptainer needed.

These lock the exact argv each CLI backend emits (the §9 hard constraints:
no --pwd, no config mount, explicit env, published port), so the PACE runtimes
are covered by shape even though the real run happens on PACE.
"""
from dataclasses import dataclass

import pytest

from deepracer_gym.service.spec import SimSpec, INTERNAL_PORT, LABEL_NS
from deepracer_gym.service.identity import make_identity
from deepracer_gym.service import backends as B


AGENT = {'action_space': [{'steering_angle': 0, 'speed': 0.6}],
         'sensor': ['STEREO_CAMERAS', 'LIDAR'], 'action_space_type': 'discrete'}
TRACK = {'WORLD_NAME': 'Austin', 'NUMBER_OF_OBSTACLES': '0'}


def make_spec(env_id=0, **kw):
    return SimSpec(identity=make_identity('alice', env_id),
                   agent_config=AGENT, track_config=TRACK, **kw)


# ---- pure argv --------------------------------------------------------------
def test_podman_argv_publishes_port_and_passes_env_and_labels():
    spec = make_spec()
    argv = B.podman_run_argv(spec)
    assert argv[:2] == ['podman', 'run']
    assert '--detach' in argv
    assert '-p' in argv
    i = argv.index('-p')
    assert argv[i + 1] == f'127.0.0.1:{spec.identity.port}:{INTERNAL_PORT}'
    # env + labels present; OCI binds the INTERNAL port inside (host maps to it)
    joined = ' '.join(argv)
    assert f'GYM_PORT={INTERNAL_PORT}' in joined
    assert 'DEEPRACER_AGENT_PARAMS=' in joined
    assert f'{LABEL_NS}.fingerprint={spec.fingerprint}' in joined
    assert argv[-1] == spec.image                       # image is last
    assert '--pwd' not in argv                           # never
    assert '-v' not in argv and '--volume' not in argv   # no mount


def test_apptainer_argv_no_pwd_no_mount_has_overlay_and_env():
    spec = make_spec(env_id=1)
    argv = B.apptainer_run_argv(spec)
    assert argv[:3] == ['apptainer', 'instance', 'run']
    assert '--pwd' not in argv                           # §9: PACE lacks it
    assert '--bind' not in argv                          # no config mount
    assert '--overlay' in argv
    assert spec.identity.overlay in argv
    # env passed explicitly as one --env CSV (host env is inherited, §9 c82707f)
    env_i = argv.index('--env')
    assert f'GYM_PORT={spec.identity.port}' in argv[env_i + 1]
    assert f'ROS_DOMAIN_ID={spec.identity.ros_domain_id}' in argv[env_i + 1]
    assert argv[-2:] == [spec.image, spec.identity.name]


# ---- CLI backends with an injected fake executor ----------------------------
@dataclass
class FakeResult:
    returncode: int = 0
    stdout: str = ''
    stderr: str = ''


class Recorder:
    """Stand-in for subprocess.run that records argv and returns canned output."""
    def __init__(self, outputs=None):
        self.calls = []
        self._outputs = outputs or {}

    def __call__(self, argv, capture_output=True, text=True, **kw):
        self.calls.append(argv)
        for key, res in self._outputs.items():
            if key in argv:
                return res
        return FakeResult(stdout='container-id-123\n')


def test_podman_backend_start_and_stop_argv():
    rec = Recorder()
    be = B.PodmanBackend(executor=rec)
    spec = make_spec()
    handle = be.start(spec)
    assert handle.name == spec.identity.name
    assert handle.port == spec.identity.port
    assert handle.id == 'container-id-123'
    # a leftover-clear (rm -f) then the run
    assert rec.calls[0][:3] == ['podman', 'rm', '-f']
    assert rec.calls[1][:2] == ['podman', 'run']
    be.stop(handle)
    assert rec.calls[-1] == ['podman', 'rm', '-f', spec.identity.name]


def test_podman_backend_start_raises_on_failure():
    rec = Recorder(outputs={'run': FakeResult(returncode=125, stderr='boom')})
    be = B.PodmanBackend(executor=rec)
    with pytest.raises(RuntimeError, match='podman run failed'):
        be.start(make_spec())


def test_podman_is_alive_parses_inspect():
    rec = Recorder(outputs={'inspect': FakeResult(stdout='true\n')})
    be = B.PodmanBackend(executor=rec)
    assert be.is_alive(make_spec_handle()) is True
    rec = Recorder(outputs={'inspect': FakeResult(stdout='false\n')})
    be = B.PodmanBackend(executor=rec)
    assert be.is_alive(make_spec_handle()) is False


def test_apptainer_backend_start_argv():
    rec = Recorder()
    be = B.ApptainerBackend(executor=rec)
    spec = make_spec(env_id=2)
    handle = be.start(spec)
    assert handle.name == spec.identity.name
    # stop-if-exists then instance run
    assert rec.calls[0][:3] == ['apptainer', 'instance', 'stop']
    assert rec.calls[1][:3] == ['apptainer', 'instance', 'run']


def make_spec_handle():
    spec = make_spec()
    return B.SimHandle(id='x', name=spec.identity.name, port=spec.identity.port,
                       backend='podman', fingerprint=spec.fingerprint, env_id=0)


def test_detect_backend_prefers_available(monkeypatch):
    monkeypatch.setattr(B.DockerBackend, 'available', staticmethod(lambda: False))
    monkeypatch.setattr(B.PodmanBackend, 'available', staticmethod(lambda: True))
    monkeypatch.setattr(B.PodmanBackend, '__init__', lambda self: None)
    be = B.detect_backend()
    assert be.name == 'podman'


def test_detect_backend_explicit_unavailable_raises(monkeypatch):
    monkeypatch.setattr(B.ApptainerBackend, 'available', staticmethod(lambda: False))
    with pytest.raises(RuntimeError, match='not available'):
        B.detect_backend(prefer='apptainer')
