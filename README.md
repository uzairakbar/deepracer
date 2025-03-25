# Project 4 - CS 7642, Spring '25

## Setup
- Docker.
- Conda (or Python 3.10 or higher).
- Linux or Windows machine with an Intel CPU.
Please see the detailed setup instructions in [`SETUP.md`](https://github.gatech.edu/rldm/P4_deepracer/blob/main/SETUP.md).

### Launch DeepRacer
Start the simulator container with the following command.
```bash
source scripts/start_deepracer.sh \
    [-C=MAX_CPU; default="3"] \
    [-M=MAX_MEMORY; default="6g"]
```
Similarly, use `scripts/stop_deepracer.sh` and `scripts/cleanup_deepracer.sh` to stop the simulaiton container and clean setup artifacts (when finished with the project).

## Usage
```python
import gymnasium as gym
import deepracer_gym

env = gym.make('deepracer-v0')

observation, info = env.reset()

observation, reward, terminated, truncated, info = env.step(
    env.action_space.sample()
)
```
See the [packages directory](https://github.gatech.edu/rldm/P4_deepracer/tree/main/packages) for details.

## Logging
View training metrics via tensorboard.
```bash
tensorboard --logdir runs [--port=PORT; default=6006]
```
