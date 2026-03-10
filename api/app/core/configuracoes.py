from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracoes(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    nome_aplicacao: str = "Organizer IA"
    versao: str = "0.1.0"
    porta: int = 8000
    origens_permitidas: list[str] = ["http://localhost:4200"]
    groq_api_key: SecretStr


configuracoes = Configuracoes()
