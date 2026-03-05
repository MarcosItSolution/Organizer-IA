from fastapi import APIRouter, Depends

from app.features.chat.esquemas import MensagemEntrada, MensagemSaida
from app.features.chat.servico import ServicoChat

roteador_chat = APIRouter()


def obter_servico_chat() -> ServicoChat:
    return ServicoChat()


@roteador_chat.post("/", response_model=MensagemSaida)
async def enviar_mensagem(
    mensagem: MensagemEntrada,
    servico: ServicoChat = Depends(obter_servico_chat),
) -> MensagemSaida:
    return servico.processar_mensagem(mensagem)
