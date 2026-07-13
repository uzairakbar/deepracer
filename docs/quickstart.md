# Quick Start

```python
import gymnasium as gym
import deepracer  # registers the deepracer-v0 environment

env = gym.make("deepracer-v0")      # starts a simulator service on demand

observation, info = env.reset()

observation, reward, terminated, truncated, info = env.step(
    env.action_space.sample()
)

env.close()                         # stops + removes the simulator service
```

`gym.make("deepracer-v0")` works out of the box with the packaged defaults. From here you
can:

- customize the environment — see [Configuring Environments](configuring.md);
- inspect the observation/action spaces and terminal flags — see [Gymnasium API](gym-api.md);
- run and clean up many simulators — see [Managing Environments](managing.md).
