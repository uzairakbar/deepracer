---
title: Configuring DeepRacer Gym Environments
description: Customize the DeepRacer Gym environment, including reward functions, action spaces, sensors, and track configuration.
---

# Configuring Environments

The `deepracer-v0` environment can be customized by specifying configurations in `gym.make()`:

```python
env = gym.make(
    "deepracer-v0",
    agent_config: dict=agent_config,    # action space + sensors
    track_config: dict=track_config,    # track, bots, obstacles
    reward_function=reward_function,    # custom reward function
    cpus: int=3, memory: str="6g",      # allocate sim resources
    cache: bool=True,                   # keep sim warm on close
)
```

Most users should only need to specify `reward_function`, `agent_config`, and `track_config`, each of which is described below.

## Reward Function

The reward function accepts the AWS DeepRacer [input parameters](https://docs.aws.amazon.com/solutions/latest/deepracer-on-aws/create-a-model.html#input-parameters) and returns a numeric reward. The same parameters are exposed in `info["reward_params"]`.
You can use the packaged default reward function, or define a custom one:

!!! example

    === "Complete lap"

        ```python
        def reward_function(params):
            """Example of rewarding the agent for lap completion"""
            
            if params["progress"] >= 100:
                reward = 1
            else:
                reward = 0
            
            return float(reward)
        ```

    === "Keep center (default)"

        ```python
        def reward_function(params):
            """Example of rewarding the agent to follow center line"""

            # Read input parameters
            track_width = params["track_width"]
            distance_from_center = params["distance_from_center"]

            # Calculate 3 markers that are at varying distances away from the center line
            marker_1 = 0.1 * track_width
            marker_2 = 0.25 * track_width
            marker_3 = 0.5 * track_width

            # Give higher reward if the car is closer to center line and vice versa
            if distance_from_center <= marker_1:
                reward = 1.0
            elif distance_from_center <= marker_2:
                reward = 0.5
            elif distance_from_center <= marker_3:
                reward = 0.1
            else:
                reward = 1e-3  # likely crashed/ close to off track

            return float(reward)
        ```

!!! tip
    For more examples and design ideas, see the AWS DeepRacer catalog of 
    [reward function examples](https://docs.aws.amazon.com/solutions/latest/deepracer-on-aws/create-a-model.html#sample-reward-functions).

## Agent Config

The `agent_config` defines the action and observation spaces. The settings of
relevance include:

| Parameter | Description |
|-----------|---|
| `action_space_type` | Can be `discrete` or `continuous`. |
| `action_space` | Defines the action space in terms of `speed` and `steering_angle`. See examples below. |
| `sensor` | Can be `FRONT_FACING_CAMERA` (a 160×120 colored image), `STEREO_CAMERAS` (two 160×120 greyscale images), and/or `LIDAR` (64 radial readings). <br>See the [AWS DeepRacer sensors page](https://docs.aws.amazon.com/solutions/latest/deepracer-on-aws/create-a-model.html#sensors) for details. |

!!! example

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

    === "Discrete (default)"

        Discrete actions with LiDAR + stereo camera.

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

Based on the specification in `agent_config`, the action and observation spaces are defined using the Gymnasium API, as described in the [Gymnasium Interface](./gym-api.md) section of the user guide.

!!! warning
    Two camera sensors cannot be selected at once, and LiDAR cannot be selected alone.

## Track Config

The `track_config` defines the environment (the track, #obstacles, #bot cars, etc). For example:

```python
track_config = {
    "WORLD_NAME":           "reInvent2019_wide",
    "NUMBER_OF_OBSTACLES":  "0",
    "NUMBER_OF_BOT_CARS":   "0",
    # ... and more.
}
```
!!! info
    All `track_config` parameters are string-valued because the simulator service reads them as environment variables.

The `WORLD_NAME` parameter specifies the track, selected from the [Track Catalog](../reference/tracks.md).

Please see the [Track Configuration reference](../reference/track-config.md) and/or the [DeepRacer-for-cloud documentation](https://aws-deepracer-community.github.io/deepracer-for-cloud/reference.html)
for descriptions of available `track_config` parameters.
