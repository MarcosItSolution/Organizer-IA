from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.configuracoes import configuracoes
from app.features.chat.roteador import roteador_chat
from app.features.engenheiro_prompt.roteador import roteador_engenheiro_prompt

aplicacao = FastAPI(
    title=configuracoes.nome_aplicacao,
    version=configuracoes.versao,
)

aplicacao.add_middleware(
    CORSMiddleware,
    allow_origins=configuracoes.origens_permitidas,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

aplicacao.include_router(roteador_chat, prefix="/api/v1/chat", tags=["chat"])
aplicacao.include_router(roteador_engenheiro_prompt, prefix="/api/v1/engenheiro-prompt", tags=["engenheiro-prompt"])
