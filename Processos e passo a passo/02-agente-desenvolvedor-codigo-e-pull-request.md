# 02 — Agente Desenvolvedor de Código — Execução Local

> Implementação de um agente LangGraph que recebe um prompt de engenharia, gera código completo seguindo as convenções do projeto e escreve os arquivos diretamente em disco na máquina local. A chamada acontece automaticamente a partir do Agente Arquiteto de Prompts, sem intervenção do usuário.

---

## Índice

1. [Contexto no pipeline multi-agente](#1-contexto-no-pipeline-multi-agente)
2. [Geração de código com LLMs — conceitos fundamentais](#2-geração-de-código-com-llms--conceitos-fundamentais)
3. [Stack utilizada — sem novidades de dependências](#3-stack-utilizada--sem-novidades-de-dependências)
4. [Arquitetura do agente com LangGraph](#4-arquitetura-do-agente-com-langgraph)
5. [Tool Calling com schemas aninhados](#5-tool-calling-com-schemas-aninhados)
6. [Prompt Engineering — o PROMPT_DESENVOLVEDOR](#6-prompt-engineering--o-prompt_desenvolvedor)
7. [Escrita de arquivos em disco com pathlib](#7-escrita-de-arquivos-em-disco-com-pathlib)
8. [Estrutura de arquivos](#8-estrutura-de-arquivos)
9. [Fluxo completo de uma requisição](#9-fluxo-completo-de-uma-requisição)
10. [Decisões de design e boas práticas](#10-decisões-de-design-e-boas-práticas)
11. [O que vem a seguir](#11-o-que-vem-a-seguir)

---

## 1. Contexto no pipeline multi-agente

O **Organizer IA** é construído como um pipeline de agentes especializados, onde cada agente tem uma responsabilidade única e clara — princípio **Single Responsibility** aplicado em nível arquitetural. O Agente Desenvolvedor de Código é o segundo elo dessa cadeia:

```
Usuário
  │
  ▼
┌──────────────────────────────────┐
│  Agente Arquiteto de Prompts     │  ← Passo 01 (já implementado)
│  Coleta requisitos via chat e    │
│  gera um prompt de engenharia    │
└──────────────────────────────────┘
                 │
                 │  encadeamento automático em servico.py
                 │  (sem intervenção do usuário)
                 ▼
┌──────────────────────────────────┐
│  Agente Desenvolvedor de Código  │  ← Passo 02 (este documento)
│  Lê o prompt, gera os arquivos   │
│  e os escreve diretamente em     │
│  disco na raiz do projeto        │
└──────────────────────────────────┘
                 │
                 │  arquivos criados em disco
                 ▼
┌──────────────────────────────────┐
│  Agente Revisor de Código        │  ← Passo 03 (futuro)
│  Revisa o código, sugere         │
│  melhorias e aprova ou rejeita   │
└──────────────────────────────────┘
```

### O handoff automático

O ponto de integração entre os dois agentes acontece no `servico.py` do Agente Arquiteto. Assim que o grafo do arquiteto conclui a geração do prompt, o serviço chama automaticamente o `ServicoDesenvolvedorCodigo`:

```python
# engenheiro_prompt/servico.py
async def _executar_desenvolvedor(self, prompt_engenharia: str) -> list[str]:
    from app.agents.desenvolvedor_codigo.servico import ServicoDesenvolvedorCodigo
    servico_dev = ServicoDesenvolvedorCodigo()
    resposta = await servico_dev.processar_prompt(
        EntradaDesenvolvedorCodigo(prompt_engenharia=prompt_engenharia)
    )
    return [arquivo.caminho for arquivo in resposta.arquivos_gerados]
```

O usuário faz **um único request** ao endpoint do Arquiteto — e recebe de volta, já concluída, tanto o prompt gerado quanto a lista de arquivos implementados em disco.

Essa separação de responsabilidades é intencional. Um único "super-agente" que fizesse tudo ao mesmo tempo seria mais difícil de testar, debugar e evoluir. Ao separar em agentes especializados, cada um pode ser aprimorado, substituído ou ter seu LLM trocado independentemente.

---

## 2. Geração de código com LLMs — conceitos fundamentais

### 2.1 Por que LLMs são bons para gerar código?

LLMs como Llama 3.3 70B foram treinados em enormes volumes de código-fonte aberto (GitHub, StackOverflow, documentações técnicas). Isso significa que o modelo internalizou:

- **Padrões de projeto** (Factory, Repository, Dependency Injection)
- **Convenções de cada framework** (como estruturar um FastAPI router, como criar um Angular standalone component)
- **Sintaxe de linguagens** (Python, TypeScript, SQL)
- **Boas práticas** (SOLID, Clean Code, princípios de API design)

O desafio não é fazer o modelo "saber" programar — ele já sabe. O desafio é fazer o modelo gerar código **aderente às convenções específicas do seu projeto**. É aqui que o prompt de engenharia do Agente Arquiteto (Passo 01) se torna fundamental: ele não é apenas uma descrição genérica, mas um conjunto de instruções precisas que guiam o gerador.

### 2.2 A importância do contexto estruturado

Compare dois cenários:

**Sem o Agente Arquiteto (prompt genérico):**
```
"Crie uma API de cadastro de usuários com FastAPI"
```
O LLM vai gerar algo funcional, mas provavelmente usando `try/except` nas rotas, retornando `dict`, sem `async def`, sem a estrutura de pastas do projeto — tudo que viola nossas convenções.

**Com o prompt de engenharia gerado pelo Agente Arquiteto (prompt estruturado):**
```markdown
# Papel e Especialidade
Você é um desenvolvedor Python sênior especializado em FastAPI...

# Convenções do Projeto (extraídas do CLAUDE.md)
- Sempre async def nas rotas
- Proibido retornar dict — sempre schemas Pydantic
- Proibido try/except
- Estrutura: api/app/features/{nome}/roteador.py, esquemas.py, servico.py
...

# Estrutura de Arquivos Esperada
- api/app/features/usuarios/__init__.py
- api/app/features/usuarios/esquemas.py
- api/app/features/usuarios/servico.py
- api/app/features/usuarios/roteador.py
```

O segundo cenário instrui o LLM de forma explícita e imperativa. A qualidade do código gerado é substancialmente superior porque o modelo recebe **restrições concretas** e **caminhos de arquivo exatos**, não apenas uma intenção vaga.

### 2.3 Temperature e geração de código

Ao contrário de tarefas conversacionais, geração de código exige **determinismo e precisão**. Uma temperatura alta (0.7+) introduz "criatividade" que pode resultar em:

- Nomes de variáveis inconsistentes entre arquivos do mesmo PR
- Lógica correta mas estruturada de formas diferentes a cada geração
- Comentários inesperados ou estruturas de código não convencionais

Por isso, o Agente Desenvolvedor usa `temperature=0.1` — o mais próximo de determinístico possível sem ser `0.0` (que pode tornar o modelo repetitivo em prompts longos). Com temperatura baixa, o modelo sempre escolhe os tokens mais prováveis, produzindo código mais previsível, consistente e fiel às convenções descritas no prompt.

---

## 3. Stack utilizada — sem novidades de dependências

A base da stack é idêntica ao Agente Arquiteto (FastAPI, LangGraph, LangChain, Groq). Não há novas dependências neste agente.

A escrita de arquivos em disco é feita com `pathlib.Path` — módulo da biblioteca padrão do Python, sem instalação adicional. Isso é uma vantagem significativa em relação à versão anterior que usava PyGithub (dependência externa, síncrona, acoplada ao GitHub).

| Camada | Tecnologia | Papel |
|--------|-----------|-------|
| **LLM** | Llama 3.3 70B via Groq | Geração de código |
| **Agent Framework** | LangGraph | Orquestração do grafo de estado |
| **LLM Abstraction** | LangChain + langchain-groq | Abstração sobre a API do Groq |
| **API** | FastAPI | Endpoint HTTP do agente |
| **File I/O** | pathlib (stdlib) | Escrita dos arquivos gerados em disco |

---

## 4. Arquitetura do agente com LangGraph

### 4.1 O grafo

```
START
  │
  ▼
┌────────────────────┐
│  no_gerador_codigo │  ← LLM analisa o prompt e gera todos os arquivos via tool call
└────────────────────┘
         │
         ▼
  [roteador_desenvolvedor]  ← Conditional Edge: o LLM chamou escrever_arquivos_projeto?
         │
    ┌────┴────┐
    │         │
    ▼         ▼
  (Sim)      (Não)
    │           │
    ▼           ▼
┌───────────────────────┐   END  ← Retorna erro (LLM não chamou a tool)
│ no_escrever_arquivos  │
└───────────────────────┘
    │
    ▼
   END  ← Arquivos escritos em disco, retorna lista de caminhos
```

A diferença fundamental em relação ao Agente Arquiteto de Prompts é que **este grafo não é multi-turn**. Enquanto o arquiteto mantinha uma conversa com o usuário ao longo de vários turnos, o desenvolvedor opera em **single-shot**: recebe o prompt de engenharia completo, faz uma única chamada de LLM para gerar todo o código, e depois executa a escrita em disco.

Isso reflete a natureza diferente das duas tarefas:
- **Coleta de requisitos**: iterativa por natureza — você precisa de turnos de conversa para refinar as informações
- **Geração de código**: pode ser executada de forma completa em uma única operação, dado que o input (o prompt de engenharia) já contém todas as informações necessárias

### 4.2 O Estado (TypedDict)

```python
class EstadoAgente(TypedDict):
    mensagens: Annotated[list[BaseMessage], add_messages]
    prompt_engenharia: str
    arquivos_gerados: Optional[list[dict]]
    titulo: Optional[str]
    descricao: Optional[str]
```

Diferente do estado do Agente Arquiteto, aqui não há campos relacionados a sessão de chat nem dados de Pull Request. Os campos mapeiam diretamente o ciclo de vida desta tarefa:

| Campo | Tipo | Preenchido em | Finalidade |
|-------|------|---------------|------------|
| `mensagens` | `list[BaseMessage]` | `no_gerador_codigo` | Histórico do grafo (com reducer `add_messages`) |
| `prompt_engenharia` | `str` | Estado inicial | Input fixo — vem do Agente Arquiteto |
| `arquivos_gerados` | `Optional[list[dict]]` | `no_escrever_arquivos` | Lista de arquivos extraídos do tool call |
| `titulo` | `Optional[str]` | `no_escrever_arquivos` | Título da implementação |
| `descricao` | `Optional[str]` | `no_escrever_arquivos` | Descrição markdown do que foi implementado |

### 4.3 Os nós (Nodes)

**`no_gerador_codigo`**

```python
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
```

Este nó constrói o contexto do zero — não há histórico de conversas anteriores. O LLM recebe exatamente dois elementos:
1. O system prompt com as convenções do projeto (carregadas do `CLAUDE.md`)
2. O prompt de engenharia completo + instrução explícita para chamar a tool

A instrução explícita ao final ("chame `escrever_arquivos_projeto`") é uma técnica de **instruction following** que aumenta a confiabilidade do tool call. Sem essa instrução, o modelo pode gerar o código em texto puro ao invés de estruturá-lo no schema da tool.

**`no_escrever_arquivos`**

```python
async def no_escrever_arquivos(estado: EstadoAgente) -> dict:
    ultima_mensagem = estado["mensagens"][-1]
    tool_call = ultima_mensagem.tool_calls[0]
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
```

Este nó não faz chamada de LLM — ele é um **nó de ação** puro. Extrai os dados estruturados do tool call e escreve cada arquivo em disco. É totalmente assíncrono e não depende de serviços externos.

### 4.4 O roteador (Conditional Edge)

```python
def roteador_desenvolvedor(estado: EstadoAgente) -> Literal["no_escrever_arquivos", "__end__"]:
    ultima_mensagem = estado["mensagens"][-1]
    if isinstance(ultima_mensagem, AIMessage) and ultima_mensagem.tool_calls:
        return "no_escrever_arquivos"
    return END
```

A lógica é idêntica ao roteador do Agente Arquiteto. O padrão é consistente entre os dois agentes:
- `tool_calls` presente → o LLM está pronto para agir → avança para `no_escrever_arquivos`
- `tool_calls` ausente → o LLM respondeu em texto puro (erro ou falha de instruction following) → encerra o grafo

---

## 5. Tool Calling com schemas aninhados

### 5.1 O desafio: uma tool que recebe uma lista de objetos

O agente precisa que o LLM entregue **uma lista de arquivos**, onde cada arquivo tem três campos (caminho, conteúdo, descrição). Isso exige um schema **aninhado** — um `BaseModel` dentro de outro:

```python
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
```

Note que `nome_branch_base` foi removido em relação a uma versão anterior que criava Pull Requests. Agora os arquivos são escritos diretamente em disco — não há branch, commit ou PR.

### 5.2 O JSON Schema gerado automaticamente pelo Pydantic

Quando `bind_tools([escrever_arquivos_projeto])` é chamado, o LangChain serializa `CodigoParaEscrita` para JSON Schema e inclui na requisição ao Groq:

```json
{
  "name": "escrever_arquivos_projeto",
  "description": "Chame quando todos os arquivos de código estiverem prontos para escrever no projeto.",
  "parameters": {
    "type": "object",
    "properties": {
      "arquivos": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "caminho": { "type": "string", "description": "Caminho relativo do arquivo na raiz do projeto..." },
            "conteudo": { "type": "string", "description": "Conteúdo completo e funcional do arquivo" },
            "descricao": { "type": "string", "description": "Descrição em uma linha..." }
          },
          "required": ["caminho", "conteudo", "descricao"]
        }
      },
      "titulo": { "type": "string" },
      "descricao": { "type": "string" }
    },
    "required": ["arquivos", "titulo", "descricao"]
  }
}
```

O LLM recebe esse schema e sabe exatamente como estruturar o tool call — incluindo cada arquivo com seus três campos.

### 5.3 Como os dados chegam no nó `no_escrever_arquivos`

Quando o LLM decide chamar a tool, o retorno de `llm.ainvoke()` é um `AIMessage` com:

```python
AIMessage(
    content="",
    tool_calls=[{
        "id": "call_xyz123",
        "name": "escrever_arquivos_projeto",
        "args": {
            "arquivos": [
                {
                    "caminho": "api/app/features/auth/roteador.py",
                    "conteudo": "from fastapi import APIRouter...\n\n# código completo",
                    "descricao": "Router FastAPI com endpoint de autenticação"
                },
                {
                    "caminho": "api/app/features/auth/esquemas.py",
                    "conteudo": "from pydantic import BaseModel...",
                    "descricao": "Schemas Pydantic de entrada e saída"
                }
            ],
            "titulo": "feat: implementa autenticação de usuários",
            "descricao": "## Mudanças\n- Adiciona endpoint POST /api/v1/auth/login\n..."
        }
    }]
)
```

No `no_escrever_arquivos`, acessamos `tool_call["args"]` para extrair esses dados e iterar sobre a lista `"arquivos"`, escrevendo cada um em disco.

### 5.4 A importância das `description` nos Fields

Cada `Field(description=...)` é crucial. O LLM lê essas descrições para entender o que preencher em cada campo. Por exemplo:

```python
caminho: str = Field(
    description="Caminho relativo do arquivo na raiz do projeto (ex: api/app/features/auth/roteador.py)"
)
```

O exemplo concreto no `description` mostra o formato esperado. Sem isso, o LLM poderia usar caminhos absolutos ou estruturas incorretas incompatíveis com o projeto.

---

## 6. Prompt Engineering — o PROMPT_DESENVOLVEDOR

```python
_RAIZ_PROJETO = Path(__file__).parent.parent.parent.parent.parent

_CONTEXTO_PROJETO = _carregar_contexto_projeto()  # lê CLAUDE.md

PROMPT_DESENVOLVEDOR = f"""Você é um desenvolvedor full-stack sênior especializado em Angular 19 e FastAPI.

Você recebe um prompt de engenharia detalhado e deve gerar TODOS os arquivos de código necessários
para implementar a feature descrita, seguindo rigorosamente as convenções do projeto.

## Convenções do Projeto

{_CONTEXTO_PROJETO}

## Estrutura de Pastas do Projeto

### Backend (api/)
- Features: `api/app/features/{{nome_feature}}/`
  - `__init__.py`, `roteador.py`, `esquemas.py`, `servico.py`
- Agentes: `api/app/agents/{{nome_agente}}/`

### Frontend (web/)
- Features: `web/src/app/features/{{nome-feature}}/`
- Services: `web/src/app/core/services/`
- Models: `web/src/app/core/models/`

## Sua tarefa
1. Leia o prompt de engenharia com atenção
2. Identifique quais arquivos precisam ser criados (backend, frontend ou ambos)
3. Gere TODOS os arquivos com conteúdo COMPLETO e funcional
4. Chame `escrever_arquivos_projeto` com todos os arquivos gerados

Os caminhos dos arquivos devem ser relativos à raiz do projeto."""
```

### Análise das seções do prompt

**1. Injeção do CLAUDE.md**

```python
_CONTEXTO_PROJETO = _carregar_contexto_projeto()  # lê CLAUDE.md em tempo de módulo
```

A diferença fundamental em relação a qualquer versão anterior: as convenções do projeto não estão hardcoded no `PROMPT_DESENVOLVEDOR`. Estão no `CLAUDE.md`, que é lido na inicialização do módulo e interpolado via f-string. Isso significa que:

- Atualizar uma convenção no `CLAUDE.md` automaticamente afeta ambos os agentes (arquiteto e desenvolvedor) no próximo restart
- Não há duplicação de informação entre o `CLAUDE.md` e o código dos agentes

**2. Estrutura de pastas explícita**

```
- Features: `api/app/features/{nome_feature}/`
  - `__init__.py`, `roteador.py`, `esquemas.py`, `servico.py`
```

Informar a estrutura de pastas é crítico porque o LLM precisa gerar os valores corretos para `DadosArquivo.caminho`. Sem isso, cada geração poderia usar estruturas diferentes e incompatíveis com o projeto.

**3. Instrução de encerramento explícita**

```
Chame `escrever_arquivos_projeto` com todos os arquivos gerados
```

Esta instrução garante que o LLM entende que a conclusão é chamar a tool — não gerar texto puro. É uma forma de **instruction anchoring**: reforçar o comportamento desejado ao final do prompt.

**4. Caminhos relativos à raiz do projeto**

```
Os caminhos dos arquivos devem ser relativos à raiz do projeto.
```

Instrução essencial para que `_RAIZ_PROJETO / arquivo["caminho"]` resulte no caminho absoluto correto ao escrever em disco.

---

## 7. Escrita de arquivos em disco com pathlib

### 7.1 Calculando a raiz do projeto

```python
from pathlib import Path

_RAIZ_PROJETO = Path(__file__).parent.parent.parent.parent.parent
```

A conta de `.parent` a partir de `agente.py`:

| `.parent` | Resultado |
|-----------|-----------|
| `Path(__file__)` | `api/app/agents/desenvolvedor_codigo/agente.py` |
| `.parent` (1) | `api/app/agents/desenvolvedor_codigo/` |
| `.parent` (2) | `api/app/agents/` |
| `.parent` (3) | `api/app/` |
| `.parent` (4) | `api/` |
| `.parent` (5) | `Organizer IA/` ← raiz do projeto |

### 7.2 Escrevendo os arquivos

```python
for arquivo in arquivos:
    caminho_completo = _RAIZ_PROJETO / arquivo["caminho"]
    caminho_completo.parent.mkdir(parents=True, exist_ok=True)
    caminho_completo.write_text(arquivo["conteudo"], encoding="utf-8")
```

Três operações por arquivo:

1. **`_RAIZ_PROJETO / arquivo["caminho"]`** — junta o caminho absoluto da raiz com o caminho relativo gerado pelo LLM. O operador `/` do `pathlib.Path` é sobrescrito para concatenar partes de caminho de forma segura e cross-platform.

2. **`caminho_completo.parent.mkdir(parents=True, exist_ok=True)`** — cria todos os diretórios intermediários necessários. `parents=True` é equivalente a `mkdir -p`. `exist_ok=True` não lança exceção se o diretório já existir — comportamento idempotente.

3. **`caminho_completo.write_text(arquivo["conteudo"], encoding="utf-8")`** — escreve o conteúdo do arquivo. Se o arquivo já existir, ele é sobrescrito. Se não existir, é criado.

### 7.3 Por que escrever em disco em vez de criar um PR?

A escrita em disco elimina toda a complexidade de:
- Autenticação com a GitHub API (token, permissões)
- Criação de branches (unicidade por timestamp)
- Vários commits HTTP síncronos (um por arquivo)
- Dependência de serviço externo (GitHub)
- Biblioteca extra (PyGithub, que é síncrona — problema com async)

Para um projeto de estudo rodando localmente, escrever em disco é:
- **Mais simples**: `pathlib` é stdlib, sem dependências extras
- **Mais rápido**: I/O local é ordens de magnitude mais rápido que HTTP
- **Mais direto**: o desenvolvedor vê imediatamente os arquivos no projeto, pode rodar, testar e commitar quando quiser
- **Completamente assíncrono**: `write_text` dentro de `async def` não bloqueia o event loop para operações rápidas como I/O de disco em arquivos pequenos

---

## 8. Estrutura de arquivos

```
api/app/
├── core/
│   └── configuracoes.py           # Sem mudanças — github_token etc. permanecem mas não são usados aqui
│
├── agents/
│   ├── __init__.py
│   │
│   ├── engenheiro_prompt/         # Agente Arquiteto (ver documento 01)
│   │   ├── __init__.py
│   │   ├── agente.py              # Agora lê CLAUDE.md e injeta contexto nos prompts
│   │   ├── esquemas.py            # RespostaAgente com fase "implementado" e arquivos_implementados
│   │   ├── servico.py             # Encadeia desenvolvedor_codigo automaticamente
│   │   └── roteador.py
│   │
│   └── desenvolvedor_codigo/
│       ├── __init__.py
│       ├── agente.py              # Grafo LangGraph — lê CLAUDE.md, escreve arquivos em disco
│       ├── esquemas.py            # EntradaDesenvolvedorCodigo, RespostaDesenvolvedorCodigo
│       ├── github.py              # Mantido mas não usado — pode ser removido futuramente
│       ├── servico.py             # ServicoDesenvolvedorCodigo — orquestra agente e retorno HTTP
│       └── roteador.py            # APIRouter — POST /api/v1/desenvolvedor-codigo/ (ainda acessível)
│
└── features/
    └── chat/
        └── ...
```

### `esquemas.py` — contratos da API

```python
class ArquivoGerado(BaseModel):
    caminho: str
    conteudo: str
    descricao: str

class EntradaDesenvolvedorCodigo(BaseModel):
    prompt_engenharia: str           # O output do Agente Arquiteto

class RespostaDesenvolvedorCodigo(BaseModel):
    arquivos_gerados: list[ArquivoGerado] = []
    titulo: str = ""
    descricao: str = ""
    fase: Literal["finalizado", "erro"]
    mensagem: str
```

`url_pull_request` e `titulo_pr` foram removidos. `titulo` e `descricao` substituem o contexto que antes ia para o PR.

`ArquivoGerado` é um schema Pydantic que espelha `DadosArquivo` do `agente.py`. Por que duplicar?

- `DadosArquivo` pertence ao domínio do agente (LangGraph, tool calling) — é parte do contrato interno entre o LLM e o código
- `ArquivoGerado` pertence ao domínio da API HTTP — é parte do contrato externo entre o backend e o frontend

São responsabilidades distintas. Se o agente precisar de campos internos extras, isso não vaza para o schema HTTP. Se a API precisar de campos de apresentação, isso não polui o schema do LLM.

### `servico.py` — tradução entre mundos

```python
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

        arquivos_gerados: list[dict] = resultado.get("arquivos_gerados") or []

        if not arquivos_gerados:
            return RespostaDesenvolvedorCodigo(
                fase="erro",
                mensagem=mensagem_texto or "O agente não conseguiu gerar o código.",
            )

        arquivos = [ArquivoGerado(...) for arquivo in arquivos_gerados]
        return RespostaDesenvolvedorCodigo(
            arquivos_gerados=arquivos,
            titulo=resultado.get("titulo") or "",
            descricao=resultado.get("descricao") or "",
            fase="finalizado",
            mensagem=mensagem_texto,
        )
```

O critério de sucesso mudou: antes era verificar se `url_pull_request` estava preenchido. Agora é verificar se `arquivos_gerados` tem itens — pois os arquivos já foram escritos em disco pelo próprio `no_escrever_arquivos`.

---

## 9. Fluxo completo de uma requisição

> O endpoint `/api/v1/desenvolvedor-codigo/` ainda existe e pode ser chamado diretamente. Mas no fluxo normal, ele é chamado internamente pelo `servico.py` do Agente Arquiteto.

### Input: prompt de engenharia do Agente Arquiteto

```python
EntradaDesenvolvedorCodigo(
    prompt_engenharia="""# Prompt de Engenharia

## Papel e Especialidade
Você é um desenvolvedor sênior full-stack especializado em Angular 19 e FastAPI...

## Contexto do Projeto
[convenções do CLAUDE.md]

## Tarefa
Implemente um endpoint de cadastro de usuários com validação de e-mail único...

## Estrutura de Arquivos Esperada
- api/app/features/usuarios/__init__.py
- api/app/features/usuarios/esquemas.py
- api/app/features/usuarios/servico.py
- api/app/features/usuarios/roteador.py
"""
)
```

### Fase 1 — Serviço monta o estado inicial

```
servico.py — processar_prompt()
  │  Monta estado_inicial com prompt_engenharia
  │  Todos os outros campos do estado: None
  ▼
agente_desenvolvedor_codigo.ainvoke(estado_inicial)
```

### Fase 2 — `no_gerador_codigo` executa

```
LangGraph inicia no_gerador_codigo
  │
  │  LLM recebe:
  │    [SystemMessage(PROMPT_DESENVOLVEDOR)]  ← inclui CLAUDE.md
  │    [HumanMessage("Prompt de engenharia:\n\n{...}\n\nGere o código...")]
  │
  │  LLM processa o prompt e identifica:
  │    ✓ Feature: cadastro de usuários
  │    ✓ Arquivos necessários: 4 arquivos backend
  │
  │  LLM decide chamar a tool:
  │  AIMessage(
  │    content="",
  │    tool_calls=[{
  │      name: "escrever_arquivos_projeto",
  │      args: {
  │        arquivos: [
  │          { caminho: "api/app/features/usuarios/__init__.py", conteudo: "", descricao: "..." },
  │          { caminho: "api/app/features/usuarios/esquemas.py", conteudo: "from pydantic import...", ... },
  │          { caminho: "api/app/features/usuarios/servico.py", conteudo: "from ...", ... },
  │          { caminho: "api/app/features/usuarios/roteador.py", conteudo: "from fastapi import...", ... }
  │        ],
  │        titulo: "feat: cadastro de usuários",
  │        descricao: "## Mudanças\n- Adiciona endpoint POST /api/v1/usuarios/\n..."
  │      }
  │    }]
  │  )
  │
  ▼
roteador_desenvolvedor → tool_calls presente → "no_escrever_arquivos"
```

### Fase 3 — `no_escrever_arquivos` escreve em disco

```
no_escrever_arquivos
  │
  │  Extrai dados do tool_call
  │  Cria ToolMessage (protocolo obrigatório)
  │
  │  Para cada arquivo:
  │    caminho_completo = _RAIZ_PROJETO / "api/app/features/usuarios/__init__.py"
  │    caminho_completo.parent.mkdir(parents=True, exist_ok=True)
  │    caminho_completo.write_text(conteudo, encoding="utf-8")
  │
  │  Arquivos escritos:
  │    /Users/marcos/Projetos/Organizer IA/api/app/features/usuarios/__init__.py ✓
  │    /Users/marcos/Projetos/Organizer IA/api/app/features/usuarios/esquemas.py ✓
  │    /Users/marcos/Projetos/Organizer IA/api/app/features/usuarios/servico.py  ✓
  │    /Users/marcos/Projetos/Organizer IA/api/app/features/usuarios/roteador.py ✓
  │
  ▼
Estado final: { arquivos_gerados: [...], titulo: "feat: ...", descricao: "## Mudanças..." }
```

### Fase 4 — Serviço extrai e retorna

```
servico.py
  │  arquivos_gerados tem itens → fase = "finalizado"
  │  Converte list[dict] → list[ArquivoGerado]
  ▼
RespostaDesenvolvedorCodigo {
  arquivos_gerados: [
    { caminho: "api/app/features/usuarios/__init__.py", conteudo: "", descricao: "..." },
    { caminho: "api/app/features/usuarios/esquemas.py", conteudo: "from pydantic import...", ... },
    ...
  ],
  titulo: "feat: cadastro de usuários",
  descricao: "## Mudanças\n...",
  fase: "finalizado",
  mensagem: "Implementação concluída! 4 arquivo(s) escrito(s) no projeto."
}
```

### Fase 5 — Retorno ao Agente Arquiteto

```
_executar_desenvolvedor() no servico.py do Arquiteto
  │  recebe RespostaDesenvolvedorCodigo
  │  extrai: [arquivo.caminho for arquivo in resposta.arquivos_gerados]
  │  retorna: ["api/app/features/usuarios/__init__.py", ..., "api/app/features/usuarios/roteador.py"]
  ▼
RespostaAgente {
  resposta: "Implementação concluída! 4 arquivo(s) criado(s) no projeto.",
  fase: "implementado",
  markdown_final: "# Prompt de Engenharia...",
  prompt_engenharia: "...",
  arquivos_implementados: [
    "api/app/features/usuarios/__init__.py",
    "api/app/features/usuarios/esquemas.py",
    "api/app/features/usuarios/servico.py",
    "api/app/features/usuarios/roteador.py"
  ]
}
```

---

## 10. Decisões de design e boas práticas

### 10.1 Por que `temperature=0.1` e não `0.0`?

`temperature=0.0` (completamente determinístico) pode criar um problema em prompts muito longos: o modelo pode "travar" em um token subótimo, pois sempre escolhe o máximo sem qualquer variação. Com `0.1`, mantemos o quase-determinismo mas com uma pequena margem de exploração que ajuda o modelo a produzir código mais natural.

Em geração de código, a temperatura ideal está entre `0.0` e `0.2`. Acima de `0.3`, começam a aparecer inconsistências de nomenclatura e estruturas de código criativas demais para o contexto.

### 10.2 `write_text` sobrescreve arquivos existentes — comportamento intencional

`Path.write_text()` sobrescreve o arquivo se ele já existir. Isso é **intencional**: se o usuário pedir para implementar uma funcionalidade que já tem arquivos, os arquivos antigos são substituídos pelos novos gerados pelo LLM.

Em cenários de produção, seria necessário um mecanismo de diff/merge para não perder código existente. Para o estudo atual, a sobrescrita simples é aceitável e previsível.

### 10.3 Injeção do CLAUDE.md no PROMPT_DESENVOLVEDOR

Da mesma forma que no Agente Arquiteto, o PROMPT_DESENVOLVEDOR injeta o conteúdo do `CLAUDE.md` via f-string em tempo de módulo:

```python
_RAIZ_PROJETO = Path(__file__).parent.parent.parent.parent.parent

def _carregar_contexto_projeto() -> str:
    claude_md = _RAIZ_PROJETO / "CLAUDE.md"
    if claude_md.exists():
        return claude_md.read_text(encoding="utf-8")
    return ""

_CONTEXTO_PROJETO = _carregar_contexto_projeto()
```

Isso garante que **um único arquivo** (`CLAUDE.md`) é a fonte de verdade das convenções do projeto para ambos os agentes — arquiteto e desenvolvedor. Elimina a possibilidade de divergência onde um agente conhecia uma convenção e o outro não.

### 10.4 Por que o `ToolMessage` é obrigatório antes de escrever em disco?

```python
tool_message = ToolMessage(
    content="Código recebido. Escrevendo arquivos no projeto...",
    tool_call_id=tool_call["id"],
)

# Só depois: escreve os arquivos
for arquivo in arquivos:
    caminho_completo.write_text(...)
```

O protocolo de tool calling do LangChain/Groq exige que cada `AIMessage` com `tool_calls` seja seguido de `ToolMessage`(s) correspondentes (com o mesmo `tool_call_id`) antes de qualquer nova mensagem. Isso é válido mesmo neste agente onde o `ToolMessage` não é "enviado de volta ao LLM" — ele precisa estar no estado para que a sequência de mensagens seja válida e o grafo funcione corretamente.

### 10.5 Agente single-shot vs. multi-turn — quando usar cada um

Este agente foi projetado como **single-shot** (uma única chamada de LLM para gerar todo o código). Isso é possível porque o input já está completo e estruturado (o prompt de engenharia do Agente Arquiteto).

Quando faz sentido usar multi-turn neste contexto?

- Quando o código gerado é tão longo que ultrapassa o limite de tokens da resposta do LLM — você precisaria dividir a geração em partes, com cada parte sendo um turno
- Quando você quer um "revision loop": gerar → verificar com linter → corrigir → verificar novamente

Por ora, single-shot é a escolha mais simples e adequada.

### 10.6 O endpoint `/desenvolvedor-codigo/` ainda existe

Mesmo sendo chamado automaticamente pelo Agente Arquiteto, o endpoint `POST /api/v1/desenvolvedor-codigo/` continua exposto pela API. Isso é útil para:

- **Testes**: enviar um prompt diretamente sem passar pelo fluxo de chat do arquiteto
- **Debug**: verificar se o desenvolvedor está gerando o código correto para um prompt específico
- **Flexibilidade**: outros clientes (scripts, ferramentas externas) podem usar o desenvolvedor de forma independente

---

## 11. O que vem a seguir

Com os dois primeiros agentes implementados e integrados, o pipeline está funcional end-to-end:

```
[Agente Arquiteto de Prompts] → (automático) → [Agente Desenvolvedor] → arquivos em disco
```

### Próximas melhorias neste agente

**1. Lidar com o limite de tokens do LLM**

Features complexas podem gerar muitos arquivos com código extenso. O Llama 3.3 70B via Groq tem limite de tokens por resposta. Uma estratégia seria dividir a geração: primeiro gerar a lista de arquivos necessários, depois gerar o conteúdo de cada arquivo em chamadas separadas — padrão chamado **Map-Reduce** em pipelines de agentes.

**2. Geração com contexto do código existente**

Atualmente, o agente não sabe o que já existe no projeto. Se a feature precisa se integrar com código existente (ex: adicionar um endpoint a um router já existente), o agente não tem essa informação. Uma solução seria ler os arquivos relevantes do disco antes da geração e incluir no contexto — técnica de **Retrieval-Augmented Generation (RAG)** aplicada ao filesystem local.

**3. Streaming de progresso**

A chamada atual bloqueia o frontend por 30-60s (tempo do Arquiteto + tempo do Desenvolvedor). Implementar Server-Sent Events (SSE) permitiria mostrar o progresso em tempo real: "gerando prompt... (20s) → implementando arquivos... (40s) → concluído".

**4. Agente Revisor de Código (Passo 03)**

O próximo agente do pipeline pode revisar o código escrito em disco, verificar se as convenções foram seguidas, rodar análise estática e sugerir melhorias antes de commitar.

**5. Testes unitários dos nós**

Cada nó do grafo pode ser testado isoladamente mockando o LLM e o filesystem:

```python
async def test_no_escrever_arquivos(tmp_path, monkeypatch):
    monkeypatch.setattr("app.agents.desenvolvedor_codigo.agente._RAIZ_PROJETO", tmp_path)
    estado = {
        "mensagens": [AIMessage(content="", tool_calls=[{
            "id": "call_1",
            "name": "escrever_arquivos_projeto",
            "args": {
                "arquivos": [{"caminho": "api/test.py", "conteudo": "x = 1", "descricao": "teste"}],
                "titulo": "teste",
                "descricao": "teste"
            }
        }])]
    }
    resultado = await no_escrever_arquivos(estado)
    assert (tmp_path / "api" / "test.py").read_text() == "x = 1"
    assert len(resultado["arquivos_gerados"]) == 1
```

---

*Documento atualizado em: Março de 2026*
*Projeto: Organizer IA — Applied AI Engineering*
