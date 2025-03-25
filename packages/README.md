# A Gymnasium Wrapper for DeepRacer

## Setup
### Dependencies
- Docker
- Python 3.10 or higher.
- Linux or Windows machine with Intel based CPU.

### Install
```bash
pip install ./
```

## Usage
### Launch the simulation
From the root of this repository, start the simulator container with the following command.
```bash
source scripts/start_deepracer.sh \
    [-C=MAX_CPU; default="3"] \
    [-M=MAX_MEMORY; default="6g"]
```
Similarly, use `scripts/stop_deepracer.sh` and `scripts/cleanup_deepracer.sh` to stop the simulaiton container and clean setup artifacts (when finished with the project).

To check if the container is rumming you can use the following commands.
```bash
docker ps -a            # if using Docker (local setup)
apptainer instance list # if using Apptainer (PACE ICE)
```
Note that the simulator is initialized by the config files in the `configs/` directory. To change the simulation settings, you have to stop the container, and start it back up after changing the files in `configs/` accordingly.

### Interact with the environment
```python
import gymnasium as gym
import deepracer_gym

env = gym.make(
    'deepracer-v0'
)

observation, info = env.reset()

observation, reward, terminated, truncated, info = env.step(
    env.action_space.sample()
)
```
The `terminated` flag is trigerred by the following[^1].
```json
{
    "progress": float,          # accessible in info['reward_params']
    "is_crashed": Boolean,      # accessible in info['reward_params']
    "is_reversed": Boolean,     # accessible in info['reward_params']
    "is_offtrack": Boolean,     # accessible in info['reward_params']
}
```
The `truncated` flag is trigerred by the following (not accessible in `info['reward_params']`).
```json
{
    "immobilized": Boolean,     # move <= 0.0003 for 15 consecutive steps
    "time_up": Boolean,         # 180 seconds max, or 100_000 steps max
}
```

[^1]: However, the relationship may not straightforward. For example, even if `is_crashed` is `True`, the `terminated` flag might not get trigerred if the collision object is moving faster than our racer such that an actual collision will not happen.

For more details, see the [`gymnasium` API section](#gymnasium-API) below.

## Configuration
### Reward function
The `configs/reward_function.py` file defines the reward function which accepts varous [input parameters](https://docs.aws.amazon.com/deepracer/latest/developerguide/deepracer-reward-function-input.html). These are also accessible in `info` varibale of `gymnasium` as `info['reward_params']`.

To get motivation for designing reward functions for different types of races, please take a look at the [AWS DeepRacer reward function examples](https://docs.aws.amazon.com/deepracer/latest/developerguide/deepracer-reward-function-examples.html).

### Agent parameters
The `configs/agent_params.json` configuration file defines the agent's action and observation space. The only settings of relevance are the following[^2]:.
| Parameter | Description |
|---|---|
| `action_space_type` | Can be `discrete` or `continuous`. |
| `action_space` | Defines the action space in terms of `speed` and `steering_angle`. See examples below. |
| `sensor` | Can be `FRONT_FACING_CAMERA` (a $160\times 120$ colored image), `STEREO_CAMERAS` (two $160\times 120$ greyscale images) and/or `LIDAR` ($64$ radial readings). Two camera sensors cannot be selected at once. Only LiDAR cannot be selected. For details please refer to the [AWS DeepRacer sensors page](https://docs.aws.amazon.com/deepracer/latest/developerguide/deepracer-choose-race-type.html). |

We provide two examples below:

#### Discrete actions with LiDAR + stereo camera 
```json
{
    "action_space": [
        {
            "steering_angle": 30,
            "speed": 0.6
        },
        {
            "steering_angle": 15,
            "speed": 0.6
        },
        {
            "steering_angle": 0,
            "speed": 0.6
        },
        {
            "steering_angle": -15,
            "speed": 0.6
        },
        {
            "steering_angle": -30,
            "speed": 0.6
        }
    ],
    "action_space_type": "discrete",
    "sensor": ["STEREO_CAMERAS", "LIDAR"],
    "neural_network": "DEEP_CONVOLUTIONAL_NETWORK_SHALLOW",
    "version": "4"
}
```

#### Continuous actions with LiDAR + front-facing camera
```json
{
    "action_space": {
        "speed": {
            "high": 2,
            "low": 1
        },
        "steering_angle": {
            "high": 30,
            "low": -30
        }
    },
    "action_space_type": "continuous",
    "sensor": ["FRONT_FACING_CAMERA", "LIDAR"],
    "neural_network": "DEEP_CONVOLUTIONAL_NETWORK_SHALLOW",
    "version": "4"
}
```

[^2]: Please donot change the `neural_network` and `version` variables.

### Environment parameters
The `configs/environment_params.yaml` configuration file is used to define the environment. See the [DeepRacer-for-cloud documentation](https://aws-deepracer-community.github.io/deepracer-for-cloud/reference.html) for the description of these parameters.
#### List of tracks
The following tracks can be selected by setting the `WORLD_NAME` parameter. You can find the layouts for these [here](https://github.com/aws-deepracer-community/deepracer-race-data/blob/main/raw_data/tracks/README.md).
```yaml
"Albert"
"AmericasGeneratedInclStart"
"Aragon"
"Austin"
"AWS_track"
"Belille"
"Bowtie_track"
"Canada_Race"
"Canada_Training"
"ChinaAlt_track"
"China_track"
"FS_June2020"
"hamption_open"
"hamption_pro"
"July_2020"
"jyllandsringen_open"
"jyllandsringen_pro"
"LGSWide"
"MexicoAlt_track"
"Mexico_track"
"Monaco"
"Monaco_building"
"New_YorkAlt_Track"
"New_York_Track"
"Oval_track"
"penbay_open"
"penbay_pro"
"reInvent2019_track"
"reInvent2019_wide"
"reInvent2019_wide_mirrored"
"reinvent_base"
"reinvent_base_jeremiah"
"reinvent_carpet"
"reinvent_concrete"
"reinvent_wood"
"Singapore"
"Singapore_building"
"Singapore_f1"
"Spain_track"
"Spain_track_f1"
"Straight_track"
"thunder_hill_open"
"thunder_hill_pro"
"Tokyo_Racing_track"
"Tokyo_Training_track"
"Virtual_Competition_1"
"Virtual_May19_Comp_track"
"Virtual_May19_Train_track"
"Vegas_track"
```

## `gymnasium` API

t.b.d.