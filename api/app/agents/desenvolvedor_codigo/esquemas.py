from typing import Literal, Optional

from pydantic import BaseModel


class ArquivoGerado(BaseModel):
    caminho: str
    conteudo: str
    descricao: str


class EntradaDesenvolvedorCodigo(BaseModel):
    prompt_engenharia: str


class RespostaDesenvolvedorCodigo(BaseModel):
    url_pull_request: Optional[str] = None
    arquivos_gerados: list[ArquivoGerado] = []
    titulo_pr: str = ""
    fase: Literal["finalizado", "erro"]
    mensagem: str
