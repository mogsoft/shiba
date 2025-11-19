import functools
import inspect
import json
import pathlib
from typing import Union

import toolviper.utils.logger as logger


def load_config() -> Union[dict, None]:
    config_file = (
        pathlib.Path(__file__).parent.joinpath("config") / "remote.config.json"
    )

    if config_file.exists():
        with open(config_file, "r") as file:
            return json.load(file)

    else:
        logger.error(f"Config file not found at {config_file}")
        return None


def credentials(function):
    @functools.wraps(function)
    def wrapper(*args, **kwargs):
        arguments = inspect.getcallargs(function, *args, **kwargs)
        config_open = False
        config = {}

        password_ = arguments.pop("password")

        name = function.__name__

        for arg, value in arguments.items():
            if value is None:
                if config_open is False:
                    config = load_config()

                    if config is None:
                        raise FileNotFoundError

                    config_open = True

                kwargs[arg] = config[name][arg]

        if password_ is None:
            raise ValueError("Password is required")

        return function(*args, **kwargs)

    return wrapper
