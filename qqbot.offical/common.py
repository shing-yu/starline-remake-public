from botpy import logging
import tomli as toml
from munch import DefaultMunch

with open("config.toml", "rb") as f:
    config = toml.load(f)
    config = DefaultMunch.fromDict(config)

botid = config.botid
secret = config.secret
endpoint = config.api.endpoint

logger = logging.get_logger()
