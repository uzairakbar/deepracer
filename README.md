# DeepRacer

A [Gymnasium](https://gymnasium.farama.org/) environment for the
[AWS DeepRacer](https://github.com/aws-deepracer-community/deepracer-for-cloud)
simulator. Each `deepracer-v0` environment automatically launches its own
simulator with Docker, Podman, or Apptainer, then exposes it through the standard
`gymnasium` API.

## Installation

Requirements:
- Python 3.12 or higher.
- A container runtime: Docker, Podman, or Apptainer (e.g., for rootless runs on HPC).

```bash
pip install deepracer
```

## Usage

```python
import gymnasium as gym
import deepracer  # registers the deepracer-v0 environment

env = gym.make('deepracer-v0')

observation, info = env.reset()

observation, reward, terminated, truncated, info = env.step(
    env.action_space.sample()
)

env.close()
```

See the [`client/`](client/) directory for the full documentation.
