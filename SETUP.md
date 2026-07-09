# Setup

## Dependencies

### WSL Ubuntu (only for Windows)
If using Windows, please install [WSL2 and Ubuntu](https://documentation.ubuntu.com/wsl/latest/howto/install-ubuntu-wsl2/).

Also install either the [WSL extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-wsl) or [Remote Development extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.vscode-remote-extensionpack) for VSCode to develop in WSL.

### Docker
#### Windows
Install the [Docker Desktop for Windows](https://docs.docker.com/desktop/setup/install/windows-install/) and [configure it for WSL](https://docs.docker.com/desktop/features/wsl/).

#### MacOS
```bash
brew install docker --cask
open -a Docker
```

#### Linux (Ubuntu)
Uninstall all conflicting packages.
```bash
for pkg in docker.io docker-doc docker-compose docker-compose-v2 podman-docker containerd runc; do sudo apt-get remove $pkg; done
```

Set up Docker's `apt` repository.
```bash
# Add Docker's official GPG key:
sudo apt-get update
sudo apt-get install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources:
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
```

Install the Docker packages.
```bash
yes | sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo docker run hello-world
```

Add to sudoer group.
```bash
sudo groupadd docker
sudo usermod -aG docker $USER
newgrp docker
```
**Restart your system**, then test the installation.
```bash
docker run hello-world
```

### uv
Install `uv` and make sure it is in `PATH` (change `.profile` to `.bashrc` or `.zshrc` if needed):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# put uv in PATH 
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.profile
```

## Python environment
Make a virtual environment `.venv` with dependencies installed:
```bash
if [[ "$(hostname)" == *"pace.gatech.edu"* ]]; then
    # load uv
    module load uv
    # use scratch directory on PACE for quota compliance
    export UV_CACHE_DIR="$HOME/scratch/.cache/uv"
    export UV_PROJECT_ENVIRONMENT="$HOME/scratch/uv_envs/deepracer"
    mkdir -p "$HOME/scratch/uv_envs"
    # create a local shortcut
    [ -e .venv ] || ln -s "$UV_PROJECT_ENVIRONMENT" .venv
fi
uv venv
uv pip install .
```
To run your scripts using `.venv`, use:
```bash
uv run python src/run.py
```

## PACE ICE
We recommend students to setup the project locally. However, in cases where that may not be possible, students can explore the following PACE ICE remote compute services.

* Login to the [GeorgiaTech VPN Service](https://vpn.gatech.edu/global-protect/login.esp). Download and install the [GlobalProtect VPN client](https://vpn.gatech.edu/global-protect/getsoftwarepage.esp).
* Using the VPN client, connect to [vpn.gatech.edu](vpn.gatech.edu) and login via your GeorgiaTech username and password.
* Connect to the PACE ICE on-demand service at [ondemand-ice.pace.gatech.edu](https://ondemand-ice.pace.gatech.edu/pun/sys/dashboard).
* Click on 'My Interactive Sessions' and select whichever one you prefer on the 'Interactive Apps' menu (we recommend VS Code).

### Environment setup
Please note that PACE ICE machines already come with rootless **Podman**, **Apptainer**, and UV installed (use `module load uv`). As such, you do not need Docker: the container runtime is auto-detected (Podman is preferred, with Apptainer as a fallback), so you can follow the instructions from the [python environment section](#Python-environment) exactly as written.

**Important; fix up torch for your session's GPU.** PACE sessions may assign you a different CUDA version (12 vs. 13) than your previous installs. If PyTorch throws a CUDA version error, you can simply do a hot-swap:
```bash
module load uv
export UV_CACHE_DIR="$HOME/scratch/.cache/uv"
export UV_PROJECT_ENVIRONMENT="$HOME/scratch/uv_envs/deepracer"

# check the required drivers
cc=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader 2>/dev/null | head -1 | tr -d ' .')
if   [ -z "$cc" ];     then BACKEND=cpu     # no GPU on this node
elif [ "$cc" -lt 75 ]; then BACKEND=cu126   # Pascal/Volta (sm_60/sm_70, e.g. P100/V100)
else                        BACKEND=auto    # Turing .. Blackwell and newer
fi
echo "GPU compute capability '$cc' -> reinstalling torch ($BACKEND)"

uv pip install . --reinstall-package torch --torch-backend="$BACKEND"
```
If this doesn't fix things, then do a full clean slate and [re-build the python environment](#Python-environment):
```bash
module load uv
SCRATCH_DIR="$HOME"/scratch
export UV_CACHE_DIR="$SCRATCH_DIR/.cache/uv"
export UV_PROJECT_ENVIRONMENT="$SCRATCH_DIR/uv_envs/deepracer"
uv cache clean
rm -rf .venv                     # remove local venv symlink
rm -rf "$UV_PROJECT_ENVIRONMENT" # remove the actual venv dir
rm -rf "$UV_CACHE_DIR"           # clear the uv cache
rm -f uv.lock                    # rm lockfile to rebuild fresh
# Then follow the standard Python environment setup steps again
```