"""Maintenance CLI: stop & remove orphaned DeepRacer sims.

    python -m deepracer_gym.clean

Removes any managed containers (Docker/Podman) and Apptainer instances left
running (e.g. keep_warm sims, or leftovers from a crashed/killed kernel), plus
their per-instance overlays and Apptainer's never-rotated instance logs. Best-
effort and idempotent — safe to run anytime.
"""
import os
import glob
import json
import shutil
import subprocess

from deepracer_gym.service.spec import LABEL_NS


def _run(argv):
    return subprocess.run(argv, capture_output=True, text=True)


def _clean_oci(binary: str) -> None:
    if shutil.which(binary) is None:
        return
    result = _run([binary, 'ps', '-aq', '--filter', f'label={LABEL_NS}.managed=true'])
    ids = [i for i in result.stdout.split() if i]
    for cid in ids:
        _run([binary, 'rm', '-f', cid])          # -f stops then removes
    print(f'{binary}: removed {len(ids)} managed container(s).')


def _clean_apptainer() -> None:
    if shutil.which('apptainer') is None:
        return
    result = _run(['apptainer', 'instance', 'list', '--json'])
    try:
        instances = json.loads(result.stdout).get('instances', [])
    except Exception:
        instances = []
    names = [
        i['instance'] for i in instances
        if str(i.get('instance', '')).startswith('deepracer-')
    ]
    for name in names:
        _run(['apptainer', 'instance', 'stop', name])
    for overlay in glob.glob('/tmp/deepracer_*'):
        shutil.rmtree(overlay, ignore_errors=True)
    # Apptainer never rotates its per-instance logs; they accumulate forever and
    # a stale FATAL: line poisons a later start of the same name (the backend
    # clears these per-name on start, but sweep leftovers here too).
    log_base = os.path.expanduser('~/.apptainer/instances/logs')
    logs = glob.glob(os.path.join(log_base, '*', '*', 'deepracer-*.out')) + \
        glob.glob(os.path.join(log_base, '*', '*', 'deepracer-*.err'))
    for path in logs:
        try:
            os.remove(path)
        except OSError:
            pass
    print(f'apptainer: stopped {len(names)} instance(s), cleared overlays + '
          f'{len(logs)} stale log file(s).')


def main() -> None:
    for binary in ('docker', 'podman'):
        _clean_oci(binary)
    _clean_apptainer()
    print('Done.')


if __name__ == '__main__':
    main()
