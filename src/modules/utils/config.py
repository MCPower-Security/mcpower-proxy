"""
Centralized configuration loader with caching
Reads from ~/.mcpower/config file
"""
from pathlib import Path
from typing import Dict, Optional

from modules.logs.logger import MCPLogger


def load_default_config() -> Dict[str, str]:
    """Load default configuration from embedded constants"""
    try:
        config_data = {
            "API_URL": "https://api.mcpower.tech",
            "DEBUG": "0",
            "ALLOW_BLOCK_OVERRIDE": "1",
            "MIN_BLOCK_SEVERITY": "low"
        }
        return config_data
    except Exception as e:
        raise RuntimeError(f"FATAL: Failed to load default config: {e}")


# Load default configuration from shared file
default_config = load_default_config()


class ConfigManager:
    """Singleton configuration manager with caching and file monitoring"""

    _instance: Optional['ConfigManager'] = None
    _config: Optional[Dict[str, str]] = None
    _observer = None  # Will be watchdog Observer if available

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def config(self) -> Dict[str, str]:
        """Get cached config, loading if necessary"""
        if self._config is None:
            self._config = ConfigManager._load_config()
        return self._config

    @staticmethod
    def _load_config() -> Dict[str, str]:
        """Load config from ~/.mcpower/config file"""
        config_path = ConfigManager.get_config_path()

        # Create default config if it doesn't exist
        if not config_path.exists():
            ConfigManager._create_default_config(config_path)

        content = config_path.read_text()
        # Parse key=value configuration content
        new_config = {}
        for line in content.split('\n'):
            line = line.strip()
            if line and '=' in line and not line.startswith('#'):
                key, value = line.split('=', 1)
                new_config[key.strip()] = value.strip()
        return new_config

    @classmethod
    def get_config_path(cls):
        return ConfigManager.get_user_config_dir() / 'config'

    @staticmethod
    def _create_default_config(config_path: Path):
        """Create default config file"""
        config_path.parent.mkdir(exist_ok=True)

        # Convert to key=value format
        config_lines = ['# MCPower Configuration']
        for key, value in default_config.items():
            config_lines.append(f'{key}={value}')

        config_path.write_text('\n'.join(config_lines) + '\n')

    @staticmethod
    def get_user_config_dir() -> Path:
        """Get user config directory (~/.mcpower)"""
        return Path.home() / '.mcpower'

    def get(self, key: str, default: str = None) -> str:
        """Get config value with optional default"""
        return self.config.get(key, default)

    def reload(self, logger: MCPLogger):
        """Force reload config from file"""
        self._config = None
        logger.debug("Config reloaded from ~/.mcpower/config")

    def start_monitoring(self, logger: MCPLogger):
        """Start file system monitoring using watchdog (event-driven)"""
        try:
            # Try to import watchdog - graceful fallback if not available
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler

            if self._observer is not None:
                return  # Already monitoring

            class ConfigFileHandler(FileSystemEventHandler):
                def __init__(self, config_manager):
                    self.config_manager = config_manager
                    self.config_path = str(config_manager.get_user_config_dir() / 'config')

                def on_modified(self, event):
                    if not event.is_directory and event.src_path == self.config_path:
                        logger.debug("Config file changed (event), reloading...")
                        self.config_manager.reload(logger)

                def on_created(self, event):
                    if not event.is_directory and event.src_path == self.config_path:
                        logger.debug("Config file created (event), reloading...")
                        self.config_manager.reload(logger)

            self._observer = Observer()
            event_handler = ConfigFileHandler(self)
            watch_dir = str(self.get_user_config_dir())

            self._observer.schedule(event_handler, watch_dir, recursive=False)
            self._observer.start()
            logger.debug("Started monitoring ~/.mcpower/config (event-driven)")

        except ImportError:
            logger.warning("watchdog not available, install with: pip install watchdog")
            logger.warning("Falling back to manual reload - call config.reload() when needed")
        except Exception as e:
            logger.warning(f"Failed to start file monitoring: {e}")
            logger.warning("Falling back to manual reload - call config.reload() when needed")

    def stop_monitoring(self, logger: MCPLogger):
        """Stop file system monitoring"""
        if self._observer is not None:
            self._observer.stop()
            self._observer.join()
            self._observer = None
            logger.debug("Stopped monitoring ~/.mcpower/config")


# Singleton instance
config = ConfigManager()


# Convenience functions

def resolve_config_path(path_value: str) -> str:
    """
    Resolve a configuration path value, handling ./ as relative to config folder
    
    Args:
        path_value: The path value from config (e.g., './log.txt', '/tmp/log.txt', 'log.txt')
    
    Returns:
        Resolved absolute path string
    """
    if path_value.startswith('./'):
        config_dir = ConfigManager.get_user_config_dir()
        return str(config_dir / path_value[2:])  # Remove ./ prefix

    return path_value


def get_api_url() -> str:
    """Get default API URL"""
    key = 'API_URL'
    return config.get(key, default_config.get(key))


def get_log_path() -> str:
    """Get default log file path """
    return str(ConfigManager.get_user_config_dir() / 'mcp-wrapper.log')


def get_audit_trail_path() -> str:
    """Get audit trail log file path (same directory as main log)"""
    return str(ConfigManager.get_user_config_dir() / 'audit_trail.log')


def _get_bool_config(key: str) -> bool:
    """Parse boolean config value"""
    value = str(config.get(key, default_config.get(key)))
    return value.lower() in ('true', '1', 'yes', 'on')


def is_debug_mode() -> bool:
    """Get debug mode setting"""
    return _get_bool_config('DEBUG')


def get_user_id(logger: MCPLogger) -> str:
    """Get or create user ID from ~/.mcpower/uid (never fails)"""
    from modules.utils.ids import get_or_create_user_id
    return get_or_create_user_id(logger)


def get_allow_block_override() -> bool:
    """Get ALLOW_BLOCK_OVERRIDE setting"""
    return _get_bool_config('ALLOW_BLOCK_OVERRIDE')


def get_min_block_severity() -> str:
    """Get MIN_BLOCK_SEVERITY setting"""
    key = 'MIN_BLOCK_SEVERITY'
    return config.get(key, default_config.get(key)).lower()


def compare_severity(actual: str, minimum: str) -> bool:
    """
    Compare if actual severity meets or exceeds minimum severity threshold.
    
    Args:
        actual: The actual severity level (low, medium, high, critical, unknown)
        minimum: The minimum required severity level (low, medium, high, critical)
        
    Returns:
        True if actual >= minimum, False otherwise
        
    Note:
        - Severity order: low < medium < high < critical
        - 'unknown' is treated as 'high' (fail-safe)
    """
    severity_order = {
        'low': 0,
        'medium': 1,
        'high': 2,
        'critical': 3
    }
    
    # Normalize to lowercase
    actual_normalized = actual.lower()
    minimum_normalized = minimum.lower()
    
    # Treat 'unknown' as 'high' (fail-safe)
    if actual_normalized == 'unknown':
        actual_normalized = 'high'
    
    # Get severity levels, default to 'high' if invalid
    actual_level = severity_order.get(actual_normalized, 2)
    minimum_level = severity_order.get(minimum_normalized, 0)
    
    return actual_level >= minimum_level
