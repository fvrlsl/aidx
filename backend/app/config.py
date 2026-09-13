from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "良心商家"
    env: Literal["local", "prod"] = "local"
    public_base_url: str = "http://localhost:8000"
    secret_key: str = "change-me-in-prod"
    jwt_expire_minutes: int = 60 * 24 * 30

    # 数据库：留空则使用本地 SQLite（极简模式），生产使用 postgresql+psycopg://
    database_url: str = "sqlite:///./data/app.db"

    # Redis：留空则限流/队列退化为进程内实现（极简模式）
    redis_url: str = ""
    celery_eager: bool = True
    scheduler_inprocess: bool = True

    # 对象存储：留空则用本地目录 ./data/media 并由 API 静态托管
    s3_endpoint: str = ""
    s3_bucket: str = "goodmerchant"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_public_base: str = ""
    media_dir: str = "./data/media"

    # LLM（OpenAI 兼容协议）：留空 key 则使用规则 mock
    llm_api_base: str = ""
    llm_api_key: str = ""
    llm_model: str = "qwen-plus"

    # 微信
    wx_appid: str = ""
    wx_secret: str = ""
    wx_mock: bool = True

    # 自动发布策略：positive_and_a_negative | all | none
    auto_publish_policy: str = "positive_and_a_negative"
    entity_auto_attach_threshold: int = 90
    entity_candidate_threshold: int = 60

    # 采集：新闻 RSS 模板，{keyword} 会被替换；多个用逗号分隔
    news_rss_templates: str = ""
    crawl_user_agent: str = "GoodMerchantBot/0.1 (+contact@example.com)"

    admin_default_username: str = "admin"
    admin_default_password: str = "admin123"

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
