# Setup

## Dependencies

### WSL Ubuntu (only for Windows)
If using Windows, please install [WSL2 and Ubuntu](https://documentation.ubuntu.com/wsl/latest/howto/install-ubuntu-wsl2/).

Also install either the [WSL extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-wsl) or [Remote Development extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.vscode-remote-extensionpack) for VSCode to develop in WSL.

### Colima + Rosetta (only for Mac w/ Apple Silicon)

```bash
brew install colima
softwareupdate --install-rosetta --agree-to-license
```

### Docker
#### Windows
Install the [Docker Desktop for Windows](https://docs.docker.com/desktop/setup/install/windows-install/) and [configure it for WSL](https://docs.docker.com/desktop/features/wsl/).

#### Mac
```bash
brew install docker
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

### UV
For Mac/ Linux/ Windows (under WSL Ubuntu):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Python environment
Make a virtual environment with dependencies installed:
```bash
if [[ "$(hostname)" == *"pace.gatech.edu"* ]]; then
    # load uv
    module load uv
    # use scratch directory on PACE for quota compliance
    export UV_CACHE_DIR="$HOME/scratch/.cache/uv"
    export UV_PROJECT_ENVIRONMENT="$HOME/scratch/uv_envs/deepracer"
    mkdir -p "$HOME/scratch/uv_envs"
    # create a local shortcut
    if [ ! -e .venv ]; then
        ln -s $UV_PROJECT_ENVIRONMENT .venv
    fi
fi
uv venv
uv pip install -e . --torch-backend auto
```
To run your scripts using the virtual environment, use:
```bash
uv run python src/run.py
```

## PACE ICE
We recommend students to setup the project locally. However, in cases where that may not be possible, students can explore the following PACE ICE remote compute services.

* Login to the [GeorgiaTech VPN Service](https://vpn.gatech.edu/global-protect/login.esp). Download and install the [GlobalProtect VPN client](https://vpn.gatech.edu/global-protect/getsoftwarepage.esp).
* Using the VPN client, connect to [vpn.gatech.edu](vpn.gatech.edu) and login via your GeorgiaTech username and password.
* Connect to the PACE ICE on-demand service at [ondemand-ice.pace.gatech.edu](https://ondemand-ice.pace.gatech.edu/pun/sys/dashboard).
* Click on 'My Interactive Sessions' and select whichever one you prefer on the 'Interactive Apps' menu (we recommend Coder or VS Code).

### Environment setup
Please note that PACE ICE machines already come with Apptainer and UV installed (use `module load uv`). As such, you do not need Docker, and can follow the instructions from the [python environment section](#Python-environment) exactly as written.
