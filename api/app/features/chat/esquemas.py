from pydantic import BaseModel


class MensagemEntrada(BaseModel):
    texto: str


class MensagemSaida(BaseModel):
    resposta: str
