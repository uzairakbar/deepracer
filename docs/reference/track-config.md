---
title: DeepRacer Gym Track Configuration Reference
description: Track Configuration parameters for DeepRacer Gym that define the world, and its moving/ static objects.
---

# Track Configuration

The `track_config` passed to `gym.make("deepracer-v0", track_config=...)` defines the world
and its moving/static objects. If omitted, the packaged
[default](https://github.com/uzairakbar/deepracer/blob/main/client/deepracer/defaults/environment_params.yaml)
is used. <br>See [Configuring Environments](../guide/configuring.md) for an example.

!!! info "Values are strings"
    The simulator service reads these as environment variables, so booleans and numbers are also given
    as strings, <br>e.g. `"true"`, `"0"`, `"2.0"`, etc.

| Key | Type | Default | Description |
|---|---|---|---|
| `WORLD_NAME` | str | `reInvent`<br>`2019_wide` | Track to load. See the [Track Catalog](tracks.md). |
| `CHANGE_START_POSITION` | bool | `true` | Randomize the agent's start position each episode. |
| `ALTERNATE_DRIVING_DIRECTION` | bool | `true` | Alternate clockwise / counter-clockwise across episodes. |
| `ENABLE_DOMAIN_RANDOMIZATION` | bool | `false` | Randomize textures/lighting (for sim-to-real). |
| `NUMBER_OF_OBSTACLES` | int ≥ 0 | `0` | Number of static obstacles. |
| `IS_OBSTACLE_BOT_CAR` | bool | `false` | Treat obstacles as bot cars rather than boxes. |
| `RANDOMIZE_OBSTACLE_LOCATIONS` | bool | `true` | Randomize obstacle placement each episode. |
| `OBJECT_POSITIONS` | list[float, int] | `[]` | Positions with  `progress, lane` (%age, $\pm 1$ respectively); overrides obstacle randomization. |
| `NUMBER_OF_BOT_CARS` | int ≥ 0 | `0` | Number of moving bot cars. |
| `RANDOMIZE_BOT_CAR_LOCATIONS` | bool | `true` | Randomize bot-car placement each episode. |
| `BOT_CAR_SPEED` | float (m/s) | `0.2` | Bot-car speed. |
| `MIN_DISTANCE_BETWEEN_BOT_CARS` | float (m) | `2.0` | Minimum spacing between bot cars. |
| `IS_LANE_CHANGE` | bool | `false` | Allow bot cars to change lanes. |
| `LOWER_LANE_CHANGE_TIME` | float (s) | `3.0` | Minimum time between bot-car lane changes. |
| `UPPER_LANE_CHANGE_TIME` | float (s) | `5.0` | Maximum time between bot-car lane changes. |
| `LANE_CHANGE_DISTANCE` | float (m) | `1.0` | Distance over which a lane change completes. |
| `MIN_DISTANCE_BETWEEN_OBSTACLES` | float (%) | `16.0` | Minimum distance between obstacle centers as %age of track length. |
| `RESET_BEHIND_DIST` | float (m) | `2.0` | Minimum distance to obstacle(s) at spawn time. |
| `RESET_AHEAD_DIST` | float (m) | `2.0` | Meters ahead for mercy reset teleport. |
| `ENABLE_MERCY_RESET` | bool | `true` | Teleports car ahead of nearby object after repeated crashes. |

!!! todo "Maintainer: undocumented keys"
    This list is not exhaustive, and the simulator may accept additional keys beyond those above (several undocumented in the
    [deepRacer-for-cloud reference](https://aws-deepracer-community.github.io/deepracer-for-cloud/reference.html)). We shall continue to add them here as they are confirmed.
