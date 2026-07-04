# A Gymnasium Wrapper for DeepRacer

## Setup
### Dependencies
- A container runtime: Docker, Podman or Apptainer.
- Python 3.10 or higher.

### Install
```bash
pip install -e ./
```

## Start and manage environments
Constructing a `deepracer-v0`
environment starts its own simulator container (Docker/ Podman/ Apptainer), and `env.close()` stops it. The first run
pulls the image (~several GB, one-time); each subsequent sim boots in ~1 minute.

```python
import gymnasium as gym
import deepracer_gym

env = gym.make('deepracer-v0')      # starts a simulator on demand

observation, info = env.reset()

observation, reward, terminated, truncated, info = env.step(
    env.action_space.sample()
)

env.close()                         # stops and removes the simulator container
```

To see which simulators are currently running and to reap orphans:
```python
import deepracer_gym
deepracer_gym.running()             # names of running managed simulators
deepracer_gym.shutdown_all()        # stop everything this process started
```
```bash
python -m deepracer_gym.clean       # reap orphans from a crashed kernel
```

For more details, see the [`gymnasium` API section](#gymnasium-API) below.

## Configuration
The environment is configured through **three optional arguments** to
`gym.make`. Omit any of them to use the packaged default.

| Argument | Type | Replaces the old | Controls |
|---|---|---|---|
| `agent_config` | `dict` or `None` | `configs/agent_params.json` | action space + sensors |
| `track_config` | `dict` or `None` | `configs/environment_params.yaml` | world + obstacles + bot cars |
| `reward_function` | callable or `None` | `configs/reward_function.py` | the reward (computed client-side) |

```python
env = gym.make(
    'deepracer-v0',
    agent_config=my_agent_dict,       # see schema below; None -> packaged default
    track_config=my_track_dict,
    reward_function=my_reward_fn,
)
```

### Reward function
The reward function accepts the AWS DeepRacer
[input parameters](https://docs.aws.amazon.com/deepracer/latest/developerguide/deepracer-reward-function-input.html),
which are also exposed in `info['reward_params']`.

```python
def reward_function(params):
    return float(params['progress'])   # example
```
For motivation on designing reward functions for different race types, see the
[AWS DeepRacer reward function examples](https://docs.aws.amazon.com/deepracer/latest/developerguide/deepracer-reward-function-examples.html).

### Agent parameters (`agent_config`)
Defines the agent's action and observation space. The settings of relevance[^1]:

| Parameter | Description |
|---|---|
| `action_space_type` | Can be `discrete` or `continuous`. |
| `action_space` | Defines the action space in terms of `speed` and `steering_angle`. See examples below. |
| `sensor` | Can be `FRONT_FACING_CAMERA` (a $160\times 120$ colored image), `STEREO_CAMERAS` (two $160\times 120$ greyscale images) and/or `LIDAR` ($64$ radial readings). Two camera sensors cannot be selected at once, and LiDAR cannot be selected alone. See the [AWS DeepRacer sensors page](https://docs.aws.amazon.com/deepracer/latest/developerguide/deepracer-choose-race-type.html). |

The packaged default is the discrete stereo-camera + LiDAR example below.

#### Discrete actions with LiDAR + stereo camera (the packaged default)
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
    "neural_network": "DEEP_CONVOLUTIONAL_NETWORK_SHALLOW",
    "version": "6",
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
    "neural_network": "DEEP_CONVOLUTIONAL_NETWORK_SHALLOW",
    "version": "6",
}
```

[^1]: Please do not change the `neural_network` and `version` fields. `version` tracks the simulator's model-metadata version; keep it at `"6"` (values `< 5` make training markedly less stable).

### Environment parameters (`track_config`)
Defines the environment (world, obstacles, bot cars). See the
[DeepRacer-for-cloud documentation](https://aws-deepracer-community.github.io/deepracer-for-cloud/reference.html)
for the description of these parameters. Example:
```python
track_config = {
    "WORLD_NAME": "reInvent2019_track",
    "NUMBER_OF_OBSTACLES": "0",
    "NUMBER_OF_BOT_CARS": "0",
}
```

#### List of tracks
The track is selected with the `WORLD_NAME` parameter. The full set of valid
names (127 tracks) is shipped with the package and validated against your
`track_config` before launch — a misspelled name raises with a close-match
suggestion. You can find the layouts
[here](https://github.com/aws-deepracer-community/deepracer-race-data/blob/main/raw_data/tracks/README.md).
Common ones include `reInvent2019_track`, `Vegas_track`, `Austin`, `Monaco`,
`Spain_track`, `Singapore`, `Oval_track`, and `Straight_track`.

## `gymnasium` API
The DeepRacer environment follows the standard `gymnasium` API. Here are the key components:

### Environment Creation
```python
import gymnasium as gym
import deepracer_gym

env = gym.make('deepracer-v0')
```

### Observation Space
The observation space is a composite [`gymnasium.spaces.Dict`](https://gymnasium.farama.org/api/spaces/composite/)
containing the following keys/values, depending on the sensors in your `agent_config`:
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

### Environment Step
```python
observation, reward, terminated, truncated, info = env.step(action)
```

The step function returns:
- `observation`: Dictionary of sensor readings
- `reward`: Float value from reward function
- `terminated`: Boolean indicating episode end due to:
  - Crash
  - Off-track
  - Reversed direction
  - Lap completion
- `truncated`: Boolean indicating episode end due to:
  - Time/Step limit
  - Immobilization
- `info`: Dictionary containing:
  - `reward_params`: Parameters used in reward calculation
  - `episode_status`: Current episode state

### Terminal States
The `terminated` flag is triggered by the following in `info['episode_status']`.
```yaml
{
    "lap_complete": float,  # same as info['reward_params']['progress'] >= 100
    "crashed": boolean,     # same as info['reward_params']['is_crashed']
    "off_track": boolean,   # same as info['reward_params']['is_offtrack']
    "reversed": boolean,    # progress decreases for 15 consecutive steps. NOT accessible in info['reward_params'].
}
```
The `truncated` flag is triggered by the following (not accessible in `info['reward_params']`).
```yaml
{
    "immobilized": boolean,     # move <= 0.0003 for 15 consecutive steps
    "time_up": boolean,         # 180 seconds max, or 100_000 steps max
}
```

### Environment Reset
```python
observation, info = env.reset()
```

### Environment Close
```python
env.close()
```
`env.close()` stops and removes the simulator. For a plain env this is all you
need. If you constructed the env via `gym.make` (which wraps it) and want to
override the close-time cache behavior, use `deepracer_gym.close(env, cache=…)`
or `env.unwrapped.close(cache=…)` — gymnasium's `Wrapper.close()` does not
forward keyword arguments.

### Rendering
```python
# Returns numpy array
env = gym.make('deepracer-v0', render_mode='rgb_array')
```

### Running several environments
Each `deepracer-v0` env provisions its own simulator on its own port, so you can
run up to `DEEPRACER_MAX_ENVS` (default `4`) at once — including via
`gym.vector.SyncVectorEnv` with `num_envs > 1`. Each env is a full simulator
(~3 CPU / 6 GB, ~1 min cold start), so this is real parallelism at a real
resource cost, not free. A 5th concurrent env raises a clear error.

## Limitations, Problems and Troubleshooting
- If Docker does not work for you without `sudo`, please follow the instructions in [`SETUP.md`](../SETUP.md) to add it to the `docker` group.
- The **first** `gym.make('deepracer-v0')` can be slow: the simulator image is
  downloaded (~several GB) before the container starts. This is a one-time cost;
  subsequent runs reuse the cached image and boot in ~1 minute.
- On HPC (Apptainer) the image is pulled once to a cached `.sif` under
  `$SCRATCH` (else `~/scratch`) and reused. If a run leaves an orphaned
  simulator, `python -m deepracer_gym.clean` stops instances and clears
  overlays/logs.
- We have tried to diligently test the simulator and various configurations for this project. However, it is entirely possible that some edge-cases may have gone overlooked. Should you encounter one, please hop into an OH or reach out to a TA to get it fixed ASAP.
