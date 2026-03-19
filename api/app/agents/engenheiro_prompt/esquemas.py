from typing import Literal, Optional

from pydantic import BaseModel


class MensagemHistorico(BaseModel):
    papel: Literal["usuario", "assistente"]
    conteudo: str


class EntradaAgente(BaseModel):
    mensagem: str
    historico: list[MensagemHistorico] = []


class RespostaAgente(BaseModel):
    resposta: str
    fase: Literal["coletando", "finalizado", "implementado"]
    markdown_final: Optional[str] = None
    prompt_engenharia: Optional[str] = None
    arquivos_implementados: list[str] = []
