"""Backend command-construction tests for CLI runtimes."""

from dataclasses import dataclass

import pytest
from deepracer.service import backends as B
from deepracer.service.identity import make_identity
from deepracer.service.spec import INTERNAL_PORT, LABEL_NS, SimSpec

AGENT = {
    "action_space": [{"steering_angle": 0, "speed": 0.6}],
    "sensor": ["STEREO_CAMERAS", "LIDAR"],
    "action_space_type": "discrete",
}
TRACK = {"WORLD_NAME": "Austin", "NUMBER_OF_OBSTACLES": "0"}


def make_spec(env_id=0, **kw):
    return SimSpec(
        identity=make_identity("alice", env_id),
        agent_config=AGENT,
        track_config=TRACK,
        **kw,
    )


def test_podman_argv_publishes_port_and_passes_env_and_labels():
    spec = make_spec()
    argv = B.podman_run_argv(spec)
    assert argv[:2] == ["podman", "run"]
    assert "--detach" in argv
    assert "-p" in argv
    i = argv.index("-p")
    assert argv[i + 1] == f"127.0.0.1:{spec.identity.port}:{INTERNAL_PORT}"
    # env + labels present; OCI binds the INTERNAL port inside (host maps to it)
    joined = " ".join(argv)
    assert f"GYM_PORT={INTERNAL_PORT}" in joined
    assert "DEEPRACER_AGENT_PARAMS=" in joined
    assert f"{LABEL_NS}.fingerprint={spec.fingerprint}" in joined
    # image is last, and a bare short name is docker.io-qualified so Podman's
    # enforcing short-name-mode cannot stall on a no-TTY registry prompt.
    assert argv[-1] == B.qualify_image(spec.image)
    assert "--pwd" not in argv
    assert "-v" not in argv and "--volume" not in argv  # no mount


def test_qualify_image_only_touches_bare_short_names():
    # bare short name -> docker.io-qualified (Podman enforcing short-name-mode)
    assert (
        B.qualify_image("someuser/some-image:v0")
        == "docker.io/someuser/some-image:v0"
    )
    assert B.qualify_image("alpine") == "docker.io/alpine"
    # already-qualified / local / non-docker refs are left alone
    assert (
        B.qualify_image("ghcr.io/uzairakbar/deepracer:v0")
        == "ghcr.io/uzairakbar/deepracer:v0"
    )
    assert B.qualify_image("docker.io/uzairakbar/x:v0") == "docker.io/uzairakbar/x:v0"
    assert (
        B.qualify_image("registry.example.com:5000/x:v0")
        == "registry.example.com:5000/x:v0"
    )
    assert B.qualify_image("localhost/x:v0") == "localhost/x:v0"
    assert B.qualify_image("quay.io/org/x") == "quay.io/org/x"
    assert B.qualify_image("/scratch/deepracer.sif") == "/scratch/deepracer.sif"
    assert B.qualify_image("docker://uzairakbar/x:v0") == "docker://uzairakbar/x:v0"


def test_apptainer_argv_no_pwd_no_mount_no_env_in_argv():
    spec = make_spec(env_id=1)
    argv = B.apptainer_run_argv(spec, sif="/scratch/deepracer.sif")
    assert argv[:3] == ["apptainer", "instance", "run"]
    assert "--pwd" not in argv
    assert "--bind" not in argv  # no config mount
    assert "--env" not in argv  # env goes via APPTAINERENV_*
    assert "--overlay" in argv
    assert spec.identity.overlay in argv
    assert argv[-2:] == ["/scratch/deepracer.sif", spec.identity.name]


def test_apptainer_env_uses_prefix_and_keeps_json_intact():
    spec = make_spec(env_id=1)
    env = B.apptainer_env(spec)
    # each container var is exported prefixed; apptainer strips APPTAINERENV_
    assert env["APPTAINERENV_GYM_PORT"] == str(spec.identity.port)
    assert env["APPTAINERENV_ROS_DOMAIN_ID"] == str(spec.identity.ros_domain_id)
    # the JSON config (which contains commas) survives verbatim — the reason we
    # avoid a single --env CSV
    payload = env["APPTAINERENV_DEEPRACER_AGENT_PARAMS"]
    import json as _json

    assert _json.loads(payload) == AGENT
    assert "," in payload  # would break a CSV --env


