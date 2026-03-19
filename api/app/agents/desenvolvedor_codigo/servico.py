from langchain_core.messages import AIMessage

from app.agents.desenvolvedor_codigo.agente import EstadoAgente, agente_desenvolvedor_codigo
from app.agents.desenvolvedor_codigo.esquemas import (
    ArquivoGerado,
    EntradaDesenvolvedorCodigo,
    RespostaDesenvolvedorCodigo,
)


class ServicoDesenvolvedorCodigo:
    async def processar_prompt(self, entrada: EntradaDesenvolvedorCodigo) -> RespostaDesenvolvedorCodigo:
        estado_inicial: EstadoAgente = {
            "mensagens": [],
            "prompt_engenharia": entrada.prompt_engenharia,
            "arquivos_gerados": None,
            "titulo": None,
            "descricao": None,
        }

        resultado = await agente_desenvolvedor_codigo.ainvoke(estado_inicial)

        ultima_mensagem = next(
            (m for m in reversed(resultado["mensagens"]) if isinstance(m, AIMessage) and not m.tool_calls),
            None,
        )
        mensagem_texto: str = ultima_mensagem.content if ultima_mensagem else ""  # type: ignore[assignment]

        arquivos_gerados: list[dict] = resultado.get("arquivos_gerados") or []

        if not arquivos_gerados:
            return RespostaDesenvolvedorCodigo(
                fase="erro",
                mensagem=mensagem_texto or "O agente não conseguiu gerar o código. Verifique o prompt de engenharia.",
            )

        arquivos = [
            ArquivoGerado(
                caminho=arquivo["caminho"],
                conteudo=arquivo["conteudo"],
                descricao=arquivo["descricao"],
            )
            for arquivo in arquivos_gerados
        ]

        return RespostaDesenvolvedorCodigo(
            arquivos_gerados=arquivos,
            titulo=resultado.get("titulo") or "",
            descricao=resultado.get("descricao") or "",
            fase="finalizado",
            mensagem=mensagem_texto,
        )
