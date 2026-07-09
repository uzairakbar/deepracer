# Project 4, Spring '25 - DeepRacer

![deepracer](https://github.gatech.edu/rldm/P4_deepracer/assets/78388/86684160-fe6f-4a03-972c-078cd9a9afde)

## Clone this repository
```bash
git clone https://github.gatech.edu/rldm/P4_deepracer.git
cd P4_deepracer
```

## Setup and Install Dependencies
This project requires the following to work.
- A container runtime: Docker, Podman or Apptainer (rootless on HPC, e.g. PACE).
- Python 3.10 or higher (we use [`uv`](https://astral.sh/uv) to manage the environment).

Please see the detailed setup instructions in [`SETUP.md`](https://github.gatech.edu/rldm/P4_deepracer/blob/main/SETUP.md).

## Usage
```python
import gymnasium as gym
import deepracer_gym

env = gym.make('deepracer-v0')

observation, info = env.reset()

observation, reward, terminated, truncated, info = env.step(
    env.action_space.sample()
)

env.close()
```

See the [`deepracer/client/`](deepracer/client/) directory and the
[`usage.ipynb`](usage.ipynb) notebook for details.
