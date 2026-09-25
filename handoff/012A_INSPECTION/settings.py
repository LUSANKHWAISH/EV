import os
from dotenv import load_dotenv
from pathlib import Path

# Load .env file if it exists, without overriding existing environment variables
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=False)

class Settings:
    """
    Configuration for E.V. Enhanced Virtual Intelligence.
    Reads from environment variables (with .env fallback).
    """
    def __init__(self):
        self.EV_LOG_LEVEL = self._get_env_str('EV_LOG_LEVEL', 'INFO')
        self.EV_DRY_RUN = self._get_env_bool('EV_DRY_RUN', False)
        self.EV_MAX_COMMAND_TIMEOUT = self._get_env_int('EV_MAX_COMMAND_TIMEOUT', 120)

    def _get_env_str(self, key: str, default: str) -> str:
        value = os.getenv(key, default)
        # Validate log level
        allowed = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if value.upper() not in allowed:
            raise ValueError(f"{key} must be one of {allowed}")
        return value.upper()

    def _get_env_bool(self, key: str, default: bool) -> bool:
        value = os.getenv(key)
        if value is None or value == "":
            return default
        # Accept common true/false strings
        true_values = {"true", "1", "yes", "on"}
        false_values = {"false", "0", "no", "off"}
        lower_val = value.lower()
        if lower_val in true_values:
            return True
        elif lower_val in false_values:
            return False
        else:
            raise ValueError(f"{key} must be a boolean (got '{value}')")

    def _get_env_int(self, key: str, default: int) -> int:
        value = os.getenv(key)
        if value is None:
            return default
        try:
            ival = int(value)
        except ValueError:
            raise ValueError(f"{key} must be an integer")
        if ival <= 0:
            raise ValueError(f"{key} must be a positive integer")
        return ival

# Singleton instance
settings = Settings()
