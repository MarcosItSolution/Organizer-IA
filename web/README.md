# Organizer IA

> Assistente inteligente para organização e processamento de demandas via chat — com suporte a múltiplos formatos de arquivo.

---

## Sobre o projeto

O **Organizer IA** é uma aplicação web desenvolvida como projeto de estudo em **Engenharia de IA Aplicada**. O objetivo é construir uma interface moderna de chat onde o usuário pode submeter demandas em texto livre ou através de arquivos anexados, que serão processados por modelos de inteligência artificial.

Este repositório contém o frontend (Angular) e a estrutura reservada para o backend (API), que será desenvolvida nas próximas etapas.

---

## Stack

| Camada | Tecnologia |
|---|---|
| Frontend | Angular 19 (Standalone + Signals) |
| UI | Angular Material |
| Estilo | SCSS + CSS Custom Properties |
| Backend | Python + FastAPI |
| Agentes | LangChain / LangGraph + Anthropic SDK |

---

## Funcionalidades

- Chat com input de texto livre
- Upload de múltiplos formatos de arquivo:
  - Documentos: `.doc`, `.docx`, `.txt`, `.sql`
  - Planilhas: `.csv`, `.xls`, `.xlsx`
  - Imagens: `.png`, `.jpg`, `.jpeg`
- Interface responsiva com tema dark moderno
- Animações e microinterações

---

## Estrutura do repositório

```
Organizer-IA/
├── web/          # Frontend Angular
│   ├── src/
│   │   ├── app/
│   │   │   ├── core/
│   │   │   │   └── models/       # Interfaces e tipos
│   │   │   ├── features/
│   │   │   │   └── chat/         # Componente principal do chat
│   │   │   └── shared/           # Componentes reutilizáveis
│   │   ├── styles.scss            # Tema global
│   │   └── index.html
│   └── angular.json
├── api/          # Backend FastAPI
│   ├── app/
│   │   ├── core/             # Configurações
│   │   ├── features/
│   │   │   └── chat/         # Router, schemas e service do chat
│   │   └── shared/
│   ├── railway.toml          # Configuração de deploy
│   └── requirements.txt
└── CLAUDE.md     # Contexto e convenções do projeto
```

---

## Como rodar localmente

### Pré-requisitos

- Node.js 18+
- npm 9+
- Python 3.12+

### Frontend

```bash
cd Organizer-IA/web
npm install
npx @angular/cli@19 serve
```

Disponível em `http://localhost:4200`.

### Backend

```bash
cd Organizer-IA/api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:aplicacao --reload
```

Disponível em `http://localhost:8000` — docs automáticos em `http://localhost:8000/docs`.

---

## CI/CD

### GitHub Actions (CI)

A cada `push` ou Pull Request na `main`, o workflow `.github/workflows/ci.yml` executa automaticamente:

1. Instala as dependências via `npm ci`
2. Executa o build de produção via `npm run build`

Se o build falhar, o PR fica bloqueado e o status aparece como ❌ diretamente no commit do GitHub.

### Vercel — Frontend (CD)

A **Vercel** monitora a branch `main` e publica o Angular automaticamente a cada push.

| Parâmetro | Valor |
|---|---|
| Root Directory | `web` |
| Build Command | `npm run build` |
| Output Directory | `dist/organizer-ia/browser` |

### Railway — Backend (CD)

O **Railway** monitora a branch `main` e publica o FastAPI automaticamente a cada push, usando o `api/railway.toml` como configuração.

| Parâmetro | Valor |
|---|---|
| Root Directory | `api` |
| Start Command | `uvicorn app.main:aplicacao --host 0.0.0.0 --port $PORT` |

**Variáveis de ambiente obrigatórias no Railway:**

| Variável | Descrição |
|---|---|
| `ORIGENS_PERMITIDAS` | URL do frontend em produção (ex: `["https://organizer-ia.vercel.app"]`) |

O status do deploy (✅ ou ❌) de ambas as plataformas é reportado diretamente no commit do GitHub.

---

## Convenções do projeto

- **Código em português** — variáveis, métodos, interfaces e nomes de arquivos
- **Pastas em inglês** — padrão global de arquitetura
- SOLID e Clean Code
- Tipagem estrita — proibido `any` e `var`

---

## Autor

**Marcos Castro** — [@MarcosItSolution](https://github.com/MarcosItSolution)
