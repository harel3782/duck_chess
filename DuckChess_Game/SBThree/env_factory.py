"""
EnvFactory — single-line instantiation for any Duck Chess RL stage.

Examples::

    # One environment
    env = EnvFactory.create("stage11", env_index=0)

    # Vectorised environment for training
    vec_env = EnvFactory.make_vec("stage11", n_envs=8)

    # List all registered names
    print(EnvFactory.list_stages())
"""
from __future__ import annotations

from typing import List

from stable_baselines3.common.vec_env import SubprocVecEnv

from DuckChess_Game.SBThree.base.env_base import BaseDuckChessEnv
from DuckChess_Game.SBThree.env_registry import REGISTRY


class EnvFactory:
    """Creates Duck Chess environments by stage name."""

    @staticmethod
    def create(name: str, env_index: int = 0, render_mode=None) -> BaseDuckChessEnv:
        """
        Return a single BaseDuckChessEnv configured for the given stage.

        Args:
            name:        Stage key from REGISTRY (e.g. ``"stage11"``).
            env_index:   Worker index forwarded to the env; 0 = chief worker.
            render_mode: Passed through to BaseDuckChessEnv (unused for training).

        Raises:
            KeyError: If *name* is not in the registry.
        """
        if name not in REGISTRY:
            available = ", ".join(sorted(REGISTRY))
            raise KeyError(
                f"Unknown stage {name!r}. Available: {available}"
            )
        config = REGISTRY[name]()   # factory call → fresh EnvConfig
        return BaseDuckChessEnv(config, env_index=env_index, render_mode=render_mode)

    @staticmethod
    def make_vec(name: str, n_envs: int = 8) -> SubprocVecEnv:
        """
        Return a SubprocVecEnv of *n_envs* workers for the given stage.

        Worker 0 is designated the chief worker (env_index=0) and is the
        only worker that saves replay files when ``replay_chief_only=True``.

        Args:
            name:   Stage key from REGISTRY (e.g. ``"stage12"``).
            n_envs: Number of parallel workers.
        """
        def _make_env(rank: int):
            def _init():
                return EnvFactory.create(name, env_index=rank)
            return _init

        return SubprocVecEnv([_make_env(i) for i in range(n_envs)])

    @staticmethod
    def list_stages() -> List[str]:
        """Return sorted list of all registered stage names."""
        return sorted(REGISTRY.keys())
