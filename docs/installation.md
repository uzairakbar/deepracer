# Installation

## Requirements

- Python 3.12+
- A container runtime: Docker, Podman, or Apptainer (e.g. for rootless runs on HPC)
- Sufficient hardware resources (recommended ~3 CPUs, ~6 GB RAM)

## Install

```bash
pip install deepracer
```

Or from source, from the `client/` directory of the repository:

```bash
pip install .
```

!!! info "First launch downloads the simulator image"
    On first use, the simulator image is downloaded automatically. It is several GBs, so
    the first launch may take a few minutes. Later launches reuse the cached image.
