# deepracer/service — the simulator image, as a patch series over upstream

The DeepRacer simulator image is built from the **public**
[`aws-deepracer-community/deepracer-simapp`](https://github.com/aws-deepracer-community/deepracer-simapp)
plus a small set of patches that repurpose it into a pure, training-free
simulation served to the `deepracer_gym` client over ZMQ. **We do not fork the
upstream** — we version only our delta.

## Layout
```
service/
├── upstream/      git submodule → aws-deepracer-community/deepracer-simapp, pinned (v6.0.5).
│                  The single global pin: its commit is the base for every patch.
├── patches/       our delta as a git-am-able series (git format-patch output).
├── scripts/       init_workspace / export_patches / build / bump_upstream.
├── workspace/     git-IGNORED dev sandbox (created on demand). Edit here, not in upstream/.
└── README.md
```

The image = `upstream @ pinned` + `patches/*` → built by `build-zmqsim.sh`
(which the patches add): it builds the CPU base (compiling the patched `bundle/`)
then layers the ZMQ-sim overlay. Output: `uzairakbar/deepracer-test:v0`.

## Develop the simulator (edit the patched source)
```bash
deepracer/service/scripts/init_workspace.sh     # upstream@pin + patches, as commits, in workspace/
cd deepracer/service/workspace                  # a normal git repo — edit, commit, test
# ... make changes, git commit ...
deepracer/service/scripts/export_patches.sh     # write commits back to ../patches/
git add deepracer/service/patches && git commit # in the monorepo
```
Never edit `upstream/` directly — it's read-only vendored source. `workspace/` is
git-ignored, so you can't accidentally disturb the submodule pointer.

## Build the image (needs Docker; not available on PACE)
```bash
ARCH=amd64 OUT_IMAGE=uzairakbar/deepracer-test:v0-amd64 PUSH=1 \
  deepracer/service/scripts/build.sh
```
CI (`.github/workflows/build-service-image.yml`) does this for amd64+arm64 and
stitches a multi-arch manifest. Offline-capable: it reads the vendored submodule,
no network fetch of upstream at build time.

## Bump the upstream version (deliberate, reviewed)
```bash
deepracer/service/scripts/bump_upstream.sh <new-upstream-tag>
# resolve any 3-way conflicts in workspace/, rebuild + validate, then:
deepracer/service/scripts/export_patches.sh
git add deepracer/service/upstream deepracer/service/patches
git commit -m "chore(service): bump upstream to <new-upstream-tag>"
```
Moving the submodule pointer is the single-place version change.
