# Setup

## Dependencies

### Docker
#### Windows
Install the [Docker Desktop for Windows](https://docs.docker.com/desktop/setup/install/windows-install/).

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

Test the installation.
```bash
docker run hello-world
```

### Conda
#### Windows
Install Miniconda from [here](/docs/getting-started/miniconda/install#macos-linux-installation).
#### Linux
```bash
mkdir -p ~/miniconda3
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda3/miniconda.sh
bash ~/miniconda3/miniconda.sh -b -u -p ~/miniconda3
rm ~/miniconda3/miniconda.sh
source ~/miniconda3/bin/activate
conda init --all
```

## Python environment
We can use either a python `venv` or a conda environment (recommended) for this project. Instructions for both are given below.

### PyTorch
If you would like to install the GPU version of PyTorch, go to the [official PyTorch install page](https://pytorch.org/get-started/locally/) and select your system with the `pip` option. Then copy the `--index-url` value into `requirements.txt` (if none present, remove it from `requirements.txt` as well).

### Conda environment (recommended)
```bash
conda env create -f environment.yaml
conda activate deepracer
```

### Python `venv`
Python version 3.10 or above is required.
```bash
environment='.deepracer'
python -m venv "$environment"
"$environment"/bin/python -m pip install -r requirements.txt
"$environment"/bin/python -m pip install -e ./packages/
source "$environment"/bin/activate
```

## PACE ICE
We recommend students to setup the project locally. However, in cases where that may not be possible, students can explore the following PACE ICE remote compute services.

| PACE ICE Resource | Link |
| --- | --- |
| Slurm (interactive jobs) | [gatech.service-now.com/home?id=kb_article_view&sysparm_article=KB0042096](https://gatech.service-now.com/home?id=kb_article_view&sysparm_article=KB0042096) |
| On-demand resource with GUI | [ondemand-ice.pace.gatech.edu](https://ondemand-ice.pace.gatech.edu/pun/sys/dashboard) |

We also provide one such approach below as a reference. Please use your **GeorgiaTech Student ID** in place of all of the placeholders below.

### Login to PACE ICE
```bash
GT_ID=<YOUR_GT_ID_HERE>
ssh "$GT_ID"@login-ice.pace.gatech.edu
```

### Run an interactive job
```bash
GT_ID=<YOUR_GT_ID_HERE>
JOB_NAME='cs7642'
TIME_LIMIT=360          # 6 hrs
MEMORY='32GB'           # change as required
CPUS=8                  # change as required
GPUS=1                  # change as required
salloc --nodes=1 \
    --ntasks=1 \
    --cpus-per-task="$CPUS" \
    --mem="$MEMORY" \
    --gpus="$GPUS" \
    --time="$TIME_LIMIT" \
    --job-name="$JOB_NAME"
```
For details, refer to the [Slurm documentaiton](https://gatech.service-now.com/home?id=kb_article_view&sysparm_article=KB0042096).

### `ssh` into a running interactive job
To `ssh` into a running job (named `cs7642`) from another terminal on PACE ICE, use the following command.
```bash
GT_ID=<YOUR_GT_ID_HERE>
JOB_NAME='cs7642'
nodelist=$(
    squeue -u "$GT_ID" | awk '$3 == "'"$JOB_NAME"'" {print $NF}'
)
ssh "$GT_ID"@"$nodelist"
```

### Use Conda in an interactive job
To use the conda in an interactive job, run the following command.
```bash
module load anaconda3
```