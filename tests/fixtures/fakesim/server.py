"""ZMQ stand-in for the DeepRacer sim container.

Implements the REQ/REP msgpack protocol used by gym_adapter and zmq_client so
the gym.make -> reset -> step -> close path can run against a lightweight image.
It also binds GYM_PORT, materializes /configs from DEEPRACER_* env vars, prints
the readiness marker, and accepts a new client after disconnect. FAKE_CRASH=1
exits non-zero with a FATAL line for readiness tests.
"""

import os
import pathlib
import sys

import msgpack
import msgpack_numpy as m
import numpy as np
import zmq

m.patch()

READY_MARKER = "================= Waiting for gym client ================="
EPISODE_LEN = int(os.environ.get("FAKE_EPISODE_LEN", "50"))


def materialize_configs():
    agent = os.environ.get("DEEPRACER_AGENT_PARAMS")
    track = os.environ.get("DEEPRACER_ENVIRONMENT_PARAMS")
    cfg = pathlib.Path("/configs")
    try:
        cfg.mkdir(exist_ok=True)
        if agent:
            (cfg / "agent_params.json").write_text(agent)
        if track:
            (cfg / "environment_params.yaml").write_text(track)
    except OSError:
        pass


def observation(step, game_over):
    return {
        "_next_state": {
            # The client transposes camera observations from H, W, C to C, H, W.
            "STEREO_CAMERAS": np.zeros((120, 160, 2), dtype=np.uint8),
            "LIDAR": np.ones((64,), dtype=np.float32),
        },
        "_game_over": bool(game_over),
        "_goal": False,
        "info": {
            "reward_params": {
                "steps": step,
                "track_width": 1.0,
                "distance_from_center": 0.0,
                "progress": float(step),
                "sim_time": step * 0.1,
                "is_crashed": False,
                "is_offtrack": False,
            },
            "episode_status": {
                "lap_complete": False,
                "crashed": False,
                "reversed": False,
                "off_track": False,
                "immobilized": False,
                "time_up": False,
            },
        },
    }


def main():
    if os.environ.get("FAKE_CRASH") == "1":
        print(
            "FATAL: simulation launch exited (rc=1); terminating container.",
            file=sys.stderr,
            flush=True,
        )
        sys.exit(1)

    materialize_configs()
    port = int(os.environ.get("GYM_PORT", "8888"))

    socket = zmq.Context.instance().socket(zmq.REP)
    socket.setsockopt(zmq.RCVTIMEO, 60_000)
    socket.bind(f"tcp://0.0.0.0:{port}")
    print(READY_MARKER, flush=True)

    while True:
        try:
            socket.recv()
        except zmq.Again:
            continue
        step = 1
        while True:
            game_over = step >= EPISODE_LEN
            socket.send(msgpack.packb(observation(step, game_over)))
            try:
                request = msgpack.unpackb(socket.recv())
            except zmq.Again:
                break
            if request.get("ready") is not None:  # a fresh reset handshake
                step = 1
                continue
            step = 1 if game_over else step + 1


if __name__ == "__main__":
    main()
