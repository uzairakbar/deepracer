# DeepRacer Gym
<p align="center">
  <img src="deepracer.gif" alt="DeepRacer" width="200">
</p>
A [Gymnasium](https://gymnasium.farama.org/) wrapper for the
[AWS DeepRacer](https://github.com/aws-deepracer-community/deepracer-for-cloud)
simulator. Each `deepracer-v0` environment automatically launches its own containerized simulator
(Docker/Podman/Apptainer), then exposes it through the standard `gymnasium` API.

## Quick Example

```python
import gymnasium as gym
import deepracer

env = gym.make("deepracer-v0")      # starts a simulator service on demand

observation, info = env.reset()

observation, reward, terminated, truncated, info = env.step(
    env.action_space.sample()
)

env.close()                         # stops + removes the simulator service
```

## Navigation

<div class="grid cards" markdown>

-   :material-rocket-launch: **[Getting Started](getting-started.md)**

    Install the package and run your first rollout.

-   :material-tune: **[Configuring Environments](guide/configuring.md)**

    Reward functions, action/observation spaces, tracks.

-   :material-api: **[Gymnasium Interface](guide/gym-api.md)**

    Observation space, action space, and terminal states.

-   :material-server: **[Managing Environments](guide/managing.md)**

    Caching, cleanup, resource limits, and parallel rollouts.

-   :material-book-open-variant: **[Reference](reference/tracks.md)**

    Config keys, the full track catalog, and env vars.

</div>

## Citation

If you use **DeepRacer Gym** in your work, please cite it. You can use the following BibTeX entry:

```bibtex
@software{akbar_deepracer,
    author    = {Akbar, Uzair},
    title     = {{DeepRacer Gym}},
    year      = {2026},
    version   = {0.0.0},
    publisher = {GitHub},
    url       = {https://github.com/uzairakbar/deepracer},
    note      = {Computer software}
}
```

Or in plain text:

> Akbar, U. (2026). *DeepRacer Gym (Version 0.0.0)* [Computer software]. GitHub. https://github.com/uzairakbar/deepracer

!!! note
    This is the **concept DOI**, which always resolves to the latest release. To cite a specific version instead, use that release's version DOI from its [Zenodo record](https://doi.org/#).

## References

1. Balaji, B. et al. (2020). *DeepRacer: Autonomous Racing Platform for Experimentation with Sim2Real Reinforcement Learning*. IEEE International Conference on Robotics and Automation (ICRA). https://doi.org/10.1109/ICRA40945.2020.9197465

2. AWS DeepRacer Community. (2026). *deepracer-simapp* [Computer software]. GitHub. https://github.com/aws-deepracer-community/deepracer-simapp

## Acknowledgements

This project was originally developed for use in Georgia Tech's [CS 7642 Reinforcement Learning class](https://omscs.gatech.edu/cs-7642-reinforcement-learning). Many thanks to the course staff for their support in sharing it with the broader community.
