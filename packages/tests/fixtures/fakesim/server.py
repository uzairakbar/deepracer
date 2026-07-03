"""A tiny stand-in for the DeepRacer sim container.

It exists to test the *container-management* code (backends, manager, ports,
labels, cache, concurrency) on a real runtime without the multi-GB amd64 sim.
It reproduces exactly the contract our code depends on:
  - binds GYM_PORT (which Docker/Podman set to the internal 8888),
  - materializes /configs from the DEEPRACER_* env vars (the §5.1 mechanism),
  - prints a readiness marker,
  - keeps accepting connections after a client disconnects (the survive-
    disconnect property that cache/attach relies on).
Optionally exits non-zero with a FATAL line if FAKE_CRASH=1 (readiness test).
"""
import os
import sys
import socket
import pathlib


def materialize_configs():
    agent = os.environ.get('DEEPRACER_AGENT_PARAMS')
    track = os.environ.get('DEEPRACER_ENVIRONMENT_PARAMS')
    cfg = pathlib.Path('/configs')
    cfg.mkdir(exist_ok=True)
    if agent:
        (cfg / 'agent_params.json').write_text(agent)
    if track:
        (cfg / 'environment_params.yaml').write_text(track)


def main():
    if os.environ.get('FAKE_CRASH') == '1':
        print('FATAL: simulation launch exited (rc=1); terminating container.',
              file=sys.stderr, flush=True)
        sys.exit(1)

    materialize_configs()
    port = int(os.environ.get('GYM_PORT', '8888'))

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', port))
    server.listen(8)
    # Same readiness marker the real gym_agent.py prints once its ZMQ server has
    # bound — the manager watches for it (OCI proxy makes a bare TCP probe lie).
    print('================= Waiting for gym client =================', flush=True)

    while True:                        # re-serve forever (survive client disconnect)
        try:
            conn, _ = server.accept()
        except KeyboardInterrupt:
            break
        try:
            conn.recv(64)
            conn.sendall(b'ok')
        except OSError:
            pass
        finally:
            conn.close()


if __name__ == '__main__':
    main()
