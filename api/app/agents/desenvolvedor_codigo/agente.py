from datetime import datetime
from typing import Annotated, Literal, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from app.core.configuracoes import configuracoes
from app.agents.desenvolvedor_codigo.github import ServicoGitHub

PROMPT_DESENVOLVEDOR = """Você é um desenvolvedor full-stack sênior especializado em Angular 19 e FastAPI.

Você recebe um prompt de engenharia detalhado e deve gerar TODOS os arquivos de código necessários para implementar a feature descrita, seguindo rigorosamente as convenções do projeto.

## Stack do Projeto

### Backend (FastAPI — pasta `api/`)
- Python + FastAPI com `async def` em todas as rotas
- Estrutura por feature em `api/app/features/{nome_feature}/`:
  - `__init__.py` (arquivo vazio)
  - `roteador.py` — APIRouter com endpoints assíncronos
  - `esquemas.py` — Schemas Pydantic separados para entrada e saída
  - `servico.py` — Lógica de negócio com injeção via `Depends()`
- Proibido retornar `dict` nas rotas — sempre schemas Pydantic
- Proibido `try/except` e `print()`
- Proibido `Any` do módulo `typing` — tipagem estrita obrigatória

### Frontend (Angular 19 — pasta `web/`)
- Angular 19 com standalone components e Signals
- Angular Material para UI
- Features em `web/src/app/features/{nome-feature}/`
- Services em `web/src/app/core/services/`
- Models em `web/src/app/core/models/`
- Proibido `console.log`, `any` e `var`

## Convenções obrigatórias
- Português em variáveis, métodos, propriedades, interfaces, types, enums e nomes de arquivos
- Inglês apenas em nomes de pastas
- Sem comentários no código
- Foco em clareza e manutenibilidade

## Sua tarefa
1. Leia o prompt de engenharia com atenção
2. Identifique se é necessário código backend, frontend ou ambos
3. Gere TODOS os arquivos com conteúdo COMPLETO e funcional
4. Chame `submeter_codigo_para_pull_request` com todos os arquivos, título e descrição do PR

O nome do branch deve seguir o padrão `feat/{nome-da-feature-em-kebab-case}`.
O título e a descrição do PR devem ser escritos em português."""


class DadosArquivo(BaseModel):
    caminho: str = Field(
        description="Caminho relativo do arquivo no repositório (ex: api/app/features/auth/roteador.py)"
    )
    conteudo: str = Field(description="Conteúdo completo e funcional do arquivo")
    descricao: str = Field(description="Descrição em uma linha do que este arquivo implementa")


class CodigoParaPR(BaseModel):
    arquivos: list[DadosArquivo] = Field(description="Lista de todos os arquivos a serem criados no PR")
    titulo_pr: str = Field(description="Título claro do Pull Request em português")
    descricao_pr: str = Field(description="Descrição markdown do PR listando todas as mudanças")
    nome_branch_base: str = Field(description="Nome base do branch no padrão feat/{nome-feature-kebab-case}")


@tool(args_schema=CodigoParaPR)
def submeter_codigo_para_pull_request(
    arquivos: list[DadosArquivo],
    titulo_pr: str,
    descricao_pr: str,
    nome_branch_base: str,
) -> str:
    """Chame quando todos os arquivos de código estiverem prontos para criar o Pull Request."""
    return "CODIGO_PRONTO_PARA_PR"


class EstadoAgente(TypedDict):
    mensagens: Annotated[list[BaseMessage], add_messages]
    prompt_engenharia: str
    arquivos_gerados: Optional[list[dict]]
    titulo_pr: Optional[str]
    descricao_pr: Optional[str]
    nome_branch: Optional[str]
    url_pull_request: Optional[str]


def _criar_llm_desenvolvedor() -> ChatGroq:
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=configuracoes.groq_api_key,
        temperature=0.1,
    ).bind_tools([submeter_codigo_para_pull_request])  # type: ignore[return-value]


async def no_gerador_codigo(estado: EstadoAgente) -> dict:
    llm = _criar_llm_desenvolvedor()
    mensagens = [
        SystemMessage(content=PROMPT_DESENVOLVEDOR),
        HumanMessage(
            content=f"Prompt de engenharia:\n\n{estado['prompt_engenharia']}\n\nGere o código completo e chame `submeter_codigo_para_pull_request`."
        ),
    ]
    resposta = await llm.ainvoke(mensagens)
    return {"mensagens": [resposta]}


def roteador_desenvolvedor(estado: EstadoAgente) -> Literal["no_criar_pr", "__end__"]:
    ultima_mensagem = estado["mensagens"][-1]
    if isinstance(ultima_mensagem, AIMessage) and ultima_mensagem.tool_calls:
        return "no_criar_pr"
    return END


async def no_criar_pr(estado: EstadoAgente) -> dict:
    ultima_mensagem = estado["mensagens"][-1]
    tool_call = ultima_mensagem.tool_calls[0]  # type: ignore[union-attr]
    dados: dict = tool_call["args"]

    tool_message = ToolMessage(
        content="Código recebido. Criando Pull Request no GitHub...",
        tool_call_id=tool_call["id"],
    )

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    nome_branch = f"{dados['nome_branch_base']}-{timestamp}"

    servico_github = ServicoGitHub()
    arquivos: list[dict] = dados["arquivos"]
    url_pr = servico_github.criar_pull_request(
        nome_branch=nome_branch,
        titulo=dados["titulo_pr"],
        descricao=dados["descricao_pr"],
        arquivos=arquivos,
    )

    mensagem_conclusao = AIMessage(
        content=f"Pull Request criado com sucesso! Acesse em: {url_pr}"
    )

    return {
        "mensagens": [tool_message, mensagem_conclusao],
        "arquivos_gerados": arquivos,
        "titulo_pr": dados["titulo_pr"],
        "descricao_pr": dados["descricao_pr"],
        "nome_branch": nome_branch,
        "url_pull_request": url_pr,
    }


def construir_grafo() -> StateGraph:
    grafo = StateGraph(EstadoAgente)

    grafo.add_node("no_gerador_codigo", no_gerador_codigo)
    grafo.add_node("no_criar_pr", no_criar_pr)

    grafo.add_edge(START, "no_gerador_codigo")
    grafo.add_conditional_edges("no_gerador_codigo", roteador_desenvolvedor)
    grafo.add_edge("no_criar_pr", END)

    return grafo.compile()


agente_desenvolvedor_codigo = construir_grafo()
