# 01 — Agente Arquiteto de Prompts

> Implementação de um agente conversacional com LangGraph para coleta de requisitos e geração de prompts de engenharia de software.

---

## Índice

1. [Contexto e Objetivo](#1-contexto-e-objetivo)
2. [O que é um Agente de IA?](#2-o-que-é-um-agente-de-ia)
3. [Stack utilizada](#3-stack-utilizada)
4. [Arquitetura do agente com LangGraph](#4-arquitetura-do-agente-com-langgraph)
5. [Tool Calling — o mecanismo de decisão](#5-tool-calling--o-mecanismo-de-decisão)
6. [Prompt Engineering — os system prompts](#6-prompt-engineering--os-system-prompts)
7. [Estrutura de arquivos — backend](#7-estrutura-de-arquivos--backend)
8. [Estrutura de arquivos — frontend](#8-estrutura-de-arquivos--frontend)
9. [Fluxo completo de uma requisição](#9-fluxo-completo-de-uma-requisição)
10. [Decisões de design e boas práticas](#10-decisões-de-design-e-boas-práticas)
11. [O que vem a seguir](#11-o-que-vem-a-seguir)

---

## 1. Contexto e Objetivo

O projeto **Organizer IA** tem como objetivo central criar um sistema onde o usuário descreve uma demanda de software e o sistema gera automaticamente um **prompt de engenharia** pronto para ser enviado a um modelo de linguagem (LLM) para desenvolver o código.

O **Agente Arquiteto de Prompts** é a primeira peça desse pipeline. Ele atua como um especialista em engenharia de requisitos: conversa com o usuário através de um chat, coleta informações estruturadas sobre a demanda, e quando tem dados suficientes, gera um prompt técnico detalhado formatado em Markdown.

A ideia por trás disso é **prompt engineering automatizado**: em vez de o usuário escrever um prompt do zero (tarefa difícil e propensa a resultados genéricos), o agente conduz uma entrevista guiada e produz um prompt de alta qualidade de forma sistemática.

---

## 2. O que é um Agente de IA?

Para um dev full-stack, é útil entender a diferença entre três padrões de uso de LLMs:

### 2.1 LLM simples (stateless)
```
Usuário → Mensagem → LLM → Resposta
```
Você envia uma mensagem e recebe uma resposta. Sem memória, sem decisões. É o que estava implementado antes neste projeto (o `ServicoChat` que simplesmente ecoava a mensagem).

### 2.2 Chain (cadeia)
```
Entrada → [Passo 1 LLM] → [Passo 2 LLM] → [Passo 3 LLM] → Saída
```
Uma sequência **fixa** de chamadas de LLM onde a saída de uma alimenta a próxima. Útil para pipelines determinísticos (ex: traduzir → resumir → classificar). O fluxo não muda com base no conteúdo.

### 2.3 Agente (agent)
```
Entrada → [LLM decide o que fazer] → [Executa ação/tool] → [LLM analisa resultado] → ...
```
O LLM **raciocina** sobre o que fazer a seguir. Ele pode chamar ferramentas (tools), fazer múltiplas iterações, e o fluxo é **dinâmico** — determinado pelo próprio modelo em tempo de execução. É aqui que está o **Agente Arquiteto de Prompts**.

O agente implementado segue o padrão **ReAct** (Reason + Act): o modelo raciocina sobre o estado da conversa e decide se deve continuar coletando informações ou se já tem dados suficientes para agir (gerar o prompt).

---

## 3. Stack utilizada

| Camada | Tecnologia | Versão | Papel |
|--------|-----------|--------|-------|
| **LLM** | Llama 3.3 70B via Groq | llama-3.3-70b-versatile | Modelo de linguagem base |
| **Agent Framework** | LangGraph | ≥ 0.2.0 | Orquestração do agente com grafo de estado |
| **LLM Abstraction** | LangChain + langchain-groq | ≥ 0.3.0 / ≥ 0.2.0 | Abstração sobre a API do Groq |
| **API** | FastAPI | ≥ 0.115.0 | Servidor HTTP assíncrono |
| **Config** | pydantic-settings | ≥ 2.6.0 | Gerenciamento de variáveis de ambiente |
| **Frontend** | Angular 19 | 19.2.0 | SPA com Signals e componentes standalone |
| **HTTP Client** | Angular HttpClient | — | Comunicação com a API |

### Por que Groq e não Anthropic ou Gemini?

Durante o desenvolvimento foram avaliados três provedores:

| Provedor | Resultado | Motivo |
|----------|-----------|--------|
| **Anthropic (Claude)** | Descartado | API paga — sem free tier funcional para estudo |
| **Google Gemini** | Descartado | `limit: 0` na quota free tier — chave criada via GCP Console sem quota provisionada |
| **Groq** | **Adotado** | Free tier real: 14.400 req/dia, sem necessidade de billing |

O Groq é uma infraestrutura de inferência que roda modelos open-source (Llama, Mixtral, DeepSeek) em hardware especializado (LPUs — Language Processing Units). A integração com LangChain é idêntica à de qualquer outro provedor — apenas a classe muda de `ChatAnthropic` para `ChatGroq`. Isso demonstra na prática o valor da abstração do LangChain: **trocar o provedor de LLM é uma mudança de 3 linhas de código**.

### Por que LangGraph e não LangChain puro?

LangChain oferece **Chains** e **Agents**, mas o controle sobre o fluxo é limitado. LangGraph é uma biblioteca construída sobre LangChain que representa o agente como um **grafo dirigido** (nodes + edges). Isso traz:

- **Controle explícito do fluxo**: você define exatamente quais nós existem e quais transições são possíveis
- **Estado persistente e tipado**: o estado do agente é um `TypedDict` com tipos estritos
- **Suporte nativo a ciclos**: diferente de chains lineares, grafos podem ter loops (o agente pode "voltar" para coletar mais dados)
- **Observabilidade**: cada nó é uma unidade isolada, fácil de logar e debugar
- **Escalabilidade para multi-agentes**: o mesmo grafo pode orquestrar múltiplos agentes (o próximo passo deste projeto)

---

## 4. Arquitetura do agente com LangGraph

### 4.1 O grafo

```
START
  │
  ▼
┌─────────────┐
│  no_agente  │  ← LLM conversa com o usuário
└─────────────┘
       │
       ▼
 [roteador_agente]  ← Conditional Edge: o LLM chamou alguma tool?
       │
  ┌────┴────┐
  │         │
  ▼         ▼
(Sim)      (Não)
  │           │
  ▼           ▼
┌───────────────────┐    END
│ no_gerador_prompt │  ← Gera o prompt e o markdown
└───────────────────┘
       │
       ▼
      END
```

Este grafo é compilado **uma vez** na inicialização do módulo Python (nível de módulo) e reutilizado em todas as requisições — sem overhead de reconstrução por request.

### 4.2 O Estado (TypedDict)

```python
class EstadoAgente(TypedDict):
    mensagens: Annotated[list[BaseMessage], add_messages]
    dados_coletados: Optional[dict]
    prompt_engenharia: Optional[str]
    markdown_final: Optional[str]
```

O estado é a "memória de trabalho" do agente durante uma execução. Cada nó recebe o estado atual e retorna um dicionário com as chaves que deseja atualizar.

O campo `mensagens` usa um **reducer** especial: `add_messages`. Em vez de substituir a lista, ele **anexa** novas mensagens à lista existente. Isso é fundamental para manter o histórico de conversa dentro de uma execução do grafo.

> **Analogia para dev full-stack**: o estado é como um `Redux store` — imutável, alterado apenas por ações (os retornos dos nós), e com reducers opcionais para campos específicos.

### 4.3 Os nós (Nodes)

Cada nó é uma função `async def` que recebe o `EstadoAgente` e retorna um `dict` com as atualizações:

**`no_agente`**
```python
async def no_agente(estado: EstadoAgente) -> dict:
    llm = _criar_llm_agente()
    mensagens = [SystemMessage(content=PROMPT_COLETOR)] + estado["mensagens"]
    resposta = await llm.ainvoke(mensagens)
    return {"mensagens": [resposta]}
```
- Injeta o system prompt antes do histórico de mensagens
- Chama o LLM de forma assíncrona (`ainvoke`)
- Retorna apenas a nova mensagem — o reducer `add_messages` cuida de anexá-la ao histórico

**`no_gerador_prompt`**
```python
async def no_gerador_prompt(estado: EstadoAgente) -> dict:
    tool_call = estado["mensagens"][-1].tool_calls[0]
    dados: dict = tool_call["args"]
    # ... gera o prompt via LLM com os dados coletados
    return {
        "mensagens": [tool_message, mensagem_conclusao],
        "dados_coletados": dados,
        "prompt_engenharia": prompt_gerado,
        "markdown_final": markdown,
    }
```
- Extrai os dados estruturados do `tool_call` que o LLM fez
- Faz uma nova chamada de LLM com temperatura baixa (0.3) para geração precisa
- Retorna atualizações para múltiplos campos do estado

### 4.4 O roteador (Conditional Edge)

```python
def roteador_agente(estado: EstadoAgente) -> Literal["no_gerador_prompt", "__end__"]:
    ultima_mensagem = estado["mensagens"][-1]
    if isinstance(ultima_mensagem, AIMessage) and ultima_mensagem.tool_calls:
        return "no_gerador_prompt"
    return END
```

A **conditional edge** é uma função que inspeciona o estado e retorna o nome do próximo nó. O LangGraph executa essa função após `no_agente` para decidir o caminho.

A lógica é simples: se o LLM incluiu `tool_calls` na sua resposta (ou seja, decidiu chamar a tool `solicitar_geracao_prompt`), vai para `no_gerador_prompt`. Caso contrário, encerra o grafo e retorna a resposta conversacional ao usuário.

---

## 5. Tool Calling — o mecanismo de decisão

### 5.1 O que é Tool Calling?

Tool Calling (ou Function Calling) é uma capacidade dos LLMs modernos de **declarar que querem chamar uma função** em vez de (ou além de) responder em texto. O modelo não executa a função — ele apenas emite uma estrutura JSON indicando qual função chamar e com quais argumentos. O código da aplicação é responsável por detectar isso e executar a função.

No contexto deste agente:
- A "tool" é um sinal semântico: `solicitar_geracao_prompt`
- Quando o LLM "chama" essa tool, ele está dizendo: "Coletei tudo que precisava. Aqui estão os dados estruturados."
- O roteador detecta essa chamada e direciona o fluxo para o nó de geração

### 5.2 A Tool e seu Schema Pydantic

```python
class DadosColetados(BaseModel):
    objetivo: str = Field(description="Objetivo da funcionalidade a ser implementada no projeto")
    entradas_saidas: str = Field(description="Descrição das entradas e saídas esperadas da funcionalidade")
    restricoes: str = Field(default="", description="Restrições, validações e regras de negócio específicas")
    exemplos: str = Field(default="", description="Exemplos de uso ou casos concretos de input/output")

@tool(args_schema=DadosColetados)
def solicitar_geracao_prompt(...) -> str:
    """Chame quando tiver coletado informações suficientes..."""
    return "DADOS_COLETADOS"
```

Observe que `tipo_sistema` e `tecnologias` foram **removidos** em relação a uma versão anterior. Como o agente agora opera sempre dentro do contexto do projeto Organizer IA (stack já definida: Angular 19 + FastAPI + LangGraph), coletar essas informações do usuário seria redundante. O agente foca apenas no **o quê** será construído, não no **como** — que já está definido pelas convenções do projeto.

O `args_schema` com Pydantic faz duas coisas críticas:
1. **Gera o JSON Schema** que é enviado ao LLM na requisição, descrevendo os campos e seus tipos
2. **Valida os argumentos** que o LLM retorna, garantindo que a estrutura está correta antes de usarmos

O LLM recebe esse schema e sabe exatamente quais dados deve fornecer quando decidir chamar a tool. As `description` de cada `Field` são especialmente importantes — elas aparecem no schema e guiam o LLM sobre o que preencher em cada campo.

### 5.3 Binding da tool ao LLM

```python
def _criar_llm_agente() -> ChatGroq:
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=configuracoes.groq_api_key,
        temperature=0.7,
    ).bind_tools([solicitar_geracao_prompt])
```

`.bind_tools()` configura o LLM para "conhecer" a tool. Internamente, LangChain serializa o schema Pydantic para o formato esperado pela API do Groq e inclui na requisição. O LLM pode então escolher usar essa tool em qualquer ponto da conversa.

### 5.4 Por que não usar um avaliador separado?

Uma abordagem alternativa seria ter um segundo LLM call para avaliar se "já coletamos dados suficientes". Isso foi **rejeitado** por:

- **Custo**: cada mensagem do usuário dispararia 2 calls de LLM em vez de 1
- **Latência**: dobra o tempo de resposta em todos os turnos
- **Complexidade desnecessária**: o próprio LLM, com um bom system prompt, é capaz de fazer essa avaliação internamente enquanto formula a resposta
- **Elegância**: o tool calling é exatamente o mecanismo para isso — o modelo sinaliza intenção de ação quando está pronto

---

## 6. Prompt Engineering — os system prompts

O comportamento do agente é inteiramente guiado por dois system prompts.

### 6.1 PROMPT_COLETOR

O system prompt do `no_agente`. Define:

- **Persona e contexto**: "Você é o Arquiteto de Prompts do projeto Organizer IA" — com o conteúdo completo do `CLAUDE.md` injetado diretamente no prompt
- **Lista de informações a coletar**: apenas objetivo e entradas/saídas — tipo de sistema e tecnologias são omitidos pois já estão definidos pelo projeto
- **Regras de conduta**: uma pergunta por vez, confirmar ambiguidades, não perguntar sobre stack/tecnologias
- **Critério de acionamento**: "Assim que tiver o objetivo e as entradas/saídas claramente definidos, chame `solicitar_geracao_prompt`"

A chave está em deixar o critério de transição **explícito e mensurável** no prompt. O LLM não adivinha quando parar — ele segue uma regra clara.

O conteúdo do `CLAUDE.md` é lido em tempo de inicialização do módulo e interpolado diretamente na string do prompt via f-string:

```python
_RAIZ_PROJETO = Path(__file__).parent.parent.parent.parent.parent

def _carregar_contexto_projeto() -> str:
    claude_md = _RAIZ_PROJETO / "CLAUDE.md"
    if claude_md.exists():
        return claude_md.read_text(encoding="utf-8")
    return ""

_CONTEXTO_PROJETO = _carregar_contexto_projeto()

PROMPT_COLETOR = f"""Você é o Arquiteto de Prompts do projeto Organizer IA...

## Contexto do Projeto

{_CONTEXTO_PROJETO}
...
"""
```

Isso significa que qualquer atualização no `CLAUDE.md` é refletida automaticamente no comportamento do agente no próximo restart da API — sem nenhuma mudança de código.

### 6.2 PROMPT_GERADOR

O system prompt do `no_gerador_prompt`. Define:

- **Persona e contexto do projeto**: inclui o mesmo `_CONTEXTO_PROJETO` do `CLAUDE.md`
- **Princípios**: especificidade, completude, estrutura, imperativo
- **Estrutura obrigatória** do prompt a ser gerado (7 seções: papel, contexto do projeto, tarefa, requisitos funcionais, interface de dados, estrutura de arquivos esperada, formato de entrega)

Note que a seção "Stack Tecnológica" sumiu da estrutura de saída: ela já está no `_CONTEXTO_PROJETO` injetado no prompt, então não precisa ser repetida. A seção "Estrutura de Arquivos Esperada" foi adicionada — fundamental para que o Agente Desenvolvedor saiba exatamente onde criar cada arquivo.

Usar dois LLMs com papéis distintos (um coletor/conversacional com `temperature=0.7`, outro gerador/técnico com `temperature=0.3`) é uma boa prática em IA aplicada:

- `temperature=0.7` no coletor → respostas mais naturais e variadas na conversa
- `temperature=0.3` no gerador → output mais preciso, consistente e técnico

---

## 7. Estrutura de arquivos — backend

```
api/
└── app/
    ├── core/
    │   └── configuracoes.py          # Pydantic Settings — variáveis de ambiente
    ├── features/
    │   └── engenheiro_prompt/        # Feature isolada (princípio de modularidade)
    │       ├── __init__.py
    │       ├── agente.py             # LangGraph graph — toda a lógica do agente
    │       ├── esquemas.py           # Pydantic models de entrada e saída da API
    │       ├── servico.py            # Camada de serviço — orquestra o agente
    │       └── roteador.py           # FastAPI router — define o endpoint HTTP
    └── main.py                       # Aplicação FastAPI — registra os routers
```

### Por que essa estrutura?

Segue o padrão **Feature Slicing** (ou Vertical Slicing): em vez de organizar por tipo técnico (`controllers/`, `models/`, `services/`), organiza por **domínio de negócio**. Cada feature é auto-contida.

Benefícios práticos:
- Fácil de encontrar tudo relacionado a uma feature
- Fácil de deletar uma feature sem afetar outras
- Fácil de extrair para um microsserviço se necessário

### `configuracoes.py` — SecretStr, segurança e extra="ignore"

```python
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Configuracoes(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # ignora variáveis de ambiente desconhecidas
    )
    groq_api_key: SecretStr  # Sem default → obrigatório → falha explícita na inicialização
```

`SecretStr` é um tipo especial do Pydantic que:
1. **Oculta o valor em logs e representações**: `print(config.groq_api_key)` exibe `**********`
2. **Previne vazamento acidental** em stack traces ou serialização de erros
3. É compatível diretamente com `ChatGroq(api_key=...)` do LangChain

Não ter valor padrão é intencional: se a chave não estiver configurada, a aplicação falha **na inicialização** com um erro claro, em vez de falhar silenciosamente na primeira chamada de LLM.

**Por que `extra="ignore"`?**

Plataformas de deploy como Railway injetam automaticamente variáveis de ambiente padrão como `PORT`. Sem `extra="ignore"`, o pydantic-settings levanta `ValidationError` ao encontrar uma variável que não está mapeada em nenhum campo da classe — derrubando a aplicação na inicialização. Com `extra="ignore"`, variáveis desconhecidas são silenciosamente descartadas.

### `esquemas.py` — Separação de schemas de entrada e saída

```python
class EntradaAgente(BaseModel):
    mensagem: str                          # Mensagem atual do usuário
    historico: list[MensagemHistorico] = [] # Histórico de turnos anteriores

class RespostaAgente(BaseModel):
    resposta: str                          # Texto para exibir no chat
    fase: Literal["coletando", "finalizado", "implementado"]
    markdown_final: Optional[str] = None        # Presente quando o prompt foi gerado
    prompt_engenharia: Optional[str] = None     # O prompt bruto sem formatação markdown
    arquivos_implementados: list[str] = []      # Caminhos dos arquivos escritos em disco
```

O campo `fase` agora tem três estados:
- `"coletando"` — agente ainda está fazendo perguntas ao usuário
- `"finalizado"` — removido do fluxo normal; era um estado intermediário que não existe mais na resposta ao frontend
- `"implementado"` — prompt gerado **e** código já escrito em disco pelo Agente Desenvolvedor

A fase `"finalizado"` não é mais retornada ao frontend — ao gerar o prompt, o servico encadeia automaticamente o Agente Desenvolvedor e só retorna quando a implementação está completa.

`arquivos_implementados` contém os caminhos relativos (a partir da raiz do projeto) dos arquivos criados em disco, ex: `["api/app/features/auth/roteador.py", "api/app/features/auth/esquemas.py"]`. O frontend pode exibir essa lista para o usuário saber o que foi gerado.

Schemas separados de entrada e saída são uma boa prática porque:
- Evitam expor campos internos que não deveriam sair na API
- Permitem validações diferentes para leitura e escrita
- Documentam explicitamente o contrato da API (visível no Swagger em `/docs`)

### `servico.py` — A camada de orquestração

```python
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
        # ... extrai e retorna RespostaAgente
```

O serviço faz a **tradução entre o mundo HTTP e o mundo do agente** e orquestra o pipeline completo:

```python
class ServicoAgenteArquitetoPrompts:
    async def processar_mensagem(self, entrada: EntradaAgente) -> RespostaAgente:
        # 1. Executa o grafo do Engenheiro Prompt
        resultado = await agente_arquiteto_prompts.ainvoke(estado_inicial)

        # 2. Se ainda está coletando, retorna a pergunta ao usuário
        if not markdown_final or not prompt_engenharia:
            return RespostaAgente(resposta=resposta_texto, fase="coletando")

        # 3. Prompt pronto → encadeia automaticamente o Agente Desenvolvedor
        arquivos_implementados = await self._executar_desenvolvedor(prompt_engenharia)

        # 4. Retorna resultado completo com lista de arquivos criados
        return RespostaAgente(
            resposta=f"Implementação concluída! {len(arquivos_implementados)} arquivo(s) criado(s).",
            fase="implementado",
            markdown_final=markdown_final,
            prompt_engenharia=prompt_engenharia,
            arquivos_implementados=arquivos_implementados,
        )

    async def _executar_desenvolvedor(self, prompt_engenharia: str) -> list[str]:
        from app.agents.desenvolvedor_codigo.servico import ServicoDesenvolvedorCodigo
        servico_dev = ServicoDesenvolvedorCodigo()
        resposta = await servico_dev.processar_prompt(
            EntradaDesenvolvedorCodigo(prompt_engenharia=prompt_engenharia)
        )
        return [arquivo.caminho for arquivo in resposta.arquivos_gerados]
```

O import dentro do método (`_executar_desenvolvedor`) é intencional: evita dependência circular no nível de módulo entre `engenheiro_prompt.servico` e `desenvolvedor_codigo.servico`.

**Por que o agente é stateless por request?**

O histórico de conversa é enviado pelo **frontend** em cada requisição. O backend não armazena sessão. Isso é uma escolha deliberada de design (stateless architecture) que:
- Escala horizontalmente sem necessidade de sticky sessions
- Simplifica o backend (sem banco de dados de sessão)
- É adequado para a fase atual do projeto de estudo

A contrapartida é que o frontend é responsável por manter o histórico — o que ele já faz através dos signals Angular.

### `roteador.py` — Injeção de dependência com FastAPI

```python
def obter_servico() -> ServicoAgenteArquitetoPrompts:
    return ServicoAgenteArquitetoPrompts()

@roteador_engenheiro_prompt.post("/", response_model=RespostaAgente)
async def processar_mensagem(
    entrada: EntradaAgente,
    servico: ServicoAgenteArquitetoPrompts = Depends(obter_servico),
) -> RespostaAgente:
    return await servico.processar_mensagem(entrada)
```

`Depends()` é o sistema de DI do FastAPI. Vantagens:
- **Testabilidade**: em testes, pode-se substituir `obter_servico` por um mock
- **Ciclo de vida**: o FastAPI gerencia quando cada dependência é instanciada
- **Declaratividade**: o grafo de dependências é explícito na assinatura da função

---

## 8. Estrutura de arquivos — frontend

```
web/src/app/
├── core/
│   ├── models/
│   │   └── mensagem.model.ts         # Tipos TypeScript — FaseAgente, EntradaAgente, RespostaAgente
│   └── services/
│       └── agente-prompt.service.ts  # HttpClient wrapper para a API
├── features/
│   └── chat/
│       ├── chat.component.ts         # Lógica do componente com Signals
│       ├── chat.component.html       # Template com loading, download, estado finalizado
│       └── chat.component.scss       # Estilos do componente
└── app.config.ts                     # provideHttpClient() adicionado
```

### Angular Signals vs RxJS

O componente usa **Signals** (Angular 19) para estado local reativo:

```typescript
readonly mensagens = signal<Mensagem[]>([]);
readonly carregando = signal<boolean>(false);
readonly conversaFinalizada = signal<boolean>(false);
```

Signals são mais simples que BehaviorSubjects do RxJS para estado local de componente:
- Sem necessidade de `subscribe`/`unsubscribe` para estado local
- Atualizações com `signal.set()` e `signal.update()` são mais legíveis
- Melhor integração com Change Detection do Angular 19 (OnPush por default)

O **RxJS** (`Subscription`) é mantido apenas para a chamada HTTP — onde `Observable` é o padrão natural e o `subscribe` permite cancelamento via `unsubscribe` no `ngOnDestroy`.

### Download de arquivo sem dependência externa

```typescript
baixarMarkdown(conteudo: string): void {
    const blob = new Blob([conteudo], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `prompt-engenharia-${Date.now()}.md`;
    link.click();
    URL.revokeObjectURL(url);
}
```

Técnica padrão para download client-side:
1. Cria um `Blob` com o conteúdo e o MIME type correto
2. Gera uma URL temporária com `URL.createObjectURL`
3. Cria um elemento `<a>` programaticamente, simula um clique e dispara o download
4. Revoga a URL com `URL.revokeObjectURL` para liberar memória — **detalhe importante** frequentemente esquecido

---

## 9. Fluxo completo de uma requisição

### Turno de coleta (conversa normal)

```
Frontend (Angular)
  │  POST /api/v1/engenheiro-prompt/
  │  { mensagem: "quero criar uma API", historico: [] }
  ▼
FastAPI — roteador.py
  │  EntradaAgente validado pelo Pydantic
  ▼
servico.py — processar_mensagem()
  │  Constrói: [HumanMessage("quero criar uma API")]
  │  Estado inicial: { mensagens: [...], dados_coletados: null, ... }
  ▼
LangGraph — agente_arquiteto_prompts.ainvoke(estado)
  │
  ▼
no_agente
  │  LLM recebe: [SystemMessage(PROMPT_COLETOR), HumanMessage("quero criar uma API")]
  │  LLM responde: AIMessage("Ótimo! Que tipo de API você quer criar? REST, GraphQL?...")
  │  Sem tool_calls na resposta
  ▼
roteador_agente → tool_calls? NÃO → END
  ▼
servico.py
  │  ultima_resposta = AIMessage("Ótimo! Que tipo de API...")
  │  fase = "coletando"
  ▼
FastAPI → RespostaAgente { resposta: "Ótimo!...", fase: "coletando", markdown_final: null }
  ▼
Frontend
  │  Adiciona mensagem do assistente ao signal mensagens[]
  │  carregando.set(false)
```

### Turno de geração e implementação (quando o agente tem dados suficientes)

```
Frontend
  │  POST /api/v1/engenheiro-prompt/
  │  {
  │    mensagem: "entrada é um JSON com campos nome e email",
  │    historico: [
  │      { papel: "usuario", conteudo: "quero criar uma feature de cadastro" },
  │      { papel: "assistente", conteudo: "Qual o objetivo dessa feature?" },
  │      ... (turnos anteriores)
  │    ]
  │  }
  ▼
servico.py → Reconstrói histórico completo como LangChain messages
  ▼
no_agente
  │  LLM analisa TODO o histórico + mensagem atual
  │  Avalia: tenho objetivo ✓, entradas/saídas ✓ (stack já é conhecida do projeto)
  │  LLM responde com tool_call:
  │  AIMessage(
  │    content="",
  │    tool_calls=[{
  │      id: "toolu_abc123",
  │      name: "solicitar_geracao_prompt",
  │      args: {
  │        objetivo: "Endpoint de cadastro de usuários com validação de email único",
  │        entradas_saidas: "Entrada: JSON {nome, email}. Saída: usuário criado com id.",
  │        restricoes: "",
  │        exemplos: ""
  │      }
  │    }]
  │  )
  ▼
roteador_agente → tool_calls? SIM → "no_gerador_prompt"
  ▼
no_gerador_prompt
  │  Extrai args do tool_call
  │  Cria ToolMessage (obrigatório pelo protocolo LangChain/Anthropic)
  │  Chama LLM gerador com PROMPT_GERADOR (que inclui _CONTEXTO_PROJETO) + dados em JSON
  │  LLM gera: prompt técnico completo em markdown, já com estrutura de arquivos esperada
  │  _formatar_markdown(): monta documento final
  │  Retorna: { mensagens: [ToolMessage, AIMessage("Prompt gerado. Iniciando implementação...")],
  │             dados_coletados: {...}, prompt_engenharia: "...", markdown_final: "..." }
  ▼
servico.py
  │  markdown_final e prompt_engenharia presentes
  │  → chama _executar_desenvolvedor(prompt_engenharia)
  │      │
  │      ▼
  │   ServicoDesenvolvedorCodigo.processar_prompt(...)
  │      │  (LangGraph do desenvolvedor executa — ver documento 02)
  │      │  Arquivos escritos em disco na raiz do projeto
  │      ▼
  │   retorna lista de caminhos: ["api/app/features/auth/roteador.py", ...]
  ▼
RespostaAgente {
  resposta: "Implementação concluída! 4 arquivo(s) criado(s) no projeto.",
  fase: "implementado",
  markdown_final: "# Prompt...",
  prompt_engenharia: "...",
  arquivos_implementados: ["api/app/features/auth/__init__.py", ...]
}
  ▼
Frontend
  │  Exibe lista de arquivos criados
  │  conversaFinalizada.set(true) → desabilita input, mostra botão "Nova conversa"
  │  Exibe botão "Baixar .md" com o prompt de engenharia gerado
```

---

## 10. Decisões de design e boas práticas

### 10.1 Por que o histórico fica no frontend?

**Design stateless intencional.** O backend não armazena sessão de conversa. A cada request, o frontend envia todo o histórico relevante. Consequências:

- Backend escala horizontalmente sem qualquer sincronização de estado
- Sem necessidade de banco de dados, Redis ou sessão para esse fluxo
- Custo: o payload HTTP cresce com o tamanho da conversa (tradeoff aceitável para conversas curtas de requisitos)

### 10.2 Por que dois LLMs com temperaturas diferentes?

| LLM | Temperature | Papel |
|-----|-------------|-------|
| `_criar_llm_agente()` | 0.7 | Coletor — conversacional, natural, variado |
| `_criar_llm_gerador()` | 0.3 | Gerador — técnico, preciso, consistente |

Temperature controla a "criatividade" do modelo. Para conversação, queremos respostas naturais e não repetitivas (temperatura maior). Para geração técnica, queremos saídas precisas e reproduzíveis (temperatura menor).

### 10.3 Por que `SecretStr` e não `str`?

Além de segurança (mencionada acima), `SecretStr` força o desenvolvedor a acessar o valor via `.get_secret_value()` quando precisar do string puro. LangChain aceita `SecretStr` diretamente, então nunca precisamos expor o valor.

### 10.4 Por que não usar `try/except` nas rotas?

As convenções do projeto proíbem `try/except` nas rotas. Se o LangGraph ou o LLM lançar uma exceção, ela propaga para o handler global do FastAPI que retorna um `500 Internal Server Error` com o formato padrão. Para um projeto de estudo, isso é adequado. Em produção, você adicionaria um handler global customizado.

### 10.5 Por que o `ToolMessage` é obrigatório?

O protocolo de tool calling (Anthropic, OpenAI, Groq) exige que, após um `AIMessage` com `tool_calls`, o histórico de mensagens contenha um `ToolMessage` correspondente (com o mesmo `tool_call_id`) antes de qualquer nova mensagem. Se você não incluir o `ToolMessage`, a API retorna um erro de validação. Ele representa o "resultado" da execução da tool — mesmo que neste caso o resultado seja apenas um sinal interno ("DADOS_COLETADOS").

### 10.6 O grafo é compilado uma vez, não por request

```python
# Nível de módulo — executado uma vez na inicialização
agente_arquiteto_prompts = construir_grafo()
```

Compilar o grafo tem um custo de inicialização (construção do grafo, validação de nós e edges). Fazer isso a cada request seria desperdício. O grafo compilado é thread-safe e pode ser reutilizado concorrentemente.

### 10.7 Compatibilidade com Python 3.9 — `Optional` em vez de `X | None`

O servidor de desenvolvimento roda Python 3.9 (versão bundled do Xcode). A sintaxe de union types com `|` (ex: `str | None`) foi introduzida apenas no Python 3.10. No Python 3.9, ela levanta `TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'` em tempo de execução quando o Pydantic tenta avaliar as anotações.

A solução é usar `Optional[str]` do módulo `typing`, compatível com Python 3.7+:

```python
# Python 3.10+ (não funciona no 3.9)
markdown_final: str | None = None

# Compatível com 3.9+
from typing import Optional
markdown_final: Optional[str] = None
```

> **Nota**: `from __future__ import annotations` não resolve esse problema quando usado com Pydantic v2, pois o Pydantic avalia as anotações em tempo de execução via `get_type_hints()`, que não beneficia do `__future__` da mesma forma.

### 10.8 Auto-scroll com `afterNextRender`

```typescript
private rolarParaFinal(): void {
    afterNextRender(() => {
        const el = this.areaMensagens?.nativeElement;
        if (el) el.scrollTop = el.scrollHeight;
    }, { injector: this.injector });
}
```

O auto-scroll é chamado em dois momentos: ao adicionar a mensagem do usuário e ao receber a resposta do assistente.

O ponto crítico é **quando** executar o scroll. Se chamarmos `scrollTop = scrollHeight` imediatamente após `mensagens.update(...)`, o DOM ainda não foi re-renderizado pelo Angular — a nova mensagem não existe no DOM, então `scrollHeight` não inclui sua altura.

`afterNextRender` é uma API do Angular 19 que agenda um callback para ser executado **após o próximo ciclo de renderização do DOM**. Isso garante que o scroll é calculado com a nova mensagem já presente na tela.

O `injector` é necessário porque `afterNextRender` precisa de contexto de injeção para se registrar no ciclo de vida do Angular — quando chamado fora do construtor (dentro de um método), ele não tem esse contexto automaticamente.

### 10.9 Subscription e cleanup no Angular

```typescript
private subscricaoAtiva: Subscription | null = null;

ngOnDestroy(): void {
    this.subscricaoAtiva?.unsubscribe();
}
```

Gerenciar o ciclo de vida da subscription previne **memory leaks**. Se o componente for destruído enquanto uma requisição HTTP está em andamento, o `unsubscribe` cancela a subscription, evitando que o callback `next` tente atualizar o estado de um componente destruído.

---

## 11. O que vem a seguir

O pipeline de dois agentes está implementado e integrado:

```
Usuário → [Agente Arquiteto de Prompts]
                    │  (encadeamento automático no servico.py)
                    │  prompt_engenharia
                    ▼
         [Agente Desenvolvedor de Código]  ← implementado (ver documento 02)
                    │
                    │  arquivos escritos em disco
                    ▼
         [Agente Revisor de Código]        ← futuro
```

### Melhorias possíveis neste agente

1. **Streaming SSE**: em vez de esperar os dois agentes terminarem (o que pode levar 30-60s), transmitir tokens em tempo real para o frontend com Server-Sent Events — mostrando o progresso da geração do prompt e depois da escrita dos arquivos
2. **Persistência de sessão**: salvar histórico em banco de dados para retomar conversas
3. **Memória entre conversas**: usar embeddings para recuperar contexto de funcionalidades anteriores do projeto
4. **Validação do prompt gerado**: um LLM separado como "crítico" que avalia a qualidade do prompt antes de disparar o Agente Desenvolvedor
5. **Testes**: implementar testes unitários para cada nó do grafo com mocks do LLM

---

*Documento gerado em: Março de 2026*
*Projeto: Organizer IA — Applied AI Engineering*
