# Configuring Environments

`deepracer-v0` works with packaged
[defaults](https://github.com/uzairakbar/deepracer/tree/main/client/deepracer/defaults),
but you can customize it through `gym.make()`:

```python
env = gym.make(
    "deepracer-v0",
    agent_config=agent_config,      # action space + sensors
    track_config=track_config,      # track, bots, obstacles
    reward_function=reward_function,  # custom reward function
    cpus=3, memory="6g",            # allocate sim resources
    cache=True,                     # keep sim warm on close
)
```

Most users will only need `reward_function`, `agent_config`, and `track_config`, each
described below.

## Reward Function

The reward function accepts the AWS DeepRacer
[input parameters](https://docs.aws.amazon.com/solutions/latest/deepracer-on-aws/create-a-model.html#input-parameters)
and returns a numeric reward. The same parameters are exposed in `info["reward_params"]`.
You can use the packaged
[default](https://github.com/uzairakbar/deepracer/blob/main/client/deepracer/defaults/reward_function.py)
reward function, or define a custom one:

```python
def reward_function(params):
    # example reward function
    return float(params["progress"])
```

!!! tip "Examples"
    For examples and design ideas, see the AWS DeepRacer
    [reward function examples](https://docs.aws.amazon.com/solutions/latest/deepracer-on-aws/create-a-model.html#sample-reward-functions).

## Agent Config

The `agent_config` defines the agent's action and observation space. The settings of
relevance are:

| Parameter | Description |
|---|---|
| `action_space_type` | Can be `discrete` or `continuous`. |
| `action_space` | Defines the action space in terms of `speed` and `steering_angle`. See examples below. |
| `sensor` | Can be `FRONT_FACING_CAMERA` (a 160×120 colored image), `STEREO_CAMERAS` (two 160×120 greyscale images) and/or `LIDAR` (64 radial readings). Two camera sensors cannot be selected at once, and LiDAR cannot be selected alone. See the [AWS DeepRacer sensors page](https://docs.aws.amazon.com/solutions/latest/deepracer-on-aws/create-a-model.html#sensors). |

=== "Discrete (default)"

    Discrete actions with LiDAR + stereo camera — the packaged
    [default](https://github.com/uzairakbar/deepracer/blob/main/client/deepracer/defaults/agent_params.json).

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

=== "Continuous"

    Continuous actions with LiDAR + front-facing camera.

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

## Track Config

The `track_config` defines the environment (world, obstacles, bot cars). See the
[DeepRacer-for-cloud documentation](https://aws-deepracer-community.github.io/deepracer-for-cloud/reference.html)
for a description of available parameters, e.g. the packaged
[default](https://github.com/uzairakbar/deepracer/blob/main/client/deepracer/defaults/environment_params.yaml).
Example:

```python
track_config = {
    "WORLD_NAME": "reInvent2019_wide",
    "NUMBER_OF_OBSTACLES":  "0",
    "NUMBER_OF_BOT_CARS":   "0",
    # ... and more.
}
```

The `WORLD_NAME` defines the track. You can find all track names
[here](https://github.com/uzairakbar/deepracer/blob/main/client/deepracer/defaults/tracks.txt),
and view their layouts
[here](https://github.com/aws-deepracer-community/deepracer-race-data/blob/main/raw_data/tracks/README.md).
