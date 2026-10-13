# Adendo: Operações e posição da carteira

> Identificador: `001-operacoes-posicao-carteira`  
> Data: `2026-09-27`  
> Cenário: `greenfield`

---

## Vigência

Vigente desde 2026-09-27.

---

## Resumo da entrega

Implementação completa da primeira aplicação e do núcleo contábil do projeto Carteira Crypto:
- Serviço FastAPI com Uvicorn otimizado para container Koyeb (consumo < 128 MB RAM).
- Motor contábil puro com aritmética decimal (`Decimal` de 80 casas) para eliminação de resíduos, cálculo de preço médio ponderado, apuração de ganhos/perdas realizados e validação de saldo não negativo.
- Banco de dados PostgreSQL com schema privado `portfolio_private`, travas de linha exclusivas (`SELECT FOR UPDATE`), suporte a idempotência e isolamento via Row Level Security (RLS) associado ao Supabase Auth.
- Interface web com Jinja2 e CSS responsivo para acompanhamento móvel, além de endpoints REST `/api/v1` e exportação CSV higienizada contra injeção de fórmulas.
- Total de 22 ações concluídas (100% do plano de ação) e 16 testes automatizados aprovados.

---

## Impacto por artefato da extração

| Artefato | Seção | Tipo de impacto | Delta |
|---|---|---|---|
| `_reversa_sdd/prd.md` | 3. Requisitos Funcionais | `componente-novo` | RF-01 a RF-12 implementados no serviço Python FastAPI com banco PostgreSQL. |
| `_reversa_sdd/prd.md` | 4. Requisitos Não Funcionais | `componente-novo` | Restrições técnicas atendidas: container Koyeb, Supabase Auth, PostgreSQL com RLS e latência baixa. |
| `_reversa_sdd/sdd/operacoes-posicao-carteira.md` | Requisitos e Comportamento | `componente-novo` | Motor contábil puro implementado em `app/domain/ledger.py` com liquidação em USDT e preço médio ponderado. |
| `_reversa_sdd/sdd/operacoes-posicao-carteira.md` | Modelo de Dados | `delta-de-dados` | Schema `portfolio_private` e tabelas de ativos, operações, projeções e auditoria criados em `migrations/001_initial.sql`. |
| `_reversa_sdd/sdd/painel-movel-carteira.md` | Interface Móvel | `componente-novo` | Painel web implementado em `app/templates/index.html` e `app/static/style.css` com foco móvel. |
| `_reversa_sdd/sdd/monitoramento-precos-alertas.md` | Interface de Cotações | `delta-de-contrato-externo` | Porta interna `QuoteReader` implementada em `app/services/quotes.py` com modo fixture para desenvolvimento. |

---

## Regras sob vigilância

A entrega foi executada em cenário greenfield. A lista de requisitos funcionais implementados encontra-se registrada para futura vigilância de regressão em:
- [_reversa_forward/001-operacoes-posicao-carteira/regression-watch.md](file:///c:/Users/denis/Projetos/carteira-crypto/_reversa_forward/001-operacoes-posicao-carteira/regression-watch.md) (RF-01 a RF-12)

---

## Fontes

- `_reversa_forward/001-operacoes-posicao-carteira/requirements.md`
- `_reversa_forward/001-operacoes-posicao-carteira/roadmap.md`
- `_reversa_forward/001-operacoes-posicao-carteira/actions.md`
- `_reversa_forward/001-operacoes-posicao-carteira/legacy-impact.md`
- `_reversa_forward/001-operacoes-posicao-carteira/regression-watch.md`
- `_reversa_forward/001-operacoes-posicao-carteira/progress.jsonl`
