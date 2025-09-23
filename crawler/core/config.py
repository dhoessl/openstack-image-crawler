import yaml

from loguru import logger
from pathlib import Path


def config_read(configfile_path: str, msg: str = "config") -> dict:
    path = Path(configfile_path)
    if not path.is_file():
        logger.error(f"Could not find file at {configfile_path}")
        return None
    try:
        config = yaml.safe_load(Path(configfile_path).read_text())
    except PermissionError:
        logger.error("could not open config at - please check file permissions")
        return None
    except yaml.YAMLError as error:
        logger.error(f"Could not read file as YAML\n{error}")
        return None
    logger.info(f"Successfully read {msg} from {configfile_path}")
    return config
