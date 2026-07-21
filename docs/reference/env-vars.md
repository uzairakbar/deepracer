---
title: DeepRacer Gym Environment Variable Reference
description: Reference for the environment variables that configure the simulator image, container backend, concurrency, and readiness timeouts.
---

# Environment Variables

The following process-level environment variables tune the client. They are read once when
`deepracer` is imported.

| Variable | Default | Controls |
|---|---|---|
| `DEEPRACER_IMAGE` | `ghcr.io/uzairakbar/`<br>`deepracer:v0` | The simulator image to use. |
| `DEEPRACER_BACKEND` | *(auto-detected)* | Container runtime: `docker`, `podman`, or `apptainer`. |
| `DEEPRACER_MAX_ENVS` | `4` | Maximum simulators one process may run at once. |
| `DEEPRACER_READY_TIMEOUT` | `300` | Seconds to wait for a simulator to become ready <br>before failing. |

!!! example

    === "Shell"

        ```bash
        DEEPRACER_BACKEND=podman DEEPRACER_MAX_ENVS=2 python rollout.py
        ```

    === "Python"

        ```python
        import os
        os.environ["DEEPRACER_MAX_ENVS"] = "2"
        os.environ["DEEPRACER_BACKEND"] = "podman"

        import deepracer
        # ...
        ```
