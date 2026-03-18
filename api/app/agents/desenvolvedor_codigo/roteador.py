from fastapi import APIRouter, Depends

from app.agents.desenvolvedor_codigo.esquemas import EntradaDesenvolvedorCodigo, RespostaDesenvolvedorCodigo
from app.agents.desenvolvedor_codigo.servico import ServicoDesenvolvedorCodigo

roteador_desenvolvedor_codigo = APIRouter()


def obter_servico() -> ServicoDesenvolvedorCodigo:
    return ServicoDesenvolvedorCodigo()


@roteador_desenvolvedor_codigo.post("/", response_model=RespostaDesenvolvedorCodigo)
async def processar_prompt(
    entrada: EntradaDesenvolvedorCodigo,
    servico: ServicoDesenvolvedorCodigo = Depends(obter_servico),
) -> RespostaDesenvolvedorCodigo:
    return await servico.processar_prompt(entrada)
