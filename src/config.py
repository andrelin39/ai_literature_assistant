"""Application configuration loaded from .env via pydantic-settings."""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


# 專案根目錄絕對路徑，確保從任何 cwd 執行都能找到 .env
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # API keys
    anthropic_api_key: str
    semantic_scholar_api_key: str = ""  # 空字串代表未認證模式

    # Contact (for Crossref/OpenAlex polite pool & Semantic Scholar)
    contact_email: str

    # Claude models
    claude_model_default: str = "claude-sonnet-4-6"
    claude_model_advanced: str = "claude-opus-4-7"

    # Database
    database_path: str = "data/projects.db"


# Module-level singleton — 其他模組 import 這個
try:
    settings = Settings()
except Exception as e:
    import sys
    print(f"\n❌ 設定載入失敗: {e}", file=sys.stderr)
    print(f"   請確認 .env 檔案位於 {ENV_FILE}", file=sys.stderr)
    print(f"   並包含必要欄位（ANTHROPIC_API_KEY, CONTACT_EMAIL）\n", file=sys.stderr)
    raise


# 向後相容：保留 get_config() 但標記為 deprecated
def get_config() -> Settings:
    """Deprecated: use `from src.config import settings` instead."""
    import warnings
    warnings.warn(
        "get_config() is deprecated, use `from src.config import settings`",
        DeprecationWarning,
        stacklevel=2,
    )
    return settings
