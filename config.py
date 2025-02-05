import tomli as toml
from munch import DefaultMunch

with open("config.toml", "rb") as f:
    config = toml.load(f)
    config = DefaultMunch.fromDict(config)