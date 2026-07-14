# Getting Started

## Requirements

- Python 3.12+
- Linux (tested on Ubuntu 20.04+), macOS, or Windows (via WSL2)
- A container runtime: Docker, Podman, or Apptainer (e.g. for rootless runs on HPC)
- Sufficient hardware resources (recommended ~3 CPUs, ~6 GB RAM per environment)

## Installation

=== "pip"

    ```bash
    pip install deepracer
    ```

=== "uv"

    ```bash
    uv add deepracer
    ```

=== "from source (development)"

    ```bash
    git clone https://github.com/uzairakbar/deepracer.git
    cd deepracer
    uv venv --python 3.12
    uv sync --extra dev
    source .venv/bin/activate
    ```

!!! info "First launch downloads the simulator image"
    On first use, the simulator image is downloaded automatically. It is several GBs, so
    the first launch may take a few minutes. Later launches reuse the cached image.

## Rollout

```python
import gymnasium as gym
import deepracer                        # register the deepracer-v0 env in gym

env = gym.make("deepracer-v0")          # starts a simulator service on demand

observation, info = env.reset()         # reset env, start the episode rollout

print("Start DeepRacer rollout")
total_reward = 0
episode_over = True

while not episode_over:
    observation, reward, terminated, truncated, info = env.step(
        env.action_space.sample()       # take a single step via random action
    )

    total_reward += reward
    episode_over = terminated or truncated

print(f"Episode finished! Total reward: {total_reward}")
env.close()                             # stop, & remove the simulator service
```

Instantiation via `gym.make("deepracer-v0")` works out of the box with the packaged defaults. For more details on [environment configuration](guide/configuring.md), [environment management](guide/managing.md), or [interfacing via Gymnasium](guide/gym-api.md), please see the **User Guide** section.
