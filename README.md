# Project 4, Spring '25 - DeepRacer

## Setup \& Dependencies
- Docker.
- Conda (or Python 3.10 or higher).
- Linux or Windows machine with an Intel CPU.

Please see the detailed setup instructions in [`SETUP.md`](https://github.gatech.edu/rldm/P4_deepracer/blob/main/SETUP.md).

## Usage

Launch the DeepRacer simulation.
```bash
source scripts/start_deepracer.sh \
    [-C=MAX_CPU; default="3"] \
    [-M=MAX_MEMORY; default="6g"]
```

Interact with the environment via `gymnasium`.
```python
import gymnasium as gym
import deepracer_gym

env = gym.make('deepracer-v0')

observation, info = env.reset()

observation, reward, terminated, truncated, info = env.step(
    env.action_space.sample()
)
```
See the [packages directory](https://github.gatech.edu/rldm/P4_deepracer/tree/main/packages) and the [usage.ipynb](https://github.gatech.edu/rldm/P4_deepracer/tree/main/usage.ipynb) notebook for details.

## Logging
View training metrics via tensorboard.
```bash
tensorboard --logdir runs [--port=PORT; default=6006]
```