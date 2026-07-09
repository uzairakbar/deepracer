# DeepRacer Gym Service

The DeepRacer Gym service is built as a patch series from
[`aws-deepracer-community/deepracer-simapp`](https://github.com/aws-deepracer-community/deepracer-simapp)
to repurpose it into a training-free
simulation served to the `deepracer_gym` client over ZMQ.

## Layout
```
service/
├── upstream/      git submodule → aws-deepracer-community/deepracer-simapp, pinned (v6.0.5)
├── patches/       our delta as a patch series
├── scripts/       scripts to setup workspace, apply / record patches, and build the service
├── workspace/     git-IGNORED dev sandbox to edit + commit + patch the upstream source code
└── README.md
```

## Setup workspace
Because the upstream `aws-deepracer-community/deepracer-simapp` is a read-only vendored source, we cannot edit `upstream/` directly. Therefore, all development is done in a git-ignored `workspace/` sandbox with the following workflow:
```bash
deepracer/service/scripts/init_workspace.sh     # move upstream@pin + patches to workspace/
cd deepracer/service/workspace                  # normal git repo; edit, commit, test here
# ... make changes, git commit ...
deepracer/service/scripts/export_patches.sh     # write commits back to ../patches/
git add deepracer/service/patches && git commit # commit patches to this monorepo
```

## Build the image
To build the simulator service image from source (`upstream @ pin` + `patches/*`), use the `scripts/builf.sh` script as:
```bash
ARCH=amd64 OUT_IMAGE=uzairakbar/deepracer-test:v0-amd64 PUSH=1 \
  deepracer/service/scripts/build.sh
```
Our CI (`.github/workflows/build-service-image.yml`) does this for amd64+arm64 and
stitches a multi-arch manifest.

## Bump the upstream version
To bump the `upstream/` submodule pointer to another version, use the following script:
```bash
deepracer/service/scripts/bump_upstream.sh <new-upstream-tag>
# resolve any 3-way conflicts in workspace/, rebuild + validate, then:
deepracer/service/scripts/export_patches.sh
git add deepracer/service/upstream deepracer/service/patches
git commit -m "chore(service): bump upstream to <new-upstream-tag>"
```
