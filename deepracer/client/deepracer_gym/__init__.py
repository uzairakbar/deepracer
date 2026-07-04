from gymnasium.envs.registration import register

register(
    id='deepracer-v0',
    entry_point='deepracer_gym.envs:DeepracerGymEnv'
)


def close(env, cache: bool | None=None):
    '''Close a (possibly gym.make-wrapped) DeepRacer env, with an optional cache
    override.

    `gym.make` wraps the env, and gymnasium's `Wrapper.close()` does not forward
    keyword arguments, so `wrapped_env.close(cache=False)` raises. Use this helper
    (or `env.unwrapped.close(cache=…)`) to override the cache decision at close.
    A plain `env.close()` always works and uses the constructor's `cache` value.
    '''
    env.unwrapped.close(cache=cache)


def shutdown_all(include_cached: bool=True):
    '''Stop every DeepRacer container this process is managing, including any
    kept warm by cache=True. Call when you are completely done (or to reclaim
    warm containers).'''
    from deepracer_gym.service.manager import SimulationManager
    if SimulationManager._instance is not None:
        SimulationManager._instance.shutdown_all(include_cached=include_cached)


def running() -> list[str]:
    '''Names of DeepRacer simulators currently running on this host (across any
    kernels/processes). Handy to see what is up before/after your work.'''
    import shutil
    import subprocess
    from deepracer_gym.service.spec import LABEL_NS
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
