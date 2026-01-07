"""
Configuration management for Temporal + Claude Agent system.
Loads environment variables and provides configuration for all system components.
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
from pathlib import Path

# Get project root directory (where .env lives)
PROJECT_ROOT = Path(__file__).parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """System configuration loaded from environment variables"""
    
    # Anthropic Claude API
    anthropic_api_key: str = Field(..., alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-haiku-4-5", alias="ANTHROPIC_MODEL")
    
    # Temporal Configuration
    temporal_host: str = Field(..., alias="TEMPORAL_HOST")
    temporal_namespace: str = Field(..., alias="TEMPORAL_NAMESPACE")
    temporal_api_key: str = Field(..., alias="TEMPORAL_API")
    temporal_mtls_cert: Optional[str] = Field(None, alias="TEMPORAL_MTLS_CERT")
    temporal_mtls_key: Optional[str] = Field(None, alias="TEMPORAL_MTLS_KEY")
    
    # E2B Configuration
    e2b_api_key: Optional[str] = Field(None, alias="E2B_API_KEY")
    e2b_claude_template_id: str = Field(default="vqvrux7k1ay0yvczh8e3", alias="E2B_CLAUDE_TEMPLATE_ID")
    e2b_timeout_seconds: int = Field(default=0, alias="E2B_TIMEOUT_SECONDS")  # 0 = no timeout
    
    # Database
    database_path: str = Field(default=str(PROJECT_ROOT / "task_management.db"), alias="DATABASE_PATH")
    
    # Workflow Settings
    workflow_demo_duration_minutes: int = Field(default=10, alias="WORKFLOW_DEMO_DURATION_MINUTES")
    workflow_production_duration_minutes: int = Field(default=180, alias="WORKFLOW_PRODUCTION_DURATION_MINUTES")
    checkpoint_interval_minutes: int = Field(default=2, alias="CHECKPOINT_INTERVAL_MINUTES")
    
    # Default User Settings
    default_user_id: str = Field(default="default_user", alias="DEFAULT_USER_ID")
    default_timezone: str = Field(default="UTC", alias="DEFAULT_TIMEZONE")
    
    # API Settings
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8500, alias="API_PORT")
    
    class Config:
        env_file = str(ENV_FILE)  # Absolute path to .env file
        case_sensitive = False
        extra = "ignore"  # Ignore extra env vars


# Global settings instance
# Purpose: Single source of truth for configuration across all modules
settings = Settings()

