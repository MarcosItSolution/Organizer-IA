from pathlib import Path
from typing import Annotated, Literal, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_groq import ChatGroq
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

PROMPT_DESENVOLVEDOR = f"""Você é um desenvolvedor full-stack sênior especializado em Angular 19 e FastAPI.

Você recebe um prompt de engenharia detalhado e deve gerar TODOS os arquivos de código necessários para implementar a feature descrita, seguindo rigorosamente as convenções do projeto.

## Convenções do Projeto

{_CONTEXTO_PROJETO}

## Estrutura de Pastas do Projeto

### Backend (api/)
- Features: `api/app/features/{{nome_feature}}/`
  - `__init__.py`, `roteador.py`, `esquemas.py`, `servico.py`
- Agentes: `api/app/agents/{{nome_agente}}/`
  - `__init__.py`, `agente.py`, `esquemas.py`, `servico.py`, `roteador.py`

### Frontend (web/)
- Estilos globais e variáveis de tema: `web/src/styles.scss` ← use este arquivo para mudanças de tema, cores globais e variáveis CSS
- Features: `web/src/app/features/{{nome-feature}}/`
- Services: `web/src/app/core/services/`
- Models: `web/src/app/core/models/`

### Variáveis CSS globais (definidas em web/src/styles.scss)
Todos os componentes usam estas variáveis — ao alterar o tema, modifique-as aqui:
- `--cor-fundo`: cor de fundo da página
- `--cor-superficie`: cor de superfície dos cards/containers
- `--cor-superficie-elevada`: superfície com elevação (hover, dropdowns)
- `--cor-borda`: cor das bordas padrão
- `--cor-borda-hover`: cor das bordas ao hover
- `--cor-primaria`: cor primária (#6366f1)
- `--cor-primaria-clara`: variante clara da primária (#818cf8)
- `--cor-secundaria`: cor secundária (#06b6d4)
- `--gradiente-primario`: gradiente principal (linear-gradient(135deg, #6366f1, #8b5cf6))
- `--cor-texto`: cor do texto principal
- `--cor-texto-suave`: texto secundário/suave
- `--cor-texto-sutil`: texto sutil/desabilitado

## Sua tarefa
1. Leia o prompt de engenharia com atenção
2. Identifique quais arquivos precisam ser criados (backend, frontend ou ambos)
3. Gere TODOS os arquivos com conteúdo COMPLETO e funcional
4. Chame `escrever_arquivos_projeto` com todos os arquivos gerados

Os caminhos dos arquivos devem ser relativos à raiz do projeto."""


class DadosArquivo(BaseModel):
    caminho: str = Field(
        description="Caminho relativo do arquivo na raiz do projeto (ex: api/app/features/auth/roteador.py)"
    )
    conteudo: str = Field(description="Conteúdo completo e funcional do arquivo")
    descricao: str = Field(description="Descrição em uma linha do que este arquivo implementa")


class CodigoParaEscrita(BaseModel):
    arquivos: list[DadosArquivo] = Field(description="Lista de todos os arquivos a serem criados no projeto")
    titulo: str = Field(description="Título claro da implementação em português")
    descricao: str = Field(description="Descrição markdown resumindo o que foi implementado")


@tool(args_schema=CodigoParaEscrita)
def escrever_arquivos_projeto(
    arquivos: list[DadosArquivo],
    titulo: str,
    descricao: str,
) -> str:
    """Chame quando todos os arquivos de código estiverem prontos para escrever no projeto."""
    return "CODIGO_PRONTO_PARA_ESCRITA"


class EstadoAgente(TypedDict):
    mensagens: Annotated[list[BaseMessage], add_messages]
    prompt_engenharia: str
    arquivos_gerados: Optional[list[dict]]
    titulo: Optional[str]
    descricao: Optional[str]


def _criar_llm_desenvolvedor() -> ChatGroq:
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=configuracoes.groq_api_key,
        temperature=0.1,
    ).bind_tools([escrever_arquivos_projeto])  # type: ignore[return-value]


async def no_gerador_codigo(estado: EstadoAgente) -> dict:
    llm = _criar_llm_desenvolvedor()
    mensagens = [
        SystemMessage(content=PROMPT_DESENVOLVEDOR),
        HumanMessage(
            content=f"Prompt de engenharia:\n\n{estado['prompt_engenharia']}\n\nGere o código completo e chame `escrever_arquivos_projeto`."
        ),
    ]
    resposta = await llm.ainvoke(mensagens)
    return {"mensagens": [resposta]}


def roteador_desenvolvedor(estado: EstadoAgente) -> Literal["no_escrever_arquivos", "__end__"]:
    ultima_mensagem = estado["mensagens"][-1]
    if isinstance(ultima_mensagem, AIMessage) and ultima_mensagem.tool_calls:
        return "no_escrever_arquivos"
    return END


async def no_escrever_arquivos(estado: EstadoAgente) -> dict:
    ultima_mensagem = estado["mensagens"][-1]
    tool_call = ultima_mensagem.tool_calls[0]  # type: ignore[union-attr]
    dados: dict = tool_call["args"]

    tool_message = ToolMessage(
        content="Código recebido. Escrevendo arquivos no projeto...",
        tool_call_id=tool_call["id"],
    )

    arquivos: list[dict] = dados["arquivos"]
    for arquivo in arquivos:
        caminho_completo = _RAIZ_PROJETO / arquivo["caminho"]
        caminho_completo.parent.mkdir(parents=True, exist_ok=True)
        caminho_completo.write_text(arquivo["conteudo"], encoding="utf-8")

    mensagem_conclusao = AIMessage(
        content=f"Implementação concluída! {len(arquivos)} arquivo(s) escrito(s) no projeto."
    )

    return {
        "mensagens": [tool_message, mensagem_conclusao],
        "arquivos_gerados": arquivos,
        "titulo": dados["titulo"],
        "descricao": dados["descricao"],
    }


def construir_grafo() -> StateGraph:
    grafo = StateGraph(EstadoAgente)

    grafo.add_node("no_gerador_codigo", no_gerador_codigo)
    grafo.add_node("no_escrever_arquivos", no_escrever_arquivos)

    grafo.add_edge(START, "no_gerador_codigo")
    grafo.add_conditional_edges("no_gerador_codigo", roteador_desenvolvedor)
    grafo.add_edge("no_escrever_arquivos", END)

    return grafo.compile()


agente_desenvolvedor_codigo = construir_grafo()
