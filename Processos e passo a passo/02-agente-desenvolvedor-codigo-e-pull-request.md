# 02 — Agente Desenvolvedor de Código e Pull Request

> Implementação de um agente LangGraph que recebe um prompt de engenharia, gera código completo para as tecnologias identificadas e abre automaticamente um Pull Request no repositório GitHub.

---

## Índice

1. [Contexto no pipeline multi-agente](#1-contexto-no-pipeline-multi-agente)
2. [Geração de código com LLMs — conceitos fundamentais](#2-geração-de-código-com-llms--conceitos-fundamentais)
3. [Stack utilizada — o que é novo neste agente](#3-stack-utilizada--o-que-é-novo-neste-agente)
4. [Reestruturação arquitetural — a pasta `agents/`](#4-reestruturação-arquitetural--a-pasta-agents)
5. [Arquitetura do agente com LangGraph](#5-arquitetura-do-agente-com-langgraph)
6. [Tool Calling com schemas aninhados](#6-tool-calling-com-schemas-aninhados)
7. [Prompt Engineering — o PROMPT_DESENVOLVEDOR](#7-prompt-engineering--o-prompt_desenvolvedor)
8. [Integração com o GitHub via PyGithub](#8-integração-com-o-github-via-pygithub)
9. [Estrutura de arquivos](#9-estrutura-de-arquivos)
10. [Fluxo completo de uma requisição](#10-fluxo-completo-de-uma-requisição)
11. [Decisões de design e boas práticas](#11-decisões-de-design-e-boas-práticas)
12. [O que vem a seguir](#12-o-que-vem-a-seguir)

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
                 │  prompt_engenharia (markdown estruturado)
                 ▼
┌──────────────────────────────────┐
│  Agente Desenvolvedor de Código  │  ← Passo 02 (este documento)
│  Lê o prompt, identifica a       │
│  stack, gera os arquivos e       │
│  abre um Pull Request no GitHub  │
└──────────────────────────────────┘
                 │
                 │  Pull Request (branch + commits)
                 ▼
┌──────────────────────────────────┐
│  Agente Revisor de Código        │  ← Passo 03 (futuro)
│  Revisa o PR, sugere melhorias   │
│  e aprova ou solicita alterações │
└──────────────────────────────────┘
```

O ponto de integração entre o Agente Arquiteto e o Agente Desenvolvedor é o campo `prompt_engenharia` do schema `RespostaAgente`. O output de um se torna diretamente o input do outro — padrão de composição de agentes chamado **handoff**.

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

# Padrões de Código
- Sempre async def nas rotas
- Proibido retornar dict — sempre schemas Pydantic
- Proibido try/except
- Estrutura de pastas: features/{nome}/roteador.py, esquemas.py, servico.py
...
```

O segundo cenário instrui o LLM de forma explícita e imperativa. A qualidade do código gerado é substancialmente superior porque o modelo recebe **restrições concretas**, não apenas uma intenção vaga.

### 2.3 Temperature e geração de código

Ao contrário de tarefas conversacionais, geração de código exige **determinismo e precisão**. Uma temperatura alta (0.7+) introduz "criatividade" que pode resultar em:

- Nomes de variáveis inconsistentes entre arquivos do mesmo PR
- Lógica correta mas estruturada de formas diferentes a cada geração
- Comentários inesperados ou estruturas de código não convencionais

Por isso, o Agente Desenvolvedor usa `temperature=0.1` — o mais próximo de determinístico possível sem ser `0.0` (que pode tornar o modelo repetitivo em prompts longos). Com temperatura baixa, o modelo sempre escolhe os tokens mais prováveis, produzindo código mais previsível, consistente e fiel às convenções descritas no prompt.

---

## 3. Stack utilizada — o que é novo neste agente

A base da stack é idêntica ao Agente Arquiteto (FastAPI, LangGraph, LangChain, Groq). O que é novo:

| Tecnologia | Versão | Papel |
|------------|--------|-------|
| **PyGithub** | ≥ 2.0.0 | Cliente Python para a GitHub REST API |

### O que é PyGithub?

PyGithub é uma biblioteca Python que encapsula a [GitHub REST API v3](https://docs.github.com/en/rest). Em vez de fazer chamadas HTTP manuais com `httpx` ou `requests`, usamos objetos Python de alto nível:

```python
# Sem PyGithub (httpx puro) — verboso e propenso a erros
response = httpx.put(
    f"https://api.github.com/repos/{repo}/contents/{path}",
    headers={"Authorization": f"Bearer {token}"},
    json={"message": "feat: add file", "content": base64.b64encode(content.encode()).decode()}
)

# Com PyGithub — declarativo e tipado
repo.create_file(path=path, message="feat: add file", content=content, branch=branch)
```

PyGithub cuida de:
- Autenticação (Bearer token nos headers)
- Serialização (encoding base64 do conteúdo dos arquivos — requisito da GitHub API)
- Paginação de resultados
- Mapeamento de respostas JSON para objetos Python com atributos tipados

### Por que não usar httpx diretamente?

Para uma integração simples como a nossa (criar branch → commitar arquivos → abrir PR), PyGithub reduz significativamente o código e a complexidade. A desvantagem é que PyGithub é **síncrono** — não tem suporte a `async/await`. Discutimos as implicações disso na seção de decisões de design.

---

## 4. Reestruturação arquitetural — a pasta `agents/`

Durante a implementação deste agente, identificamos uma oportunidade de melhoria arquitetural: mover todos os agentes de IA de `features/` para uma nova pasta `agents/`.

### 4.1 A estrutura original

```
api/app/
├── core/
└── features/
    ├── chat/              ← feature HTTP convencional
    ├── engenheiro_prompt/ ← agente de IA (estava aqui)
    └── desenvolvedor_codigo/ ← agente de IA (iria aqui)
```

### 4.2 O problema conceitual

`features/` segue o padrão **Feature Slicing** — cada pasta representa uma funcionalidade do sistema do ponto de vista do usuário, com seu próprio router, schemas e service. Esse padrão é excelente para aplicações web convencionais.

Mas agentes de IA têm uma natureza diferente de features HTTP comuns:
- Não são apenas um endpoint que processa um request
- Contêm um grafo de estado com múltiplos nós e arestas
- Orquestram múltiplas chamadas de LLM
- Podem ter integrações com serviços externos (GitHub, no nosso caso)

Misturar um `ServicoChat` simples com um grafo LangGraph de 200 linhas na mesma pasta `features/` viola o **Princípio de Separação de Conceitos** — coisas de natureza distinta devem estar organizadas separadamente.

### 4.3 A solução — Domain Separation

```
api/app/
├── core/
├── agents/                    ← agentes de IA
│   ├── __init__.py
│   ├── engenheiro_prompt/     ← movido de features/
│   └── desenvolvedor_codigo/  ← criado aqui diretamente
└── features/
    └── chat/                  ← features HTTP convencionais
```

Essa separação torna a arquitetura autoexplicativa: ao abrir `agents/`, você sabe imediatamente que está no domínio de IA. Ao abrir `features/`, você está no domínio de features web convencionais.

### 4.4 O impacto nos imports

A mudança física de pasta exige atualizar os imports em todos os módulos que referenciam os agentes. Os arquivos afetados foram:

| Arquivo | Import antigo | Import novo |
|---------|---------------|-------------|
| `main.py` | `app.features.engenheiro_prompt.roteador` | `app.agents.engenheiro_prompt.roteador` |
| `main.py` | `app.features.desenvolvedor_codigo.roteador` | `app.agents.desenvolvedor_codigo.roteador` |
| `agents/engenheiro_prompt/roteador.py` | `app.features.engenheiro_prompt.*` | `app.agents.engenheiro_prompt.*` |
| `agents/engenheiro_prompt/servico.py` | `app.features.engenheiro_prompt.*` | `app.agents.engenheiro_prompt.*` |
| `agents/desenvolvedor_codigo/roteador.py` | `app.features.desenvolvedor_codigo.*` | `app.agents.desenvolvedor_codigo.*` |
| `agents/desenvolvedor_codigo/servico.py` | `app.features.desenvolvedor_codigo.*` | `app.agents.desenvolvedor_codigo.*` |
| `agents/desenvolvedor_codigo/agente.py` | `app.features.desenvolvedor_codigo.github` | `app.agents.desenvolvedor_codigo.github` |

> **Nota prática**: em projetos maiores, esse tipo de refatoração de imports em larga escala costuma ser feito com ferramentas como `sed` em linha de comando ou a funcionalidade "Find and Replace" da IDE. Neste projeto, a escala pequena permitiu fazer manualmente.

---

## 5. Arquitetura do agente com LangGraph

### 5.1 O grafo

```
START
  │
  ▼
┌────────────────────┐
│  no_gerador_codigo │  ← LLM analisa o prompt e gera todos os arquivos via tool call
└────────────────────┘
         │
         ▼
  [roteador_desenvolvedor]  ← Conditional Edge: o LLM chamou submeter_codigo_para_pull_request?
         │
    ┌────┴────┐
    │         │
    ▼         ▼
  (Sim)      (Não)
    │           │
    ▼           ▼
┌──────────┐   END  ← Retorna erro (LLM não chamou a tool)
│no_criar_pr│
└──────────┘
    │
    ▼
   END  ← Retorna URL do PR criado
```

A diferença fundamental em relação ao Agente Arquiteto de Prompts é que **este grafo não é multi-turn**. Enquanto o arquiteto mantinha uma conversa com o usuário ao longo de vários turnos (coletando informações pergunta a pergunta), o desenvolvedor opera em **single-shot**: recebe o prompt de engenharia completo, faz uma única chamada de LLM para gerar todo o código, e depois executa a integração com o GitHub.

Isso reflete a natureza diferente das duas tarefas:
- **Coleta de requisitos**: iterativa por natureza — você precisa de turnos de conversa para refinar as informações
- **Geração de código**: pode ser executada de forma completa em uma única operação, dado que o input (o prompt de engenharia) já contém todas as informações necessárias

### 5.2 O Estado (TypedDict)

```python
class EstadoAgente(TypedDict):
    mensagens: Annotated[list[BaseMessage], add_messages]
    prompt_engenharia: str
    arquivos_gerados: Optional[list[dict]]
    titulo_pr: Optional[str]
    descricao_pr: Optional[str]
    nome_branch: Optional[str]
    url_pull_request: Optional[str]
```

Diferente do estado do Agente Arquiteto, aqui não há `dados_coletados` nem `markdown_final`. Os campos do estado mapeiam diretamente o ciclo de vida desta tarefa:

| Campo | Tipo | Preenchido em | Finalidade |
|-------|------|---------------|------------|
| `mensagens` | `list[BaseMessage]` | `no_gerador_codigo` | Histórico de mensagens do grafo (com reducer `add_messages`) |
| `prompt_engenharia` | `str` | Estado inicial | Input do agente — vem do Agente Arquiteto |
| `arquivos_gerados` | `Optional[list[dict]]` | `no_criar_pr` | Lista de arquivos extraídos do tool call |
| `titulo_pr` | `Optional[str]` | `no_criar_pr` | Título do PR para o serviço e a resposta HTTP |
| `descricao_pr` | `Optional[str]` | `no_criar_pr` | Descrição markdown do PR |
| `nome_branch` | `Optional[str]` | `no_criar_pr` | Branch criado com timestamp de unicidade |
| `url_pull_request` | `Optional[str]` | `no_criar_pr` | URL do PR aberto no GitHub |

O campo `prompt_engenharia` é inicializado no estado inicial (não via reducer), pois é o input fixo do agente — não muda ao longo da execução.

### 5.3 Os nós (Nodes)

**`no_gerador_codigo`**

```python
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
```

Diferente do `no_agente` do arquiteto, este nó **constrói o contexto do zero** a cada chamada — não há histórico de conversas anteriores para anexar. O LLM recebe exatamente dois elementos:
1. O system prompt com as convenções do projeto
2. O prompt de engenharia completo + instrução explícita para chamar a tool

A instrução explícita ao final ("Gere o código completo e chame `submeter_codigo_para_pull_request`") é uma técnica de **instruction following** que aumenta a confiabilidade do tool call. Sem essa instrução, o modelo pode gerar o código em texto puro ao invés de estruturá-lo no schema da tool.

**`no_criar_pr`**

```python
async def no_criar_pr(estado: EstadoAgente) -> dict:
    ultima_mensagem = estado["mensagens"][-1]
    tool_call = ultima_mensagem.tool_calls[0]
    dados: dict = tool_call["args"]

    tool_message = ToolMessage(
        content="Código recebido. Criando Pull Request no GitHub...",
        tool_call_id=tool_call["id"],
    )

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    nome_branch = f"{dados['nome_branch_base']}-{timestamp}"

    servico_github = ServicoGitHub()
    url_pr = servico_github.criar_pull_request(
        nome_branch=nome_branch,
        titulo=dados["titulo_pr"],
        descricao=dados["descricao_pr"],
        arquivos=dados["arquivos"],
    )

    return {
        "mensagens": [tool_message, AIMessage(content=f"Pull Request criado com sucesso! Acesse em: {url_pr}")],
        "arquivos_gerados": dados["arquivos"],
        "titulo_pr": dados["titulo_pr"],
        "descricao_pr": dados["descricao_pr"],
        "nome_branch": nome_branch,
        "url_pull_request": url_pr,
    }
```

Este nó não faz chamada de LLM — ele é um **nó de ação** puro. Extrai os dados estruturados do tool call, delega a criação do PR para o `ServicoGitHub` e propaga os resultados para o estado.

O `ToolMessage` é criado antes da chamada ao GitHub (protocolo obrigatório, explicado na decisão de design 11.4).

### 5.4 O roteador (Conditional Edge)

```python
def roteador_desenvolvedor(estado: EstadoAgente) -> Literal["no_criar_pr", "__end__"]:
    ultima_mensagem = estado["mensagens"][-1]
    if isinstance(ultima_mensagem, AIMessage) and ultima_mensagem.tool_calls:
        return "no_criar_pr"
    return END
```

A lógica é idêntica ao roteador do Agente Arquiteto. O padrão é consistente entre os dois agentes:
- `tool_calls` presente → o LLM está pronto para executar a ação → avança para o nó de ação
- `tool_calls` ausente → o LLM respondeu em texto puro (caso de erro ou LLM não seguiu a instrução) → encerra o grafo

---

## 6. Tool Calling com schemas aninhados

### 6.1 O desafio: uma tool que recebe uma lista de objetos

No Agente Arquiteto, a tool `solicitar_geracao_prompt` recebia campos simples (`str`, `list[str]`). Aqui o desafio é maior: precisamos que o LLM entregue **uma lista de arquivos**, onde cada arquivo tem três campos (caminho, conteúdo, descrição).

Isso exige um schema **aninhado** — um `BaseModel` dentro de outro:

```python
class DadosArquivo(BaseModel):
    caminho: str = Field(
        description="Caminho relativo do arquivo no repositório (ex: api/app/features/auth/roteador.py)"
    )
    conteudo: str = Field(description="Conteúdo completo e funcional do arquivo")
    descricao: str = Field(description="Descrição em uma linha do que este arquivo implementa")


class CodigoParaPR(BaseModel):
    arquivos: list[DadosArquivo] = Field(
        description="Lista de todos os arquivos a serem criados no PR"
    )
    titulo_pr: str = Field(description="Título claro do Pull Request em português")
    descricao_pr: str = Field(description="Descrição markdown do PR listando todas as mudanças")
    nome_branch_base: str = Field(
        description="Nome base do branch no padrão feat/{nome-feature-kebab-case}"
    )
```

### 6.2 O JSON Schema gerado automaticamente pelo Pydantic

Quando `bind_tools([submeter_codigo_para_pull_request])` é chamado, o LangChain serializa `CodigoParaPR` para JSON Schema e inclui na requisição ao Groq. O schema gerado tem a seguinte estrutura:

```json
{
  "name": "submeter_codigo_para_pull_request",
  "description": "Chame quando todos os arquivos de código estiverem prontos para criar o Pull Request.",
  "parameters": {
    "type": "object",
    "properties": {
      "arquivos": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "caminho": { "type": "string", "description": "Caminho relativo do arquivo..." },
            "conteudo": { "type": "string", "description": "Conteúdo completo e funcional..." },
            "descricao": { "type": "string", "description": "Descrição em uma linha..." }
          },
          "required": ["caminho", "conteudo", "descricao"]
        },
        "description": "Lista de todos os arquivos a serem criados no PR"
      },
      "titulo_pr": { "type": "string", "description": "Título claro do Pull Request em português" },
      "descricao_pr": { "type": "string", "description": "Descrição markdown do PR listando todas as mudanças" },
      "nome_branch_base": { "type": "string", "description": "Nome base do branch no padrão feat/..." }
    },
    "required": ["arquivos", "titulo_pr", "descricao_pr", "nome_branch_base"]
  }
}
```

O LLM recebe esse schema e sabe exatamente como estruturar o tool call — incluindo cada arquivo com seus três campos. O Pydantic faz todo esse trabalho de serialização automaticamente: você define o modelo, ele gera o schema correto para qualquer provedor de LLM.

### 6.3 Como os dados chegam no nó `no_criar_pr`

Quando o LLM decide chamar a tool, o retorno do `llm.ainvoke()` é um `AIMessage` com:

```python
AIMessage(
    content="",
    tool_calls=[{
        "id": "call_xyz123",
        "name": "submeter_codigo_para_pull_request",
        "args": {
            "arquivos": [
                {
                    "caminho": "api/app/features/auth/roteador.py",
                    "conteudo": "from fastapi import APIRouter...\n\n# ... código completo",
                    "descricao": "Router FastAPI com endpoint de autenticação"
                },
                {
                    "caminho": "api/app/features/auth/esquemas.py",
                    "conteudo": "from pydantic import BaseModel...",
                    "descricao": "Schemas Pydantic de entrada e saída"
                }
            ],
            "titulo_pr": "feat: implementa autenticação de usuários",
            "descricao_pr": "## Mudanças\n- Adiciona endpoint POST /api/v1/auth/login\n...",
            "nome_branch_base": "feat/autenticacao-usuarios"
        }
    }]
)
```

No `no_criar_pr`, acessamos `tool_call["args"]` para extrair esses dados. A chave `"arquivos"` contém a lista de dicts que passamos diretamente para `ServicoGitHub.criar_pull_request()`.

### 6.4 A importância das `description` nos Fields

Cada `Field(description=...)` é crucial. O LLM lê essas descrições para entender o que preencher em cada campo. Por exemplo:

```python
caminho: str = Field(
    description="Caminho relativo do arquivo no repositório (ex: api/app/features/auth/roteador.py)"
)
```

O exemplo concreto no description (`ex: api/app/features/auth/roteador.py`) mostra o formato esperado. Sem isso, o LLM poderia usar caminhos absolutos, caminhos relativos errados ou formatos inconsistentes.

---

## 7. Prompt Engineering — o PROMPT_DESENVOLVEDOR

```python
PROMPT_DESENVOLVEDOR = """Você é um desenvolvedor full-stack sênior especializado em Angular 19 e FastAPI.

Você recebe um prompt de engenharia detalhado e deve gerar TODOS os arquivos de código necessários para
implementar a feature descrita, seguindo rigorosamente as convenções do projeto.

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
...
```

### Análise das seções do prompt

**1. Definição de persona**

```
Você é um desenvolvedor full-stack sênior especializado em Angular 19 e FastAPI.
```

LLMs respondem melhor quando a persona é específica e especializada. "Desenvolvedor sênior" ativa padrões de código mais cuidadosos; "Angular 19 e FastAPI" direciona o modelo para o subset correto do seu conhecimento de programação.

**2. Estrutura de pastas explícita**

```
Estrutura por feature em `api/app/features/{nome_feature}/`:
  - `__init__.py` (arquivo vazio)
  - `roteador.py` — APIRouter com endpoints assíncronos
  - `esquemas.py` — Schemas Pydantic separados para entrada e saída
  - `servico.py` — Lógica de negócio com injeção via `Depends()`
```

Informar a estrutura de pastas é crítico porque o LLM precisa gerar os `caminho` corretos nos campos `DadosArquivo.caminho`. Sem isso, cada geração poderia usar estruturas diferentes e incompatíveis com o projeto real.

**3. Proibições explícitas e imperativas**

```
- Proibido retornar `dict` nas rotas — sempre schemas Pydantic
- Proibido `try/except` e `print()`
- Proibido `Any` do módulo `typing` — tipagem estrita obrigatória
```

LLMs tendem a gerar código "médio" — o que a maioria dos desenvolvedores escreve. A maioria dos exemplos online usa `try/except` em rotas FastAPI, retorna dicts, etc. Sem proibições explícitas, o modelo segue esses padrões populares. Com as proibições, ele é forçado a produzir código que adere às nossas convenções.

**4. Instrução de encerramento explícita**

```
Chame `submeter_codigo_para_pull_request` com todos os arquivos, título e descrição do PR
```

Esta instrução ao final do prompt garante que o LLM entende que a conclusão do seu trabalho é chamar a tool — não apenas gerar texto. É uma forma de **instruction anchoring**: reforçar o comportamento desejado ao final do prompt.

---

## 8. Integração com o GitHub via PyGithub

### 8.1 O `ServicoGitHub`

```python
class ServicoGitHub:
    def __init__(self) -> None:
        self._cliente = Github(configuracoes.github_token.get_secret_value())
        self._repo = self._cliente.get_repo(configuracoes.github_repo)

    def criar_pull_request(
        self,
        nome_branch: str,
        titulo: str,
        descricao: str,
        arquivos: list[dict],
    ) -> str:
        branch_base = configuracoes.github_branch_base
        sha_base = self._repo.get_branch(branch_base).commit.sha

        self._repo.create_git_ref(f"refs/heads/{nome_branch}", sha_base)

        for arquivo in arquivos:
            self._repo.create_file(
                path=arquivo["caminho"],
                message=f"feat: adiciona {arquivo['caminho']}",
                content=arquivo["conteudo"],
                branch=nome_branch,
            )

        pr = self._repo.create_pull(
            title=titulo,
            body=descricao,
            head=nome_branch,
            base=branch_base,
        )

        return pr.html_url
```

O método `criar_pull_request` executa exatamente **três operações** com a GitHub API, na ordem necessária:

### 8.2 Operação 1 — Criar o branch

```python
sha_base = self._repo.get_branch(branch_base).commit.sha
self._repo.create_git_ref(f"refs/heads/{nome_branch}", sha_base)
```

Para criar um branch no GitHub, você precisa do SHA do commit mais recente do branch base (geralmente `main`). O `create_git_ref` cria uma referência Git apontando para esse commit. Na prática, é como fazer `git checkout -b feat/nova-feature main` — o novo branch aponta para o mesmo commit que `main`.

**Por que `refs/heads/` como prefixo?**

Branches no Git são referências (`refs`) armazenadas em `refs/heads/`. Tags ficam em `refs/tags/`. A GitHub API usa o nome completo da referência para criar branches.

### 8.3 Operação 2 — Commitar cada arquivo

```python
for arquivo in arquivos:
    self._repo.create_file(
        path=arquivo["caminho"],
        message=f"feat: adiciona {arquivo['caminho']}",
        content=arquivo["conteudo"],
        branch=nome_branch,
    )
```

`create_file` faz uma requisição `PUT /repos/{owner}/{repo}/contents/{path}` para cada arquivo. Internamente, o PyGithub:

1. Recebe o `content` como string UTF-8
2. Faz o encoding em Base64 (requisito da GitHub Contents API)
3. Envia a requisição com o SHA do arquivo anterior (None para novos arquivos)
4. Cada chamada cria um commit separado no branch

**Implicação importante**: se o agente gerar 5 arquivos, o PR terá 5 commits — um por arquivo. Para um PR gerado automaticamente, isso é aceitável. Em contextos de produção, você poderia usar a [Git Trees API](https://docs.github.com/en/rest/git/trees) para criar todos os arquivos em um único commit (mais complexo, mas mais "limpo" no histórico).

### 8.4 Operação 3 — Abrir o Pull Request

```python
pr = self._repo.create_pull(
    title=titulo,
    body=descricao,
    head=nome_branch,   # branch com as mudanças
    base=branch_base,   # branch de destino (main)
)
return pr.html_url
```

`create_pull` abre o PR via `POST /repos/{owner}/{repo}/pulls`. Os parâmetros `head` e `base` seguem a convenção do Git:
- `head`: branch de **origem** (onde estão as mudanças)
- `base`: branch de **destino** (onde as mudanças serão mergeadas)

O retorno `pr.html_url` é a URL do PR no formato `https://github.com/{owner}/{repo}/pull/{number}` — o que retornamos ao usuário.

### 8.5 Configuração necessária

Três variáveis de ambiente controlam a integração com o GitHub:

```env
GITHUB_TOKEN=ghp_seu_personal_access_token
GITHUB_REPO=marcos/Organizer-IA
GITHUB_BRANCH_BASE=main
```

**`GITHUB_TOKEN`** — Personal Access Token (PAT) com escopo `repo`. No GitHub: Settings → Developer settings → Personal access tokens → Fine-grained tokens (recomendado) ou Classic tokens. O escopo mínimo necessário é:
- `repo:read` — ler o repositório
- `repo:write` (ou `contents:write`) — criar arquivos e commits
- `pull_requests:write` — abrir Pull Requests

**`GITHUB_REPO`** — formato `{owner}/{repo}`, idêntico ao que aparece na URL do repositório.

**`GITHUB_BRANCH_BASE`** — branch de destino do PR. Default: `"main"`.

---

## 9. Estrutura de arquivos

```
api/app/
├── core/
│   └── configuracoes.py           # Adicionados: github_token, github_repo, github_branch_base
│
├── agents/                        # Nova pasta — domínio de agentes de IA
│   ├── __init__.py
│   │
│   ├── engenheiro_prompt/         # Movido de features/ (sem mudanças no código)
│   │   ├── __init__.py
│   │   ├── agente.py
│   │   ├── esquemas.py
│   │   ├── servico.py
│   │   └── roteador.py
│   │
│   └── desenvolvedor_codigo/      # Novo agente
│       ├── __init__.py
│       ├── agente.py              # Grafo LangGraph — lógica principal do agente
│       ├── esquemas.py            # Pydantic: EntradaDesenvolvedorCodigo, RespostaDesenvolvedorCodigo
│       ├── github.py              # ServicoGitHub — integração com a GitHub API
│       ├── servico.py             # ServicoDesenvolvedorCodigo — orquestra agente e retorno HTTP
│       └── roteador.py            # APIRouter — POST /api/v1/desenvolvedor-codigo/
│
└── features/
    └── chat/                      # Feature HTTP convencional (inalterada)
        ├── __init__.py
        ├── roteador.py
        ├── esquemas.py
        └── servico.py
```

### `configuracoes.py` — configurações opcionais do GitHub

```python
class Configuracoes(BaseSettings):
    # ... campos existentes
    github_token: Optional[SecretStr] = None   # Optional: app sobe sem GitHub
    github_repo: str = ""
    github_branch_base: str = "main"
```

A grande diferença de `groq_api_key` é que `github_token` é `Optional`. Isso foi uma decisão deliberada: sem a chave do Groq, nenhum agente funciona — a aplicação deve falhar imediatamente. Sem as credenciais do GitHub, apenas o endpoint `/desenvolvedor-codigo/` falha — os outros endpoints (`/engenheiro-prompt/`, `/chat/`) continuam funcionando normalmente. `Optional` implementa o princípio de **graceful degradation** (degradação graciosa) no nível de configuração.

### `esquemas.py` — contratos da API

```python
class ArquivoGerado(BaseModel):
    caminho: str
    conteudo: str
    descricao: str

class EntradaDesenvolvedorCodigo(BaseModel):
    prompt_engenharia: str           # O output do Agente Arquiteto

class RespostaDesenvolvedorCodigo(BaseModel):
    url_pull_request: Optional[str] = None
    arquivos_gerados: list[ArquivoGerado] = []
    titulo_pr: str = ""
    fase: Literal["finalizado", "erro"]
    mensagem: str
```

`ArquivoGerado` é um schema Pydantic que espelha `DadosArquivo` do `agente.py`. Por que duplicar?

- `DadosArquivo` pertence ao domínio do agente (LangGraph, tool calling) — é parte do contrato interno entre o LLM e o código
- `ArquivoGerado` pertence ao domínio da API HTTP — é parte do contrato externo entre o backend e quem consome a API

São responsabilidades distintas. Se o agente precisar adicionar campos internos (ex: um `hash_conteudo` para deduplicação), isso não deve vazar para o schema HTTP. Se a API precisar adicionar campos de apresentação (ex: `tamanho_bytes`), isso não deve poluir o schema do LLM.

### `servico.py` — tradução entre mundos

```python
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
        mensagem_texto: str = ultima_mensagem.content if ultima_mensagem else ""

        if resultado.get("url_pull_request"):
            arquivos = [ArquivoGerado(...) for arquivo in resultado["arquivos_gerados"]]
            return RespostaDesenvolvedorCodigo(fase="finalizado", ...)

        return RespostaDesenvolvedorCodigo(fase="erro", mensagem=mensagem_texto or "...")
```

O serviço implementa um padrão importante: **detecção de sucesso vs. erro pelo estado final** do grafo. Se `url_pull_request` está preenchido no estado final, o agente completou o fluxo feliz. Se está `None`, o roteador chegou ao `END` sem passar por `no_criar_pr` — o LLM não chamou a tool.

Note também o uso de `next()` com um `reversed()` para localizar a última `AIMessage` sem `tool_calls`. Essa mesma técnica foi usada no Agente Arquiteto e é um padrão recorrente para extrair a "resposta final" de uma sequência de mensagens LangChain.

---

## 10. Fluxo completo de uma requisição

### Input: prompt de engenharia do Agente Arquiteto

```
POST /api/v1/desenvolvedor-codigo/
{
  "prompt_engenharia": "# Prompt de Engenharia\n\n## Papel e Especialidade\nVocê é um desenvolvedor Python sênior...\n\n## Tarefa\nImplemente um sistema de autenticação com JWT..."
}
```

### Fase 1 — FastAPI recebe e valida

```
roteador.py
  │  EntradaDesenvolvedorCodigo validado pelo Pydantic
  │  (campo "prompt_engenharia" é obrigatório)
  ▼
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
  │    [SystemMessage(PROMPT_DESENVOLVEDOR)] +
  │    [HumanMessage("Prompt de engenharia:\n\n{...}\n\nGere o código completo...")]
  │
  │  LLM processa o prompt de engenharia e identifica:
  │    ✓ Stack: FastAPI + Angular 19
  │    ✓ Feature: autenticação com JWT
  │    ✓ Arquivos necessários: 4 arquivos backend + 2 frontend
  │
  │  LLM decide chamar a tool:
  │  AIMessage(
  │    content="",
  │    tool_calls=[{
  │      name: "submeter_codigo_para_pull_request",
  │      args: {
  │        arquivos: [
  │          { caminho: "api/app/features/auth/__init__.py", conteudo: "", descricao: "..." },
  │          { caminho: "api/app/features/auth/esquemas.py", conteudo: "from pydantic import...", ... },
  │          { caminho: "api/app/features/auth/servico.py", conteudo: "import jwt...", ... },
  │          { caminho: "api/app/features/auth/roteador.py", conteudo: "from fastapi import...", ... },
  │          { caminho: "web/src/app/core/services/autenticacao.service.ts", conteudo: "...", ... },
  │          { caminho: "web/src/app/features/login/login.component.ts", conteudo: "...", ... }
  │        ],
  │        titulo_pr: "feat: implementa autenticação de usuários com JWT",
  │        descricao_pr: "## Mudanças\n\n### Backend\n- Adiciona endpoint POST /api/v1/auth/login\n...",
  │        nome_branch_base: "feat/autenticacao-jwt"
  │      }
  │    }]
  │  )
  │
  ▼
roteador_desenvolvedor → tool_calls presente → "no_criar_pr"
```

### Fase 3 — `no_criar_pr` cria o PR

```
no_criar_pr
  │
  │  Extrai dados do tool_call
  │  Cria ToolMessage (protocolo obrigatório)
  │
  │  timestamp = "20260311143052"
  │  nome_branch = "feat/autenticacao-jwt-20260311143052"
  │
  │  ServicoGitHub()
  │    .criar_pull_request(
  │        nome_branch="feat/autenticacao-jwt-20260311143052",
  │        titulo="feat: implementa autenticação de usuários com JWT",
  │        descricao="## Mudanças\n\n### Backend\n...",
  │        arquivos=[{...}, {...}, {...}, {...}, {...}, {...}]
  │    )
  │
  │  GitHub API — Operação 1: get_branch("main") → sha = "a330d43..."
  │  GitHub API — Operação 2: create_git_ref("refs/heads/feat/autenticacao-jwt-20260311143052", sha)
  │  GitHub API — Operação 3: create_file("api/app/features/auth/__init__.py", ...) → commit 1
  │  GitHub API — Operação 4: create_file("api/app/features/auth/esquemas.py", ...) → commit 2
  │  GitHub API — Operação 5: create_file("api/app/features/auth/servico.py", ...) → commit 3
  │  GitHub API — Operação 6: create_file("api/app/features/auth/roteador.py", ...) → commit 4
  │  GitHub API — Operação 7: create_file("web/.../autenticacao.service.ts", ...) → commit 5
  │  GitHub API — Operação 8: create_file("web/.../login.component.ts", ...) → commit 6
  │  GitHub API — Operação 9: create_pull(head="feat/...", base="main") → PR #42
  │
  │  url_pr = "https://github.com/marcos/Organizer-IA/pull/42"
  │
  ▼
Estado final: { url_pull_request: "https://github.com/...", arquivos_gerados: [...], ... }
```

### Fase 4 — Serviço extrai e retorna

```
servico.py
  │  url_pull_request presente → fase = "finalizado"
  │  Converte list[dict] → list[ArquivoGerado]
  ▼
RespostaDesenvolvedorCodigo {
  url_pull_request: "https://github.com/marcos/Organizer-IA/pull/42",
  arquivos_gerados: [
    { caminho: "api/app/features/auth/__init__.py", conteudo: "", descricao: "..." },
    ...
  ],
  titulo_pr: "feat: implementa autenticação de usuários com JWT",
  fase: "finalizado",
  mensagem: "Pull Request criado com sucesso! Acesse em: https://github.com/..."
}
```

---

## 11. Decisões de design e boas práticas

### 11.1 Por que `temperature=0.1` e não `0.0`?

`temperature=0.0` (completamente determinístico) pode criar um problema em prompts muito longos: o modelo pode "travar" em um token subótimo, pois sempre escolhe o máximo sem qualquer variação. Com `0.1`, mantemos a quase-determinismo mas com uma pequena margem de exploração que ajuda o modelo a produzir código mais natural.

Em geração de código, a temperatura ideal está entre `0.0` e `0.2`. Acima de `0.3`, você começa a ver inconsistências de nomenclatura e estruturas de código criativas demais para o contexto.

### 11.2 Unicidade do branch com timestamp

```python
timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
nome_branch = f"{dados['nome_branch_base']}-{timestamp}"
# Exemplo: feat/autenticacao-jwt-20260311143052
```

O LLM gera um `nome_branch_base` semanticamente descritivo (ex: `feat/autenticacao-jwt`). O serviço adiciona um timestamp no formato `%Y%m%d%H%M%S` para garantir unicidade.

Por que essa separação de responsabilidades?

- **LLM cria o nome semântico**: o modelo sabe o que está sendo implementado, então deve gerar o nome descritivo
- **Código garante a unicidade**: o timestamp é uma preocupação operacional (evitar conflitos de nome de branch) — não faz sentido o LLM se preocupar com isso

Se o branch `feat/autenticacao-jwt` já existisse (de uma execução anterior), a operação `create_git_ref` do GitHub falharia com um erro 422. O timestamp elimina esse risco ao tornar cada branch essencialmente único.

### 11.3 `github_token` como `Optional[SecretStr]` — fail at feature level

```python
github_token: Optional[SecretStr] = None
github_repo: str = ""
github_branch_base: str = "main"
```

Compare com `groq_api_key: SecretStr` — obrigatório, sem default.

A diferença é intencional. O Groq é uma dependência global — sem ele, nenhum agente funciona. O GitHub é uma dependência do endpoint específico `/desenvolvedor-codigo/`. Tornar `github_token` obrigatório significaria que um desenvolvedor trabalhando apenas no Agente Arquiteto (ou no `chat/`) precisaria configurar credenciais do GitHub para nem usar.

Este é o princípio **fail at the right level**: o sistema só falha no nível em que a dependência é realmente necessária — não antes.

Na prática, quando `github_token` é `None`, o `ServicoGitHub.__init__` vai lançar `AttributeError: 'NoneType' object has no attribute 'get_secret_value'`. Essa exceção propagará pelo FastAPI e retornará um `500 Internal Server Error` — comportamento adequado para um projeto de estudo.

### 11.4 Por que o `ToolMessage` é criado antes da chamada ao GitHub?

```python
tool_message = ToolMessage(
    content="Código recebido. Criando Pull Request no GitHub...",
    tool_call_id=tool_call["id"],
)

# Só depois: chamada ao GitHub (pode ser lenta/falhar)
url_pr = servico_github.criar_pull_request(...)
```

O protocolo de tool calling do LangChain/Groq exige que cada `AIMessage` com `tool_calls` seja seguido de `ToolMessage`(s) correspondentes antes de qualquer nova mensagem. Isso é válido mesmo neste agente onde o `ToolMessage` não é "enviado de volta ao LLM" — ele precisa estar no estado para que a sequência de mensagens seja válida.

Criar o `ToolMessage` antes da chamada ao GitHub garante que, independente do resultado da operação GitHub (sucesso ou falha), o protocolo de mensagens estará correto no estado.

### 11.5 PyGithub síncrono dentro de uma função `async`

O nó `no_criar_pr` é uma `async def`, mas `ServicoGitHub.criar_pull_request()` usa PyGithub, que é **completamente síncrono** — não tem suporte a `async/await`.

```python
async def no_criar_pr(estado: EstadoAgente) -> dict:
    # ...
    servico_github = ServicoGitHub()
    url_pr = servico_github.criar_pull_request(...)  # BLOQUEANTE
```

Em produção, isso seria problemático: chamadas síncronas bloqueantes dentro de funções `async` travam o event loop do Python, impedindo que outras coroutines sejam executadas enquanto o GitHub processa as requisições HTTP. Com 6 arquivos, são pelo menos 8 requisições HTTP síncronas bloqueando o event loop.

A solução correta seria `asyncio.to_thread()`:

```python
url_pr = await asyncio.to_thread(
    servico_github.criar_pull_request,
    nome_branch=nome_branch,
    titulo=dados["titulo_pr"],
    descricao=dados["descricao_pr"],
    arquivos=dados["arquivos"],
)
```

`asyncio.to_thread()` executa a função síncrona em uma thread separada gerenciada pelo thread pool do Python, sem bloquear o event loop. Para um projeto de estudo com um usuário por vez, o comportamento atual é aceitável — mas é uma limitação conhecida a ser endereçada em versões mais maduras do sistema.

Alternativas ao PyGithub que suportam async:
- `httpx` com a GitHub API diretamente
- `gidgethub` — biblioteca assíncrona para GitHub

### 11.6 Agente single-shot vs. multi-turn — quando usar cada um

Este agente foi projetado como **single-shot** (uma única chamada de LLM para gerar todo o código). Isso é possível porque o input já está completo e estruturado (o prompt de engenharia do Agente Arquiteto).

Quando faz sentido usar multi-turn neste contexto?

- Quando o código gerado é tão longo que ultrapassa o limite de tokens da resposta do LLM — você precisaria dividir a geração em partes, com cada parte sendo um turno
- Quando você quer um "revision loop": gerar, verificar (com outro agente ou linter), corrigir, verificar novamente

Por ora, single-shot é a escolha mais simples e adequada para as features típicas que o prompt de engenharia descreve.

### 11.7 Separação do `ServicoGitHub` em arquivo próprio (`github.py`)

A integração com GitHub poderia estar diretamente no `agente.py` (no nó `no_criar_pr`). Optamos por extraí-la para um `github.py` separado por razões de:

- **Testabilidade**: em testes de integração, você pode substituir `ServicoGitHub` por um mock que não faz chamadas reais ao GitHub
- **Single Responsibility Principle (SOLID)**: `agente.py` é responsável pela lógica do grafo LangGraph; `github.py` é responsável pela integração com serviço externo
- **Facilidade de substituição**: se trocarmos PyGithub por `httpx` + GitHub API direta (para suporte a async), mudamos apenas `github.py` sem tocar em `agente.py`

---

## 12. O que vem a seguir

Com os dois primeiros agentes implementados, o pipeline está tomando forma:

```
[Agente Arquiteto de Prompts] → [Agente Desenvolvedor de Código] → [Agente Revisor] (futuro)
```

### Próximas melhorias neste agente

**1. Lidar com o limite de tokens do LLM**

Features complexas podem gerar muitos arquivos com código extenso. O Llama 3.3 70B via Groq tem limite de tokens por resposta. Uma estratégia seria dividir a geração: primeiro gerar a lista de arquivos necessários, depois gerar o conteúdo de cada arquivo em chamadas separadas — padrão chamado **Map-Reduce** em pipelines de agentes.

**2. Geração com contexto do código existente**

Atualmente, o agente não sabe o que já existe no repositório. Se a feature a ser implementada precisa se integrar com código existente (ex: adicionar um endpoint a um router existente), o agente não tem essa informação. Uma solução seria usar a GitHub API para buscar o conteúdo dos arquivos relevantes e incluir no contexto antes da geração — técnica chamada **Retrieval-Augmented Generation (RAG)**.

**3. Chamadas GitHub assíncronas**

Substituir PyGithub por `httpx` com a GitHub REST API direta, usando `async def` em todas as operações. Isso remove o bloqueio do event loop descrito na decisão 11.5.

**4. Testes unitários dos nós**

Cada nó do grafo (`no_gerador_codigo`, `no_criar_pr`) pode ser testado isoladamente mockando o LLM e o `ServicoGitHub`:

```python
async def test_no_criar_pr_com_sucesso():
    estado = EstadoAgente(
        mensagens=[AIMessage(content="", tool_calls=[{...}])],
        prompt_engenharia="...",
        ...
    )
    with mock.patch("app.agents.desenvolvedor_codigo.agente.ServicoGitHub") as mock_github:
        mock_github.return_value.criar_pull_request.return_value = "https://github.com/.../pull/1"
        resultado = await no_criar_pr(estado)
    assert resultado["url_pull_request"] == "https://github.com/.../pull/1"
```

**5. Integração com o Agente Arquiteto no frontend**

Atualmente, o frontend chama os dois agentes separadamente (dois endpoints distintos). Uma evolução natural seria uma "orquestra" no backend: um terceiro endpoint que coordena os dois agentes em sequência, passando o `prompt_engenharia` automaticamente do primeiro para o segundo — sem que o frontend precise fazer duas chamadas separadas.

---

*Documento gerado em: Março de 2026*
*Projeto: Organizer IA — Applied AI Engineering*
