from pathlib import Path
from typing import Annotated, Literal, Optional

from langchain_groq import ChatGroq
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from app.core.configuracoes import configuracoes

_RAIZ_PROJETO = Path(__file__).parent.parent.parent.parent.parent


def _carregar_contexto_projeto() -> str:
    claude_md = _RAIZ_PROJETO / "CLAUDE.md"
    if claude_md.exists():
        return claude_md.read_text(encoding="utf-8")
    return ""


_CONTEXTO_PROJETO = _carregar_contexto_projeto()

PROMPT_COLETOR = f"""Você é o Arquiteto de Prompts do projeto Organizer IA. Seu papel é conduzir uma entrevista técnica para extrair todos os requisitos necessários antes de gerar um prompt de engenharia preciso.

## Contexto do Projeto

{_CONTEXTO_PROJETO}

## Sua missão
Extrair requisitos suficientemente detalhados para que um desenvolvedor implemente a tarefa SEM precisar fazer nenhuma pergunta adicional. Mensagens vagas, curtas ou ambíguas NUNCA são suficientes.

## Regras de conduta:
- Faça UMA pergunta objetiva por vez — não sobrecarregue o usuário
- Seja direto e profissional
- NÃO pergunte sobre tecnologias ou tipo de sistema — já definidos pelo projeto
- Aproveite informações já fornecidas — não repita perguntas respondidas
- Se a resposta for vaga, peça esclarecimento antes de avançar
- **NUNCA assuma valores, componentes ou comportamentos não mencionados pelo usuário**

## O que você DEVE extrair antes de gerar o prompt:

### 1. Objetivo claro
O que exatamente deve ser feito? Uma frase genérica como "mudar a cor" ou "adicionar uma feature" NÃO é suficiente. Você precisa saber: mudar a cor de quê? adicionar qual feature?

### 2. Escopo (onde)
Em qual componente, página, arquivo ou endpoint a mudança será feita? Se o usuário não especificar, pergunte.

### 3. Detalhes técnicos (como e quanto)
Os valores e comportamentos exatos. Exemplos do que perguntar dependendo do tipo de tarefa:
- **Mudança visual** (cor, tamanho, fonte, espaçamento): de qual valor para qual valor? aplicar globalmente ou em um elemento específico? precisa ser responsivo?
- **Nova feature** (tela, endpoint, componente): qual o fluxo completo? o que aciona? o que é exibido/retornado? há estados de erro/vazio?
- **Mudança de comportamento** (validação, lógica, animação): como funciona hoje? como deve funcionar? quais são os casos de borda?
- **Integração** (nova API, serviço): qual endpoint? quais campos? qual o formato de entrada e saída?

### 4. Resultado esperado (o que o usuário/sistema vê)
O que muda na interface ou na resposta da API após a implementação?

### 5. Restrições e contexto (se relevante)
Condições especiais, regras de negócio, casos que devem funcionar de forma diferente.

## Fluxo obrigatório antes de chamar `solicitar_geracao_prompt`:

### Passo 1 — Coletar os 4 campos obrigatórios
Continue fazendo perguntas até ter respostas concretas e específicas para os 4 itens acima. Se qualquer um estiver vago ou ausente, continue perguntando. Em caso de dúvida, pergunte — nunca invente ou assuma.

### Passo 2 — Perguntar sobre restrições e exemplos (OBRIGATÓRIO antes de gerar)
Quando os 4 campos estiverem completos, SEMPRE faça esta pergunta antes de chamar a tool:

> "Para sermos mais assertivos, gostaria de adicionar alguma restrição ou exemplo?"

Interprete a resposta do usuário:
- Se o usuário fornecer restrições ou exemplos → preencha os campos `restricoes` e/ou `exemplos` com o que foi informado
- Se o usuário disser não, "pode seguir", "não tenho" ou similar → prossiga e chame `solicitar_geracao_prompt` sem esses campos

### Passo 3 — Chamar a tool
Somente após os passos 1 e 2 concluídos, chame `solicitar_geracao_prompt`."""

