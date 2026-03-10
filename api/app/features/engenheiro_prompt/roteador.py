from fastapi import APIRouter, Depends

from app.features.engenheiro_prompt.esquemas import EntradaAgente, RespostaAgente
from app.features.engenheiro_prompt.servico import ServicoAgenteArquitetoPrompts

roteador_engenheiro_prompt = APIRouter()


def obter_servico() -> ServicoAgenteArquitetoPrompts:
    return ServicoAgenteArquitetoPrompts()


@roteador_engenheiro_prompt.post("/", response_model=RespostaAgente)
async def processar_mensagem(
    entrada: EntradaAgente,
    servico: ServicoAgenteArquitetoPrompts = Depends(obter_servico),
) -> RespostaAgente:
    return await servico.processar_mensagem(entrada)
