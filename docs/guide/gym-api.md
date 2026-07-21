---
title: Interfacing with DeepRacer via Gymnasium API
description: Interface with DeepRacer simulator via Gymnasium API data structures; action spaces, observation spaces and terminal states.
---

# Gymnasium Interface

The DeepRacer environment follows the standard `gymnasium` API. The three key components are observation space, action space, and termination conditions, each of which is described below.

## Action Space

Depending on your `agent_config` specification, the action space takes one of the following forms as a [`gymnasium.spaces`](https://gymnasium.farama.org/api/spaces/fundamental/) object, with `n` the size of `agent_config["action_space"]`:

=== "Continuous"
    ```python
    Box(-1, 1, shape=(n,)) # (1)!
    ```

    1. `n` is 2 for the Continuous example in [Configuring Environments](configuring.md#agent-config).

=== "Discrete (default)"
    ```python
    Discrete(n) # (1)!
    ```

    1. `n` is 5 for the Discrete example in [Configuring Environments](configuring.md#agent-config).

??? info "Continuous action scale and order"
    Keep the following in mind for continuous action spaces:

    - **Scale:** Elements are normalized between -1 and 1, representing `low` and `high` values of the respective quantity.
    - **Order:** The `steering_angle` and `speed` occupy the 1st and 2nd
    indices of the 2D action vector/list as `[normalized_steering_angle, normalized_speed]`.

## Observation Space

The observation space is a composite
[`gymnasium.spaces.Dict`](https://gymnasium.farama.org/api/spaces/composite/) object containing
the following keys-value pairs, depending on the sensors one specifies within their `agent_config` dictionary:

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
    # 0.15–2m valid range, uniform over 360°
    "LIDAR": Box(
        low=0.15, high=float("inf"), shape=(64,)
    ),
}
```

## Terminal States

The `terminated` flag is triggered by the following fields, accesible in `info["episode_status"]`:

```python
{
    "lap_complete": bool,   # same as info['reward_params']['progress'] >= 100
    "crashed":      bool,   # same as info['reward_params']['is_crashed']
    "off_track":    bool,   # same as info['reward_params']['is_offtrack']
    "reversed":     bool,   # progress decreases for 15 consecutive steps. NOT accessible in info['reward_params'].
}
```

The `truncated` flag is triggered by the following (not accessible in `info["reward_params"]`):

```python
{
    "immobilized":  bool,   # move <= 0.0003 for 15 consecutive steps
    "time_up":      bool,   # 180 seconds max, or 100_000 steps max
}
```
