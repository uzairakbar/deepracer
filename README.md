# Project 4 - CS 7642, Spring '25

## Setup
### Dependencies
- Conda
- Docker

### Create Conda Environment
```bash
conda env create -f environment.yaml
```

### Launch DeepRacer
```bash
source scripts/start_deepracer.sh \
    [-C=MAX_CPU; default="3"] \
    [-M=MAX_MEMORY; default="6g"]
```

## Usage
```python
import gym
import deepracer_gym

env = gym.make(
    'deepracer-v0'
)
observation, info = env.reset()
observation, reward, terminated, truncated, info = env.step(
    env.action_space.sample()
)
```
The `terminated` flag is trigerred by the following.
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

## Configuration
### List of Tracks
You can find the layouts for these [here](https://github.com/aws-deepracer-community/deepracer-race-data/blob/main/raw_data/tracks/README.md).
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
