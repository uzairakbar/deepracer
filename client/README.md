# DeepRacer Gym

A Gymnasium environment for the [AWS DeepRacer](https://github.com/aws-deepracer-community/deepracer-for-cloud) simulator. Each `deepracer-v0`
environment automatically launches its own simulator with Docker, Podman, or
Apptainer, then exposes it through the standard `gymnasium` API.

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Configuring Environments](#configuring-environments)
- [Gymnasium API](#gymnasium-api)
- [Managing Environments](#managing-environments)

## Installation

Requirements:

- Python 3.10+
- Docker, Podman, or Apptainer
- Suficient HW resources (Recommended ~3 CPUs, ~6GB RAM)

From the `client/` directory:

```bash
pip install .
```

On first use, the simulator image is downloaded automatically. It is several GBs,
so the first launch may take a few minutes. Later launches reuse the cached
image.

## Quick Start

```python
import gymnasium as gym
import deepracer

env = gym.make('deepracer-v0')      # starts a simulator service on demand

observation, info = env.reset()

observation, reward, terminated, truncated, info = env.step(
    env.action_space.sample()
)

env.close()                         # stops + remove the simulator service
```

## Configuring Environments

`deepracer-v0` works with packaged [defaults](./deepracer/defaults/), but you can customize it through
`gym.make()`:

```python
env = gym.make(
    'deepracer-v0',
    agent_config: dict=agent_config,    # action space + sensors
    track_config: dict=track_config,    # track, bots, obstacles
    reward_function=reward_function,    # custom reward function
    cpus: int=3,   memory: str='6g',    # allocate sim resources
    cache: bool=True,                   # keep sim warm on close
)
```
Most users will only need `reward_function`, `agent_config`, and `track_config`, each of which is describe below.

### Reward Function
The reward function accepts the AWS DeepRacer
[input parameters](https://docs.aws.amazon.com/solutions/latest/deepracer-on-aws/create-a-model.html#input-parameters) and returns a numeric reward. The same parameters are exposed in `info['reward_params']`. You can use the packaged [default](./deepracer/defaults/reward_function.py) reward function, or define a custom one:
```python
def reward_function(params):
    # example reward function
    return float(params['progress'])
```
For examples and design ideas, see the AWS DeepRacer
[reward function examples](https://docs.aws.amazon.com/solutions/latest/deepracer-on-aws/create-a-model.html#sample-reward-functions).


### Agent Config
The `agent_config` defines the agent's action and observation space. The settings of relevance are:

| Parameter | Description |
|---|---|
| `action_space_type` | Can be `discrete` or `continuous`. |
| `action_space` | Defines the action space in terms of `speed` and `steering_angle`. See examples below. |
| `sensor` | Can be `FRONT_FACING_CAMERA` (a $160\times 120$ colored image), `STEREO_CAMERAS` (two $160\times 120$ greyscale images) and/or `LIDAR` ($64$ radial readings). Two camera sensors cannot be selected at once, and LiDAR cannot be selected alone. See the [AWS DeepRacer sensors page](https://docs.aws.amazon.com/solutions/latest/deepracer-on-aws/create-a-model.html#sensors). |

We provide two examples below:

#### Discrete actions with LiDAR + stereo camera (the packaged [default](./deepracer/defaults/agent_params.json))
```python
agent_config = {
    "action_space": [
        {"steering_angle":  30, "speed": 0.6},
        {"steering_angle":  15, "speed": 0.6},
        {"steering_angle":   0, "speed": 0.6},
        {"steering_angle": -15, "speed": 0.6},
        {"steering_angle": -30, "speed": 0.6},
    ],
    "action_space_type": "discrete",
    "sensor": ["STEREO_CAMERAS", "LIDAR"],
}
```

#### Continuous actions with LiDAR + front-facing camera
```python
agent_config = {
    "action_space": {
        "steering_angle": {"high": 30, "low": -30},
        "speed":          {"high":  2, "low":   1},
    },
    "action_space_type": "continuous",
    "sensor": ["FRONT_FACING_CAMERA", "LIDAR"],
}
```

### Track Config
The `track_config` defines the environment (world, obstacles, bot cars). See the
[DeepRacer-for-cloud documentation](https://aws-deepracer-community.github.io/deepracer-for-cloud/reference.html)
for a description of available parameters, e.g. the packaged [default](./deepracer/defaults/environment_params.yaml). Example:
```python
track_config = {
    "WORLD_NAME": "reInvent2019_wide",
    "NUMBER_OF_OBSTACLES":  "0",
    "NUMBER_OF_BOT_CARS":   "0",
    # ... and more.
}
```
The `WORLD_NAME` defines the track. You can find all track names [here](./deepracer/defaults/tracks.txt), and view their layouts [here](https://github.com/aws-deepracer-community/deepracer-race-data/blob/main/raw_data/tracks/README.md).

## Gymnasium API
The DeepRacer environment follows the standard `gymnasium` API:

```python
import gymnasium as gym
import deepracer

env = gym.make('deepracer-v0')      # create an environment

observation, info = env.reset()     # start an episode

observation, reward, terminated, truncated, info = env.step(
    env.action_space.sample()       # rollout
)
```
Three key components of observation space, action space, and terminal states are described below.
### Observation Space
The observation space is a composite [`gymnasium.spaces.Dict`](https://gymnasium.farama.org/api/spaces/composite/)
containing the following keys/values, depending on the sensors you specify in `agent_config`:
```python
{
    # two 8-bit greyscale (1 channel) images
    'STEREO_CAMERAS': Box(
        low=0, high=255, shape=(2, 120, 160)
    ),
    # one 8-bit colored (3 channel) image
    'FRONT_FACING_CAMERA': Box(
        low=0, high=255, shape=(3, 120, 160)
    ),
    'LIDAR': Box(
        low=0.15, high=float('inf'), shape=(64,)
    ),
}
```

### Action Space
Depending on the specification in your `agent_config`, the action space can be
the following. For continuous action spaces, the input is normalized between -1
and 1 representing the `low` and `high` values of the respective quantity.

| Type | `gymnasium.spaces` object |
|---|---|
| Discrete | `Discrete(n)`, where `n` is 5 for [the example above](#discrete-actions-with-lidar--stereo-camera-the-packaged-default). |
| Continuous[^2] | `Box(-1, 1, shape=(n,))`, where `n` is 2 for [the example above](#continuous-actions-with-lidar--front-facing-camera). |

[^2]: For continuous action spaces, the `steering_angle` and `speed` occupy the 1st and 2nd indices of the 2D action vector/list as `[normalized_steering_angle, normalized_speed]`.

### Terminal States
The `terminated` flag is triggered by the following in `info['episode_status']`:
```yaml
{
    "lap_complete": float,  # same as info['reward_params']['progress'] >= 100
    "crashed": boolean,     # same as info['reward_params']['is_crashed']
    "off_track": boolean,   # same as info['reward_params']['is_offtrack']
    "reversed": boolean,    # progress decreases for 15 consecutive steps. NOT accessible in info['reward_params'].
}
```
The `truncated` flag is triggered by the following (not accessible in `info['reward_params']`):
```yaml
{
    "immobilized": boolean,     # move <= 0.0003 for 15 consecutive steps
    "time_up": boolean,         # 180 seconds max, or 100_000 steps max
}
```

## Managing Environments

Each `gym.make("deepracer-v0")` creates a Gymnasium environment and, by default, starts one simulator service behind it. When you are done with the environment, call `env.close()` so the simulator is stopped and removed.

**Caching:** If you are creating many environments in one process, simulator startup time can become noticeable. Use `cache=True` to keep a ***matching*** simulator warm after `close()` so a later environment with the same configuration can reuse it.

```python
env = gym.make("deepracer-v0", cache=True)
env.close()  # keeps the matching simulator warm for reuse in this process
```

**Cleanup:** A cached simulator is only reused within the same Python process. When you are completely done, or if you want to reclaim resources, stop managed simulators:

```python
import deepracer

deepracer.running()       # list managed simulators on this host
deepracer.shutdown_all()  # stop simulators owned by this process
```

If your notebook, script, or job is interrupted, a simulator can be left behind. 
Use the cleanup command before starting another batch of environments:

```bash
python -m deepracer.clean
```

`python -m deepracer.clean` removes managed Docker/Podman containers and Apptainer instances left behind by interrupted runs.

**Resource limits:** By default, a process can manage up to `DEEPRACER_MAX_ENVS=4` simulators at the
same time. For each simulator, budget roughly 3 CPUs, 6 GB of memory, and
about a minute of startup time

**Parallel rollouts:** To use multiple environments in "parallel", you may use `SyncVectorEnv`. E.g., for 3 parallel rollouts:

```python
from gymnasium.vector import SyncVectorEnv

def make_environment():
    return gym.make('deepracer-v0')

# spin up 3 environments (should take ~3 mins for boot-up)
envs = SyncVectorEnv([make_environment  for _ in range(3)])
```

Unfortunately, `AsyncVectorEnv` is not currently supported by `deepracer`.
