from typing import Annotated, Literal, Optional

from langchain_groq import ChatGroq
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from app.core.configuracoes import configuracoes

PROMPT_COLETOR = """Você é o Arquiteto de Prompts, especialista em engenharia de requisitos para sistemas de IA.

Sua missão é conduzir uma conversa objetiva para coletar as informações necessárias e, quando estiver pronto, gerar um prompt de engenharia de software de alta qualidade.

## Informações obrigatórias:
1. **Objetivo** — O que o sistema deve fazer? Qual problema resolve?
2. **Tipo de sistema** — API REST, aplicação web, CLI, biblioteca, microsserviço, etc.
3. **Tecnologias** — Linguagem(ns), frameworks, banco de dados, etc.
4. **Entradas e saídas** — Quais dados entram e o que o sistema produz/retorna?

## Informações opcionais (colete se relevantes ao contexto):
5. **Restrições** — Performance, segurança, escalabilidade, padrões de código obrigatórios
6. **Exemplos** — Casos de uso concretos, exemplos de input/output

## Regras de conduta:
- Faça UMA pergunta objetiva por vez — não sobrecarregue o usuário
- Seja direto, profissional e amigável
- Confirme informações ambíguas antes de prosseguir
- Aproveite informações espontâneas — se o usuário já forneceu algo, não pergunte novamente
- Adapte as perguntas ao que já foi coletado na conversa

## Critério para gerar o prompt:
Assim que tiver os 4 itens obrigatórios (objetivo, tipo de sistema, tecnologias e entradas/saídas), chame `solicitar_geracao_prompt` com todos os dados coletados. Restrições e exemplos são opcionais — inclua se foram mencionados."""

PROMPT_GERADOR = """Você é um especialista sênior em prompt engineering para geração de código com modelos de linguagem.

Com base nos dados fornecidos, crie um prompt técnico completo e preciso. Este prompt será usado por um modelo de IA para desenvolver o código especificado.

## Princípios obrigatórios:
- **Especificidade**: Cada requisito deve ser explícito — nunca implícito
- **Completude**: Inclua tudo que o modelo precisa saber para desenvolver o código sem dúvidas
- **Estrutura**: Use markdown com hierarquia clara e seções bem definidas
- **Imperativo**: Use linguagem direta e imperativa (ex: "Implemente...", "Garanta...", "Proíba...")

## Estrutura obrigatória do prompt a ser gerado:

### 1. Papel e Especialidade
Defina quem o modelo deve ser (ex: "Você é um desenvolvedor Python sênior especializado em APIs REST...")

### 2. Contexto do Projeto
Descrição completa do sistema, seu propósito e contexto de negócio

### 3. Tarefa
Descrição precisa e detalhada do que deve ser desenvolvido

### 4. Stack Tecnológica
Liste tecnologias com versões quando relevante

### 5. Requisitos Funcionais
- Comportamentos obrigatórios
- Regras de negócio
- Fluxos de dados e processamento

### 6. Padrões de Código
- Boas práticas obrigatórias (SOLID, Clean Code, etc.)
- Nomenclatura e estrutura de pastas
- Proibições explícitas

### 7. Interface de Dados
- Entradas com tipos e validações
- Saídas com formatos esperados
- Exemplos concretos de uso

### 8. Restrições Adicionais
Performance, segurança, escalabilidade (inclua apenas se foram especificadas)

### 9. Formato de Entrega
O que o modelo deve entregar (código completo, estrutura de arquivos, testes, etc.)

Escreva o prompt em português. O resultado deve ser um documento markdown completo e auto-suficiente."""


class DadosColetados(BaseModel):
    objetivo: str = Field(description="Objetivo principal do sistema/funcionalidade")
    tipo_sistema: str = Field(description="Tipo: API REST, web app, CLI, biblioteca, microsserviço, etc.")
    tecnologias: list[str] = Field(description="Lista de tecnologias, linguagens e frameworks")
    entradas_saidas: str = Field(description="Descrição das entradas e saídas esperadas do sistema")
    restricoes: str = Field(default="", description="Restrições e requisitos não-funcionais")
    exemplos: str = Field(default="", description="Exemplos de uso ou casos concretos de input/output")