def test_resolve_sif_passes_through_sif_and_pulls_docker(monkeypatch, tmp_path):
    rec = Recorder()
    be = B.ApptainerBackend(executor=rec)
    # a .sif path is used as-is (no pull)
    assert be._resolve_sif("/some/path/x.sif") == "/some/path/x.sif"
    assert rec.calls == []
    # a docker name is pulled once to a cached sif under scratch
    monkeypatch.setattr(be, "_scratch", lambda: str(tmp_path))
    sif = be._resolve_sif("ghcr.io/uzairakbar/deepracer:v0")
    assert sif.startswith(str(tmp_path)) and sif.endswith(".sif")
    assert rec.calls[0][:3] == ["apptainer", "pull", "--force"]
    assert rec.calls[0][-1] == "docker://ghcr.io/uzairakbar/deepracer:v0"


def test_apptainer_backend_start_uses_sif_and_apptainerenv(monkeypatch):
    rec = Recorder()
    be = B.ApptainerBackend(executor=rec)
    monkeypatch.setattr(B.os, "makedirs", lambda *a, **k: None)  # no real overlay
    spec = make_spec(env_id=2, image="/scratch/deepracer.sif")  # .sif -> no pull
    handle = be.start(spec)
    assert handle.name == spec.identity.name
    assert handle.overlay == spec.identity.overlay
    # No listed instance means start without a stop call. An unconditional
    # stop-before-run can race with a fresh instance.
    assert rec.calls[0][:4] == ["apptainer", "instance", "list", "--json"]
    assert rec.calls[1][:3] == ["apptainer", "instance", "run"]
    assert rec.calls[1][-2:] == ["/scratch/deepracer.sif", spec.identity.name]
    assert all(call[:3] != ["apptainer", "instance", "stop"] for call in rec.calls)


def test_apptainer_backend_start_stops_a_genuinely_stale_instance(monkeypatch):
    spec = make_spec(env_id=2, image="/scratch/deepracer.sif")
    listing = FakeResult(
        stdout=f'{{"instances": [{{"instance": "{spec.identity.name}"}}]}}'
    )
    rec = Recorder(outputs={"--json": listing})
    be = B.ApptainerBackend(executor=rec)
    monkeypatch.setattr(B.os, "makedirs", lambda *a, **k: None)
    be.start(spec)
    # instance IS listed as already present -> stop it before the fresh run
    assert rec.calls[0][:4] == ["apptainer", "instance", "list", "--json"]
    assert rec.calls[1][:3] == ["apptainer", "instance", "stop"]
    assert rec.calls[2][:3] == ["apptainer", "instance", "run"]


def test_apptainer_backend_start_clears_stale_logs(monkeypatch):
    # Apptainer appends to per-name logs, so stale FATAL lines must be removed.
    spec = make_spec(env_id=2, image="/scratch/deepracer.sif")
    rec = Recorder()
    be = B.ApptainerBackend(executor=rec)
    monkeypatch.setattr(B.os, "makedirs", lambda *a, **k: None)
    stale = [f"/logs/{spec.identity.name}.out", f"/logs/{spec.identity.name}.err"]
    monkeypatch.setattr(be, "_log_paths", lambda name: stale)
    removed = []
    monkeypatch.setattr(B.os, "remove", lambda p: removed.append(p))
    be.start(spec)
    assert removed == stale  # both stale logs cleared


def test_detect_backend_env_override(monkeypatch):
    monkeypatch.setenv("DEEPRACER_BACKEND", "apptainer")
    monkeypatch.setattr(B.ApptainerBackend, "available", staticmethod(lambda: True))
    monkeypatch.setattr(B.ApptainerBackend, "__init__", lambda self: None)
    assert B.detect_backend().name == "apptainer"


@dataclass
class FakeResult:
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""


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
        return FakeResult(stdout="container-id-123\n")


def test_podman_backend_start_and_stop_argv():
    rec = Recorder()
    be = B.PodmanBackend(executor=rec)
    spec = make_spec()
    handle = be.start(spec)
    assert handle.name == spec.identity.name
    assert handle.port == spec.identity.port
    assert handle.id == "container-id-123"
    # a leftover-clear (rm -f), an image-presence probe, then the run
    assert rec.calls[0][:3] == ["podman", "rm", "-f"]
    assert rec.calls[1][:3] == ["podman", "image", "exists"]
    assert rec.calls[2][:2] == ["podman", "run"]
    be.stop(handle)
    assert rec.calls[-1] == ["podman", "rm", "-f", spec.identity.name]


