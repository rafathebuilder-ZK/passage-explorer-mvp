"""Configuration management for Passage Explorer."""
import os
import yaml
from pathlib import Path
from typing import Optional


class Config:
    """Manages application configuration."""
    
    DEFAULT_CONFIG = {
        'library_path': './Library',
        'library_path_absolute': False,
        'max_passage_length': 420,
        'context_words': 400,
        'session_history_days': 30,
        'initial_indexing_batch_size': 8,
        'progressive_indexing_batch_size': 4,
        # Stage 2+ settings
        'embedding_model': 'local',  # 'local' or 'openai' (only local implemented)
        'openai_api_key': None,
    }
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize configuration.
        
        Args:
            config_path: Path to config file. If None, uses default location.
        """
        self.project_root = Path(__file__).parent.parent
        self.config_path = Path(config_path) if config_path else self.project_root / 'config.yaml'
        self._config = {}
        self._load_config()
    
    def _load_config(self):
        """Load configuration from file or create default."""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    self._config = yaml.safe_load(f) or {}
            except Exception as e:
                raise ValueError(f"Failed to load config file {self.config_path}: {e}")
        else:
            # Create default config
            self._config = self.DEFAULT_CONFIG.copy()
            self._save_config()
    
    def _save_config(self):
        """Save current configuration to file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, 'w') as f:
            yaml.dump(self._config, f, default_flow_style=False)
    
    def get(self, key: str, default=None):
        """Get configuration value."""
        return self._config.get(key, self.DEFAULT_CONFIG.get(key, default))
    
    def set(self, key: str, value):
        """Set configuration value."""
        self._config[key] = value
        self._save_config()
    
    @property
    def library_path(self) -> Path:
        """Get library path as absolute Path."""
        path_str = self.get('library_path', './Library-Sample')
        if self.get('library_path_absolute', False):
            return Path(path_str)
        else:
            return (self.project_root / path_str).resolve()
    
    @library_path.setter
    def library_path(self, value: str):
        """Set library path."""
        self.set('library_path', value)
    
    def validate_library_path(self) -> tuple[bool, Optional[str]]:
        """Validate library path exists and is readable.
        
        Returns:
            (is_valid, error_message)
        """
        lib_path = self.library_path
        if not lib_path.exists():
            return False, f"Library path does not exist: {lib_path}"
        if not lib_path.is_dir():
            return False, f"Library path is not a directory: {lib_path}"
        if not os.access(lib_path, os.R_OK):
            return False, f"Library path is not readable: {lib_path}"
        return True, None
