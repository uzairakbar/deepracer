from gymnasium.envs.registration import register

register(
    id='deepracer-v0',
    entry_point='deepracer.envs:DeepracerGymEnv'
)


def close(env, cache: bool | None=None):
    '''Close a (possibly gym.make-wrapped) DeepRacer env, overriding its cache flag.

    The container's fate is normally the env's `cache` flag (set at gym.make), and a
    plain `env.close()` already honors it through the wrapper. Use this helper (or
    `env.unwrapped.close(cache=…)`) only to *override* that decision at close time —
    e.g. `deepracer.close(env, cache=False)` to force-stop a cache=True env.
    '''
    env.unwrapped.close(cache=cache)


def shutdown_all():
    '''Stop every DeepRacer container this process is managing, including any
    kept warm. Call when you are completely done (or to reclaim warm
    containers).'''
    from deepracer.service.manager import SimulationManager
    if SimulationManager._instance is not None:
        SimulationManager._instance.shutdown_all()


def running() -> list[str]:
    '''Names of DeepRacer simulators currently running on this host (across any
    kernels/processes). Handy to see what is up before/after your work.'''
    import shutil
    import subprocess
    from deepracer.service.spec import LABEL_NS
    names: list[str] = []
    for engine in ('podman', 'docker'):
        if shutil.which(engine) is None:
            continue
        result = subprocess.run(
            [engine, 'ps', '--filter', f'label={LABEL_NS}.managed=true',
             '--format', '{{.Names}}'],
            capture_output=True, text=True,
        )
        names += [n for n in result.stdout.split() if n]
    return names
