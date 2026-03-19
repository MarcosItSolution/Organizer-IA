from typing import Optional

from langchain_core.messages import AIMessage, HumanMessage

from app.agents.engenheiro_prompt.agente import EstadoAgente, agente_arquiteto_prompts
from app.agents.engenheiro_prompt.esquemas import EntradaAgente, RespostaAgente


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
        prompt_engenharia: Optional[str] = resultado.get("prompt_engenharia")

        if not markdown_final or not prompt_engenharia:
            return RespostaAgente(
                resposta=resposta_texto,
                fase="coletando",
            )

        arquivos_implementados = await self._executar_desenvolvedor(prompt_engenharia)

        return RespostaAgente(
            resposta=f"Implementação concluída! {len(arquivos_implementados)} arquivo(s) criado(s) no projeto.",
            fase="implementado",
            markdown_final=markdown_final,
            prompt_engenharia=prompt_engenharia,
            arquivos_implementados=arquivos_implementados,
        )

    async def _executar_desenvolvedor(self, prompt_engenharia: str) -> list[str]:
        from app.agents.desenvolvedor_codigo.esquemas import EntradaDesenvolvedorCodigo
        from app.agents.desenvolvedor_codigo.servico import ServicoDesenvolvedorCodigo

        servico_dev = ServicoDesenvolvedorCodigo()
        resposta = await servico_dev.processar_prompt(
            EntradaDesenvolvedorCodigo(prompt_engenharia=prompt_engenharia)
        )
        return [arquivo.caminho for arquivo in resposta.arquivos_gerados]
