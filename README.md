# DeepRacer

[![PyPI](https://img.shields.io/pypi/v/deepracer?logo=pypi&logoColor=white)](https://pypi.org/project/deepracer/)
[![Downloads](https://img.shields.io/pepy/dt/deepracer?logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI%2BPHBhdGggZmlsbD0id2hpdGUiIGQ9Ik01LDIwSDE5VjE4SDVNMTksOUgxNVYzSDlWOUg1TDEyLDE2TDE5LDlaIi8%2BPC9zdmc%2B&label=downloads)](https://pepy.tech/project/deepracer)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/github/license/uzairakbar/deepracer?logo=opensourceinitiative&logoColor=white)](LICENSE)
[![Tests](https://img.shields.io/github/actions/workflow/status/uzairakbar/deepracer/test.yml?branch=develop&logo=githubactions&logoColor=white&label=tests)](https://github.com/uzairakbar/deepracer/actions/workflows/test.yml)
[![Coverage](https://img.shields.io/codecov/c/github/uzairakbar/deepracer?branch=develop&logo=pytest&logoColor=white)](https://codecov.io/gh/uzairakbar/deepracer)
[![Docker Pulls](https://img.shields.io/docker/pulls/uzairakbar/deepracer-test?logo=docker&logoColor=white&label=pulls)](https://hub.docker.com/r/uzairakbar/deepracer-test)
[![DOI](https://zenodo.org/badge/1297933489.svg)](https://zenodo.org/badge/latestdoi/1297933489)

<p align="center">
  <img src="docs/deepracer.gif" alt="DeepRacer" width="200">
</p>

A [Gymnasium](https://gymnasium.farama.org/) wrapper for the
[AWS DeepRacer](https://github.com/aws-deepracer-community/deepracer-for-cloud)
simulator. Each `deepracer-v0` environment automatically launches its own
containerized simulator (Docker/Podman/Apptainer), then exposes it through the standard `gymnasium` API.

## Install

Requirements:
- Python 3.12+
- Linux (tested on Ubuntu 20.04+), macOS, or Windows (via WSL2)
- A container runtime: Docker, Podman, or Apptainer (e.g. for rootless runs on HPC)
- Sufficient hardware resources (recommended ~3 CPUs, ~6 GB RAM per environment)

```bash
pip install deepracer
```

## Quick Start

```python
import gymnasium as gym
import deepracer

env = gym.make("deepracer-v0")      # starts a simulator service on demand

observation, info = env.reset()

observation, reward, terminated, truncated, info = env.step(
    env.action_space.sample()
)

env.close()
```

See the [`client/`](client/) directory for the full documentation.
