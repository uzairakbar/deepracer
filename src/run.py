import os
import time
import torch
import datetime
import numpy as np
from loguru import logger
from munch import munchify
from torch.utils.tensorboard import SummaryWriter

from src.agents import RandomAgent
from src.utils import (
    device,
    set_seed,
    make_environment,
    RUNS_DIR,
    MODELS_DIR,
)


DEVICE = device()
# Default training hyper-parameters (these are just dummy example values).
# Override any of them by passing a dict to run(), e.g. run({'total_timesteps': 2048}).
DEFAULT_HYPER_PARAMS: dict = {
    'seed':             42,
    'cpu_only':         False,
    'environment':      'deepracer-v0',
    'experiment_name':  'time_trial',
    'learning_rate':    2e-2,
    'total_timesteps':  1024,
    'gamma':            0.99,
}


def tensor(x: np.array, type=torch.float, device=DEVICE) -> torch.Tensor:
    return torch.tensor(x, dtype=type, device=device)


def zeros(x: tuple, type=torch.float, device=DEVICE) -> torch.Tensor:
    return torch.zeros(x, dtype=type, device=device)


def run(hparams: dict | None=None, agent_config: dict | None=None, track_config: dict | None=None):
    start_time = time.time()

    # start from the defaults, override with anything passed in
    final_hparams = dict(DEFAULT_HYPER_PARAMS)
    if hparams:
        final_hparams.update(hparams)
    args = munchify(final_hparams)
    
    # save parameters and/or configs if you wish
    run_name = (
        f"{args.environment}__{args.experiment_name}__{args.seed}__{int(time.time())}"
    )
    writer = SummaryWriter(f"{RUNS_DIR}/{run_name}")
    writer.add_text(
        'hyperparameters',
        "|param|value|\n|-|-|\n%s" % (
            "\n".join(
                [f"|{key}|{value}|" for key, value in vars(args).items()]
            )
        ),
    )
    
    set_seed(args.seed)

    env = make_environment(
        args.environment, agent_config=agent_config, track_config=track_config
    )
    agent = RandomAgent(environment=env)

    # start rolling
    observation, info = env.reset()
    for step in range(args.total_timesteps):
        
        action = agent.get_action(observation)
        observation, reward, terminated, truncated, info = env.step(
            action
        )

        # just a dummy log to give you an example
        writer.add_scalar(
            'charts/steps', step, step
        )

        if terminated or truncated:
            
            et = time.time()-start_time
            et = str(datetime.timedelta(seconds=round(et)))

            logger.info(
                f'step={step}, ' + \
                f'episodic_return={info["episode"]["r"]}, ' + \
                f'episodic_length={info["episode"]["l"]}, ' + \
                f'time_elapsed={et}'
            )
            
            writer.add_scalar(
                'charts/episodic_return', info['episode']['r'], step
            )
            writer.add_scalar(
                'charts/episodic_length', info['episode']['l'], step
            )

            break
    
    # save your agent/model often
    os.makedirs(MODELS_DIR, exist_ok=True)
    torch.save(
        agent, os.path.join(MODELS_DIR, f'{agent.name}.torch')
    )
    logger.info(
        f'Model {agent.name} saved.'
    )

    env.close()
    writer.close()
