# Managing Environments

Each `gym.make("deepracer-v0")` creates a Gymnasium environment and, by default, starts
one simulator service behind it. When you are done with the environment, call
`env.close()` so the simulator is stopped and removed.

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
done, or if you want to reclaim resources, stop managed simulators:

```python
import deepracer

deepracer.running()       # list managed simulators on this host
deepracer.shutdown_all()  # stop simulators owned by this process
```

If your notebook, script, or job is interrupted, a simulator can be left behind. Use the
cleanup command before starting another batch of environments:

```bash
python -m deepracer.clean
```

`python -m deepracer.clean` removes managed Docker/Podman containers and Apptainer
instances left behind by interrupted runs.

## Resource limits

By default, a process can manage up to `DEEPRACER_MAX_ENVS=4` simulators at the same time.
For each simulator, budget roughly 3 CPUs, 6 GB of memory, and about a minute of startup
time.

## Parallel rollouts

To use multiple environments in "parallel", you may use `SyncVectorEnv`. E.g. for 3
parallel rollouts:

```python
from gymnasium.vector import SyncVectorEnv

def make_environment():
    return gym.make("deepracer-v0")

# spin up 3 environments (should take ~3 mins for boot-up)
envs = SyncVectorEnv([make_environment for _ in range(3)])
```

!!! warning
    `AsyncVectorEnv` is not currently supported by `deepracer`.
