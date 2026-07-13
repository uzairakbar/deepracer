# Gymnasium API

The DeepRacer environment follows the standard `gymnasium` API:

```python
import gymnasium as gym
import deepracer

env = gym.make("deepracer-v0")      # create an environment

observation, info = env.reset()     # start an episode

observation, reward, terminated, truncated, info = env.step(
    env.action_space.sample()       # rollout
)
```

The three key components — observation space, action space, and terminal states — are
described below.

## Observation Space

The observation space is a composite
[`gymnasium.spaces.Dict`](https://gymnasium.farama.org/api/spaces/composite/) containing
the following keys/values, depending on the sensors you specify in `agent_config`:

```python
{
    # two 8-bit greyscale (1 channel) images
    "STEREO_CAMERAS": Box(
        low=0, high=255, shape=(2, 120, 160)
    ),
    # one 8-bit colored (3 channel) image
    "FRONT_FACING_CAMERA": Box(
        low=0, high=255, shape=(3, 120, 160)
    ),
    "LIDAR": Box(
        low=0.15, high=float("inf"), shape=(64,)
    ),
}
```

## Action Space

Depending on the specification in your `agent_config`, the action space can be one of the
following. For continuous action spaces, the input is normalized between -1 and 1,
representing the `low` and `high` values of the respective quantity.

| Type | `gymnasium.spaces` object |
|---|---|
| Discrete | `Discrete(n)`, where `n` is 5 for the discrete example in [Configuring Environments](configuring.md#agent-config). |
| Continuous | `Box(-1, 1, shape=(n,))`, where `n` is 2 for the continuous example in [Configuring Environments](configuring.md#agent-config). |

!!! note "Continuous action ordering"
    For continuous action spaces, the `steering_angle` and `speed` occupy the 1st and 2nd
    indices of the 2D action vector/list as `[normalized_steering_angle, normalized_speed]`.

## Terminal States

The `terminated` flag is triggered by the following in `info["episode_status"]`:

| Status | Description |
|---|---|
| `lap_complete` | `float` — same as `info["reward_params"]["progress"] >= 100`. |
| `crashed` | `bool` — same as `info["reward_params"]["is_crashed"]`. |
| `off_track` | `bool` — same as `info["reward_params"]["is_offtrack"]`. |
| `reversed` | `bool` — progress decreases for 15 consecutive steps. Not accessible in `info["reward_params"]`. |

The `truncated` flag is triggered by the following (not accessible in `info["reward_params"]`):

| Status | Description |
|---|---|
| `immobilized` | `bool` — moves ≤ 0.0003 for 15 consecutive steps. |
| `time_up` | `bool` — 180 seconds max, or 100,000 steps max. |
