# Organizer IA — Contexto do Projeto

## Objetivo
Projeto de estudo para engenharia de IA aplicada.

## Stack
- Frontend: Angular 19 (standalone components, Signals)
- UI: Angular Material
- Backend: Python + FastAPI
- Agentes: LangChain / LangGraph + Anthropic SDK

## Funcionalidades planejadas
1. Chat com input de texto livre
2. Upload de anexos com suporte aos formatos: `.sql`, `.doc`, `.docx`, `.csv`, `.xls`, `.xlsx`, `.txt`, `.png`, `.jpg`, `.jpeg`

## Convenções
- Português em todo o código (variáveis, métodos, propriedades, interfaces, types, enums) e em nomes de arquivos
- Inglês apenas em nomes de pastas (padrão global de arquitetura)

## Regras de código (geral)
- Utilize Boas práticas de programação como SOLID e Clean Code
- Sempre tipar variáveis — proibido `any` e `var`
- Proibido `console.log`
- Proibido comentários no código
- Proibido `try/catch`
- Sempre foque na clareza e na simplicidade do código
- Sempre foque na manutenibilidade do código

## Regras de código — Python / FastAPI (api/)
- Sempre usar `async def` nas funções de rota
- Proibido retornar `dict` nas rotas — sempre usar schemas Pydantic
- Proibido `print()` — equivalente ao `console.log`
- Proibido `try/except` nas rotas — usar `HTTPException` para erros HTTP e deixar exceções não tratadas propagarem para o handler global
- Proibido hardcode de configurações — usar `pydantic-settings` com `.env`
- Proibido `Any` do módulo `typing` — tipagem estrita obrigatória
- Cada feature deve ter seu próprio `APIRouter` — nunca registrar rotas direto no `aplicacao`
- Usar injeção de dependências via `Depends()` para serviços e dependências compartilhadas
- Schemas de entrada e saída sempre separados (ex: `MensagemEntrada`, `MensagemSaida`)
- Estrutura por feature: cada módulo contém `roteador.py`, `esquemas.py` e `servico.py`