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
            "titulo_pr": None,
            "descricao_pr": None,
            "nome_branch": None,
            "url_pull_request": None,
        }

        resultado = await agente_desenvolvedor_codigo.ainvoke(estado_inicial)

        ultima_mensagem = next(
            (m for m in reversed(resultado["mensagens"]) if isinstance(m, AIMessage) and not m.tool_calls),
            None,
        )
        mensagem_texto: str = ultima_mensagem.content if ultima_mensagem else ""  # type: ignore[assignment]

        if resultado.get("url_pull_request"):
            arquivos = [
                ArquivoGerado(
                    caminho=arquivo["caminho"],
                    conteudo=arquivo["conteudo"],
                    descricao=arquivo["descricao"],
                )
                for arquivo in (resultado.get("arquivos_gerados") or [])
            ]
            return RespostaDesenvolvedorCodigo(
                url_pull_request=resultado["url_pull_request"],
                arquivos_gerados=arquivos,
                titulo_pr=resultado.get("titulo_pr") or "",
                fase="finalizado",
                mensagem=mensagem_texto,
            )

        return RespostaDesenvolvedorCodigo(
            fase="erro",
            mensagem=mensagem_texto or "O agente não conseguiu gerar o código. Verifique o prompt de engenharia.",
        )
