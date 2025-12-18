import uuid
import csv
import functools
import getpass
import inspect
import json
import multiprocessing
import pathlib
import time
from typing import Union

import psutil
import toolviper.utils.logger as logger


def cpu_usage(stop_event, filename):
    if filename is None:
        filename = f"cpu_usage_{uuid.uuid4()}.csv"

    with open(filename, "w") as csvfile:
        number_of_cores = psutil.cpu_count(logical=True)

        core_list = [f"c{core}" for core in range(number_of_cores)]
        writer = csv.writer(csvfile, delimiter=",", lineterminator="\n")
        writer.writerow(core_list)
        while not stop_event.is_set():
            usage = psutil.cpu_percent(percpu=True, interval=1)
            writer.writerow(usage)


def monitor(filename=None):
    def function_wrapper(function):
        @functools.wraps(function)
        def wrapper(*args, **kwargs):
            stop_event = multiprocessing.Event()

            monitor_process = multiprocessing.Process(
                target=cpu_usage, args=(stop_event, filename)
            )
            monitor_process.start()

            time.sleep(1)

            try:
                results = function(*args, **kwargs)
            finally:
                stop_event.set()
                monitor_process.join(timeout=1)
                monitor_process.terminate()

            return results

        return wrapper

    return function_wrapper


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
                if not config_open:
                    config = load_config()

                    if config is None:
                        raise FileNotFoundError

                    config_open = True

                kwargs[arg] = config[name][arg]

        if password_ is None:
            logger.info("Please enter password:\n")
            kwargs["password"] = getpass.getpass(
                prompt=f"(username={kwargs['username']}): "
            )

        return function(*args, **kwargs)

    return wrapper