PROMPT_GERADOR = f"""Você é um especialista sênior em prompt engineering para geração de código com modelos de linguagem.

## Contexto do Projeto

{_CONTEXTO_PROJETO}

Com base nos dados coletados e nas convenções do projeto acima, crie um prompt técnico completo e preciso. Este prompt será usado por um modelo de IA para implementar a funcionalidade no projeto.

## Princípios obrigatórios:
- **Especificidade**: Cada requisito deve ser explícito — nunca implícito
- **Completude**: Inclua tudo que o modelo precisa saber para desenvolver sem dúvidas
- **Estrutura**: Use markdown com hierarquia clara e seções bem definidas
- **Imperativo**: Use linguagem direta ("Implemente...", "Garanta...", "Proíba...")

## Estrutura obrigatória do prompt a ser gerado:

### 1. Papel e Especialidade
Defina que o modelo é um desenvolvedor sênior full-stack especializado em Angular 19 e FastAPI

### 2. Contexto do Projeto
Inclua as convenções obrigatórias do projeto (stack, nomenclatura, proibições)

### 3. Tarefa
Descrição precisa e detalhada do que deve ser implementado

### 4. Requisitos Funcionais
- Comportamentos obrigatórios
- Regras de negócio
- Fluxos de dados e processamento

### 5. Interface de Dados
- Entradas com tipos e validações
- Saídas com formatos esperados
- Exemplos concretos se disponíveis

### 6. Estrutura de Arquivos Esperada
Especifique os caminhos exatos dos arquivos a criar/modificar, com base na estrutura do projeto

### 7. Formato de Entrega
O modelo deve entregar código completo e funcional para cada arquivo

Escreva o prompt em português. O resultado deve ser um documento markdown completo e auto-suficiente."""


class DadosColetados(BaseModel):
    objetivo: str = Field(
        description="Objetivo específico e concreto — o que exatamente deve ser feito. Ex: 'Alterar a cor de fundo do componente ChatComponent de #07090f para #ffffff'"
    )
    escopo: str = Field(
        description="Onde a mudança será aplicada — nome do componente, página, arquivo, endpoint ou módulo específico"
    )
    detalhes_tecnicos: str = Field(
        description="Especificações técnicas exatas: valores concretos (cores em hex, tamanhos em px/rem, nomes de variáveis CSS, campos de API, etc.), comportamentos detalhados e condições específicas"
    )
    resultado_esperado: str = Field(
        description="O que o usuário ou o sistema vê/recebe após a implementação — o 'antes e depois' ou o comportamento final esperado"
    )
    restricoes: str = Field(
        default="",
        description="Restrições, regras de negócio, casos de borda, condições especiais ou elementos que NÃO devem ser alterados"
    )
    exemplos: str = Field(
        default="",
        description="Exemplos concretos, casos de uso, screenshots descritos ou referências visuais mencionadas pelo usuário"
    )


@tool(args_schema=DadosColetados)
def solicitar_geracao_prompt(
    objetivo: str,
    escopo: str,
    detalhes_tecnicos: str,
    resultado_esperado: str,
    restricoes: str = "",
    exemplos: str = "",
) -> str:
    """Chame SOMENTE quando tiver respostas concretas e específicas para: objetivo exato, escopo (onde), detalhes técnicos (valores/comportamentos precisos) e resultado esperado. Nunca chame com dados vagos ou assumidos."""
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
    import json

    ultima_mensagem = estado["mensagens"][-1]
    tool_call = ultima_mensagem.tool_calls[0]  # type: ignore[union-attr]
    dados: dict = tool_call["args"]

    tool_message = ToolMessage(
        content="Dados recebidos. Gerando prompt de engenharia...",
        tool_call_id=tool_call["id"],
    )

    llm = _criar_llm_gerador()
    dados_formatados = json.dumps(dados, ensure_ascii=False, indent=2)
    mensagens_geracao = [
        SystemMessage(content=PROMPT_GERADOR),
        HumanMessage(content=f"Requisitos coletados:\n```json\n{dados_formatados}\n```\n\nGere o prompt de engenharia completo e detalhado."),
    ]
    resposta_geracao = await llm.ainvoke(mensagens_geracao)
    prompt_gerado: str = resposta_geracao.content  # type: ignore[assignment]

    markdown = _formatar_markdown(dados, prompt_gerado)
    mensagem_conclusao = AIMessage(
        content="O prompt de engenharia foi gerado. Iniciando implementação no projeto..."
    )

    return {
        "mensagens": [tool_message, mensagem_conclusao],
        "dados_coletados": dados,
        "prompt_engenharia": prompt_gerado,
        "markdown_final": markdown,
    }


def _formatar_markdown(dados: dict, prompt: str) -> str:
    restricoes = dados.get("restricoes", "")
    exemplos = dados.get("exemplos", "")

    secao_restricoes = f"\n## Restrições e Casos de Borda\n\n{restricoes}\n" if restricoes else ""
    secao_exemplos = f"\n## Exemplos e Referências\n\n{exemplos}\n" if exemplos else ""

    return f"""# Prompt de Engenharia

## Visão Geral

| Campo | Informação |
|-------|------------|
| **Objetivo** | {dados.get("objetivo", "")} |
| **Escopo** | {dados.get("escopo", "")} |

## Detalhes Técnicos

{dados.get("detalhes_tecnicos", "")}

## Resultado Esperado

{dados.get("resultado_esperado", "")}
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
