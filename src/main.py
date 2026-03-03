"""Script to launch agents according to configuration.

設定に応じたエージェントを起動するスクリプト.
"""

import argparse
import logging
import multiprocessing
from pathlib import Path

import yaml

from starter import connect

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


def execute(config_path: Path) -> None:
    """Execute based on the configuration file.

    設定ファイルをもとに実行する.

    Args:
        config_path (Path): Path to the configuration file / 設定ファイルのパス
    """
    print(f"Loading config from {config_path}")
    try:
        with Path.open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f)
            print("Config loaded successfully")
            print(f"Config keys: {list(config.keys())}")
            logger.info("設定ファイルを読み込みました")

        agent_num = int(config["agent"]["num"])
        print(f"Agent num: {agent_num}")
        threads: list[multiprocessing.Process] = []
        for i in range(agent_num):
            print(f"Starting agent {i + 1}")
            thread = multiprocessing.Process(
                target=connect,
                args=(config, i + 1),
            )
            threads.append(thread)
            thread.start()
        for thread in threads:
            thread.join()
        print("All agents finished")
    except Exception as e:
        print(f"Error in execute: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        nargs="+",
        default=["./config/config.yml"],
        help="設定ファイルのパス (複数指定可)",
    )
    args = parser.parse_args()

    print(f"Args config: {args.config}")
    paths: list[Path] = []
    for config_path in args.config:
        glob_path = Path(config_path)
        paths.extend([path for path in Path.glob(glob_path.parent, glob_path.name) if path.is_file()])

    print(f"Paths: {paths}")
    multiprocessing.set_start_method("spawn")
    threads: list[multiprocessing.Process] = []
    for path in paths:
        print(f"Starting execute for {path}")
        thread = multiprocessing.Process(
            target=execute,
            args=(Path(path),),
        )
        threads.append(thread)
        thread.start()
    for thread in threads:
        thread.join()

    print("Main process finished")
