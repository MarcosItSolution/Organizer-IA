from typing import Optional

from langchain_core.messages import AIMessage, HumanMessage

from app.features.engenheiro_prompt.agente import EstadoAgente, agente_arquiteto_prompts
from app.features.engenheiro_prompt.esquemas import EntradaAgente, RespostaAgente


class ServicoAgenteArquitetoPrompts:
    async def processar_mensagem(self, entrada: EntradaAgente) -> RespostaAgente:
        mensagens_historico = [
            HumanMessage(content=m.conteudo) if m.papel == "usuario" else AIMessage(content=m.conteudo)
            for m in entrada.historico
        ]
        mensagens_historico.append(HumanMessage(content=entrada.mensagem))

        estado_inicial: EstadoAgente = {
            "mensagens": mensagens_historico,
            "dados_coletados": None,
            "prompt_engenharia": None,
            "markdown_final": None,
        }

        resultado = await agente_arquiteto_prompts.ainvoke(estado_inicial)

        ultima_resposta = next(
            (
                m for m in reversed(resultado["mensagens"])
                if isinstance(m, AIMessage) and not (m.tool_calls)
            ),
            None,
        )

        resposta_texto = ultima_resposta.content if ultima_resposta else ""
        markdown_final: Optional[str] = resultado.get("markdown_final")
        fase = "finalizado" if markdown_final else "coletando"

        return RespostaAgente(
            resposta=resposta_texto,
            fase=fase,
            markdown_final=markdown_final,
            prompt_engenharia=resultado.get("prompt_engenharia"),
        )
