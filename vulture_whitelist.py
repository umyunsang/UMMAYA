# Vulture whitelist — false positives from framework patterns.
# See: https://github.com/jendrikseipp/vulture#whitelisting

# Pydantic @field_validator / @model_validator require cls as first arg
cls  # noqa: F821

# __aexit__ protocol requires *args
args  # noqa: F821

# typer Option with callback — parameter parsed by typer, never read in function body
version  # noqa: F821

# InMemoryHistory.store_string override — base class uses string before calling super
string  # noqa: F821

position  # noqa: F821
pretty  # noqa: F821
