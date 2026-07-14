import socket

import pytest
from deepracer.service.identity import (
    DISPLAY_BASE,
    PORT_HI,
    PORT_LO,
    fingerprint,
    make_identity,
    port_is_free,
    string_to_port,
)


def test_string_to_port_deterministic_and_in_band():
    for s in ("alice_0", "bob_3", "x"):
        p = string_to_port(s)
        assert p == string_to_port(s)  # deterministic
        assert PORT_LO <= p <= PORT_HI  # unprivileged band


def test_identity_fields_derive_from_seed():
    ident = make_identity("alice", 2)
    assert ident.name == "deepracer-alice-2"
    assert ident.port == string_to_port("alice_2")
    assert 1 <= ident.ros_domain_id <= 101
    assert ident.gz_partition == "alice_2"
    assert ident.display == f":{DISPLAY_BASE + 2}"
    assert ident.overlay == "/tmp/deepracer_alice_2"


def test_distinct_env_ids_get_distinct_ports_and_displays():
    ids = [make_identity("alice", i) for i in range(4)]
    assert len({i.port for i in ids}) == 4  # no port collisions
    assert len({i.display for i in ids}) == 4  # no Xvfb/TCP-6000 collision
    assert len({i.overlay for i in ids}) == 4


def test_different_users_separate_ports():
    assert make_identity("alice", 0).port != make_identity("bob", 0).port


def test_port_is_free_detects_a_live_listener():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    s.listen(1)
    busy = s.getsockname()[1]
    try:
        assert port_is_free(busy) is False
    finally:
        s.close()
    # after close the port is free again (may race, but overwhelmingly true)
    assert port_is_free(busy) is True


def test_free_env_id_skips_taken_and_busy(monkeypatch):
    # env_id 0 and 1 "busy" via monkeypatched probe; 2 free.
    import deepracer.service.identity as idm

    busy_ports = {make_identity("u", 0).port, make_identity("u", 1).port}
    monkeypatch.setattr(
        idm, "port_is_free", lambda p, host="127.0.0.1": p not in busy_ports
    )
    got = idm.free_env_id("u", max_envs=4)
    assert got.env_id == 2


def test_free_env_id_respects_taken_set(monkeypatch):
    import deepracer.service.identity as idm

    monkeypatch.setattr(idm, "port_is_free", lambda p, host="127.0.0.1": True)
    got = idm.free_env_id("u", max_envs=4, taken={0, 1})
    assert got.env_id == 2


def test_free_env_id_raises_when_all_busy(monkeypatch):
    import deepracer.service.identity as idm

    monkeypatch.setattr(idm, "port_is_free", lambda p, host="127.0.0.1": False)
    with pytest.raises(RuntimeError, match="slots are in use"):
        idm.free_env_id("u", max_envs=4)


def test_fingerprint_stable_and_order_insensitive():
    a = {"sensor": ["LIDAR"], "action_space": [1, 2]}
    t1 = {"WORLD_NAME": "Austin", "NUMBER_OF_OBSTACLES": "0"}
    t2 = {"NUMBER_OF_OBSTACLES": "0", "WORLD_NAME": "Austin"}  # reordered
    fp = fingerprint("img", a, t1)
    assert fp == fingerprint("img", a, t2)  # key order irrelevant
    assert fp == fingerprint("img", a, t1)  # deterministic


def test_fingerprint_excludes_nothing_relevant():
    base = fingerprint("img", {"a": 1}, {"w": "X"})
    assert base != fingerprint("img2", {"a": 1}, {"w": "X"})  # image matters
    assert base != fingerprint("img", {"a": 2}, {"w": "X"})  # agent matters
    assert base != fingerprint("img", {"a": 1}, {"w": "Y"})  # track matters
    assert base != fingerprint("img", {"a": 1}, {"w": "X"}, evaluation=True)
