---
title: Managing DeepRacer Gym Environments
description: DeepRacer Gym manages containerized simulations and lifecycle across many Gymnasium environments, including caching, clean up, and parallel roll-outs.
---

# Managing Environments

Each call to `gym.make("deepracer-v0")` creates a Gymnasium environment and, by default, launches a dedicated simulator instance. You can inspect the simulators currently managed by:

```python
import deepracer
deepracer.running()         # list managed simulators on this host
```

You can also inspect running simulator services directly through your container runtime:

```bash
docker ps
podman ps
apptainer instance list
```

When you are done with the environment, call `env.close()` to stop and remove the simulator.

## Caching

If you are creating many environments in one process, simulator startup time can become
noticeable. Use `cache=True` to keep a **matching** simulator warm after `close()` so a
later environment with the same configuration can reuse it.

```python
env = gym.make("deepracer-v0", cache=True)
env.close()  # keeps the matching simulator warm for reuse in this process
```

## Cleanup

A cached simulator is only reused within the same Python process. When you are completely
done, or if you want to reclaim resources, stop all simulators managed by the current process:

```python
import deepracer
deepracer.shutdown_all()    # stop simulators owned by this process
```

If your notebook, script, or job is interrupted, a running simulator can be left behind. In this case, you can use the following
cleanup command before starting another batch of environments:

```bash
python -m deepracer.clean   # purge *all* running deepracer simulators
```

This will remove *all* managed Docker/Podman containers and Apptainer
instances.

## Resource limits

By default, a process can manage up to `DEEPRACER_MAX_ENVS=4` simulators at the same time.
For each simulator, budget roughly 3 CPUs, 6 GB of memory, and about a minute of startup
time.

!!! note
    At present, `deepracer` is CPU-only, and does not utilize GPU acceleration for simulation.

## Parallel rollouts

To use multiple environments in "parallel", use [`SyncVectorEnv`](https://gymnasium.farama.org/api/vector/sync_vector_env/). E.g., for three
parallel rollouts:

```python
from gymnasium.vector import SyncVectorEnv

def make_environment():
    return gym.make("deepracer-v0")

# spin up 3 environments (should take ~3 mins for boot-up)
envs = SyncVectorEnv([make_environment for _ in range(3)])
```

!!! warning
    [`AsyncVectorEnv`](https://gymnasium.farama.org/api/vector/async_vector_env/) is not currently supported by `deepracer`.
