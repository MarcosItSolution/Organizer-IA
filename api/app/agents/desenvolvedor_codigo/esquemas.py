from typing import Literal

from pydantic import BaseModel


class ArquivoGerado(BaseModel):
    caminho: str
    conteudo: str
    descricao: str


class EntradaDesenvolvedorCodigo(BaseModel):
    prompt_engenharia: str


class RespostaDesenvolvedorCodigo(BaseModel):
    arquivos_gerados: list[ArquivoGerado] = []
    titulo: str = ""
    descricao: str = ""
    fase: Literal["finalizado", "erro"]
    mensagem: str