def test_podman_backend_start_raises_on_failure():
    rec = Recorder(outputs={"run": FakeResult(returncode=125, stderr="boom")})
    be = B.PodmanBackend(executor=rec)
    with pytest.raises(RuntimeError, match="podman run failed"):
        be.start(make_spec())


def test_podman_is_alive_parses_inspect():
    rec = Recorder(outputs={"inspect": FakeResult(stdout="true\n")})
    be = B.PodmanBackend(executor=rec)
    assert be.is_alive(make_spec_handle()) is True
    rec = Recorder(outputs={"inspect": FakeResult(stdout="false\n")})
    be = B.PodmanBackend(executor=rec)
    assert be.is_alive(make_spec_handle()) is False


def test_podman_managed_containers_filters_by_managed_label():
    # the startup-hint query: list managed deepracer containers by name
    rec = Recorder(
        outputs={"ps": FakeResult(stdout="deepracer-alice-0\ndeepracer-alice-1\n")}
    )
    be = B.PodmanBackend(executor=rec)
    names = be.managed_containers()
    assert names == ["deepracer-alice-0", "deepracer-alice-1"]
    argv = rec.calls[-1]
    assert argv[:3] == ["podman", "ps", "--filter"]
    assert f"label={LABEL_NS}.managed=true" in argv
    # empty output -> no names, no crash
    rec = Recorder(outputs={"ps": FakeResult(stdout="")})
    assert B.PodmanBackend(executor=rec).managed_containers() == []


def _capture_info(fn):
    """Run fn() while capturing loguru INFO messages; returns the message list."""
    from loguru import logger

    msgs = []
    sink = logger.add(lambda m: msgs.append(str(m)), level="INFO", format="{message}")
    try:
        fn()
    finally:
        logger.remove(sink)
    return msgs


def test_podman_pull_hint_only_when_image_absent():
    # absent (image exists -> rc!=0) => hint, and it probes with `image exists`
    rec = Recorder(outputs={"exists": FakeResult(returncode=1)})
    be = B.PodmanBackend(executor=rec)
    msgs = _capture_info(lambda: be._log_if_pulling("docker.io/x:v0"))
    assert any("Pulling simulator image" in m for m in msgs)
    assert rec.calls[-1][:3] == ["podman", "image", "exists"]
    # present (rc==0) => no hint
    rec = Recorder(outputs={"exists": FakeResult(returncode=0)})
    be = B.PodmanBackend(executor=rec)
    msgs = _capture_info(lambda: be._log_if_pulling("docker.io/x:v0"))
    assert not any("Pulling simulator image" in m for m in msgs)


def test_docker_pull_hint_only_when_image_absent():
    import docker

    class FakeImages:
        def __init__(self, present):
            self._present = present

        def get(self, image):
            if not self._present:
                raise docker.errors.ImageNotFound(image)
            return object()

    class FakeClient:
        def __init__(self, present):
            self.images = FakeImages(present)

    be = B.DockerBackend(client=FakeClient(present=False))
    msgs = _capture_info(lambda: be._log_if_pulling("x:v0"))
    assert any("Pulling simulator image" in m for m in msgs)

    be = B.DockerBackend(client=FakeClient(present=True))
    msgs = _capture_info(lambda: be._log_if_pulling("x:v0"))
    assert not any("Pulling simulator image" in m for m in msgs)


def make_spec_handle():
    spec = make_spec()
    return B.SimHandle(
        id="x",
        name=spec.identity.name,
        port=spec.identity.port,
        backend="podman",
        fingerprint=spec.fingerprint,
        env_id=0,
    )


def test_detect_backend_prefers_available(monkeypatch):
    monkeypatch.setattr(B.DockerBackend, "available", staticmethod(lambda: False))
    monkeypatch.setattr(B.PodmanBackend, "available", staticmethod(lambda: True))
    monkeypatch.setattr(B.PodmanBackend, "__init__", lambda self: None)
    be = B.detect_backend()
    assert be.name == "podman"


def test_detect_backend_explicit_unavailable_raises(monkeypatch):
    monkeypatch.setattr(B.ApptainerBackend, "available", staticmethod(lambda: False))
    with pytest.raises(RuntimeError, match="not available"):
        B.detect_backend(prefer="apptainer")