@tool(args_schema=DadosColetados)
def solicitar_geracao_prompt(
    objetivo: str,
    tipo_sistema: str,
    tecnologias: list[str],
    entradas_saidas: str,
    restricoes: str = "",
    exemplos: str = "",
) -> str:
    """Chame quando tiver coletado informações suficientes para gerar o prompt de engenharia.
    Mínimo necessário: objetivo, tipo_sistema, tecnologias e entradas_saidas."""
    return "DADOS_COLETADOS"


class EstadoAgente(TypedDict):
    mensagens: Annotated[list[BaseMessage], add_messages]
    dados_coletados: Optional[dict]
    prompt_engenharia: Optional[str]
    markdown_final: Optional[str]


def _criar_llm_agente() -> ChatGroq:
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=configuracoes.groq_api_key,
        temperature=0.7,
    ).bind_tools([solicitar_geracao_prompt])  # type: ignore[return-value]


def _criar_llm_gerador() -> ChatGroq:
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=configuracoes.groq_api_key,
        temperature=0.3,
    )


async def no_agente(estado: EstadoAgente) -> dict:
    llm = _criar_llm_agente()
    mensagens = [SystemMessage(content=PROMPT_COLETOR)] + estado["mensagens"]
    resposta = await llm.ainvoke(mensagens)
    return {"mensagens": [resposta]}


def roteador_agente(estado: EstadoAgente) -> Literal["no_gerador_prompt", "__end__"]:
    ultima_mensagem = estado["mensagens"][-1]
    if isinstance(ultima_mensagem, AIMessage) and ultima_mensagem.tool_calls:
        return "no_gerador_prompt"
    return END


async def no_gerador_prompt(estado: EstadoAgente) -> dict:
    ultima_mensagem = estado["mensagens"][-1]
    tool_call = ultima_mensagem.tool_calls[0]  # type: ignore[union-attr]
    dados: dict = tool_call["args"]

    tool_message = ToolMessage(
        content="Dados recebidos. Gerando prompt de engenharia...",
        tool_call_id=tool_call["id"],
    )

    llm = _criar_llm_gerador()
    import json
    dados_formatados = json.dumps(dados, ensure_ascii=False, indent=2)
    mensagens_geracao = [
        SystemMessage(content=PROMPT_GERADOR),
        HumanMessage(content=f"Dados coletados:\n```json\n{dados_formatados}\n```\n\nGere o prompt de engenharia."),
    ]
    resposta_geracao = await llm.ainvoke(mensagens_geracao)
    prompt_gerado: str = resposta_geracao.content  # type: ignore[assignment]

    markdown = _formatar_markdown(dados, prompt_gerado)
    mensagem_conclusao = AIMessage(
        content="O prompt de engenharia foi gerado com sucesso! Você pode visualizar e baixar o documento acima."
    )

    return {
        "mensagens": [tool_message, mensagem_conclusao],
        "dados_coletados": dados,
        "prompt_engenharia": prompt_gerado,
        "markdown_final": markdown,
    }


def _formatar_markdown(dados: dict, prompt: str) -> str:
    tecnologias = ", ".join(dados.get("tecnologias", []))
    restricoes = dados.get("restricoes", "")
    exemplos = dados.get("exemplos", "")

    secao_restricoes = f"\n## Restrições\n\n{restricoes}\n" if restricoes else ""
    secao_exemplos = f"\n## Exemplos\n\n{exemplos}\n" if exemplos else ""

    return f"""# Prompt de Engenharia

## Visão Geral

| Campo | Informação |
|-------|------------|
| **Objetivo** | {dados.get("objetivo", "")} |
| **Tipo de Sistema** | {dados.get("tipo_sistema", "")} |
| **Tecnologias** | {tecnologias} |

## Entradas e Saídas

{dados.get("entradas_saidas", "")}
{secao_restricoes}{secao_exemplos}
---

## Prompt Gerado

{prompt}

---

*Gerado pelo Organizer IA — Arquiteto de Prompts*
"""


def construir_grafo() -> StateGraph:
    grafo = StateGraph(EstadoAgente)

    grafo.add_node("no_agente", no_agente)
    grafo.add_node("no_gerador_prompt", no_gerador_prompt)

    grafo.add_edge(START, "no_agente")
    grafo.add_conditional_edges("no_agente", roteador_agente)
    grafo.add_edge("no_gerador_prompt", END)

    return grafo.compile()


agente_arquiteto_prompts = construir_grafo()
