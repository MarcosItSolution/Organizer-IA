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
| Backend | A definir |

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
├── api/          # Backend (em desenvolvimento)
└── CLAUDE.md     # Contexto e convenções do projeto
```

---

## Como rodar localmente

### Pré-requisitos

- Node.js 18+
- npm 9+

### Instalação

```bash
# Clone o repositório
git clone https://github.com/MarcosItSolution/Organizer-IA.git

# Acesse a pasta do frontend
cd Organizer-IA/web

# Instale as dependências
npm install

# Inicie o servidor de desenvolvimento
npx @angular/cli@19 serve
```

A aplicação estará disponível em `http://localhost:4200`.

---

## Convenções do projeto

- **Código em português** — variáveis, métodos, interfaces e nomes de arquivos
- **Pastas em inglês** — padrão global de arquitetura
- SOLID e Clean Code
- Tipagem estrita — proibido `any` e `var`

---

## Autor

**Marcos Castro** — [@MarcosItSolution](https://github.com/MarcosItSolution)
