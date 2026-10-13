# Impacto Arquitetural: Operações e posição da carteira

> Identificador: `001-operacoes-posicao-carteira`  
> Data: `2026-09-27`  
> Política de edição: `allowLegacyEdits: true`, `allowedPaths: []` (liberação irrestrita)  
> Contexto: **Feature greenfield, sem legado pré-existente. Âncora: prd.md + specs SDD.**

---

## 1. Mapeamento de arquivos criados por componente

| Arquivo afetado | Componente (`_reversa_sdd/sdd/`) | Tipo | Severidade | Justificativa |
|---|---|---|---|---|
| `pyproject.toml` | operacoes-posicao-carteira.md | `componente-novo` | LOW | Manifesto de dependências e empacotamento do serviço Python |
| `.env.example` | operacoes-posicao-carteira.md | `componente-novo` | LOW | Modelo de variáveis de ambiente para PostgreSQL e Supabase |
| `migrations/001_initial.sql` | operacoes-posicao-carteira.md | `componente-novo` | HIGH | Schema `portfolio_private`, tabelas, índices e políticas de RLS |
| `app/config.py` | operacoes-posicao-carteira.md | `componente-novo` | MEDIUM | Módulo de configuração tipada com Pydantic Settings |
| `app/db.py` | operacoes-posicao-carteira.md | `componente-novo` | HIGH | Conexão psycopg 3, pool de conexões, timeouts e injeção RLS |
| `app/migrate.py` | operacoes-posicao-carteira.md | `componente-novo` | MEDIUM | Runner administrativo para execução de migrações |
| `app/domain/ledger.py` | operacoes-posicao-carteira.md | `componente-novo` | HIGH | Motor contábil puro com Decimal(80), replay e cálculo de preço médio |
| `app/auth.py` | operacoes-posicao-carteira.md | `componente-novo` | HIGH | Validador de JWT Supabase Auth com checagem de `OWNER_USER_ID` |
| `app/services/quotes.py` | monitoramento-precos-alertas.md | `componente-novo` | MEDIUM | Porta QuoteReader com suporte a modo fixture de desenvolvimento |
| `app/services/portfolio.py` | operacoes-posicao-carteira.md | `componente-novo` | HIGH | Orquestrador transacional com lock de linha e idempotência |
| `app/services/exports.py` | operacoes-posicao-carteira.md | `componente-novo` | MEDIUM | Gerador de CSV com higienização contra injeção de fórmulas |
| `app/routes/api.py` | operacoes-posicao-carteira.md | `componente-novo` | HIGH | Endpoints REST `/api/v1` para ativos, operações e projeções |
| `app/routes/exports.py` | operacoes-posicao-carteira.md | `componente-novo` | MEDIUM | Endpoints HTTP para download dos relatórios CSV |
| `app/templates/index.html` | painel-movel-carteira.md | `componente-novo` | MEDIUM | Template Jinja2 com layout responsivo do painel |
| `app/static/style.css` | painel-movel-carteira.md | `componente-novo` | LOW | Estilos CSS modernos com tema dark e glassmorphism |
| `app/main.py` | operacoes-posicao-carteira.md | `componente-novo` | HIGH | Aplicação principal FastAPI, health checks e lifespan |
| `app/logging.py` | operacoes-posicao-carteira.md | `componente-novo` | LOW | Logging estruturado JSON com mascaramento de dados sensíveis |
| `scripts/seed_demo.py` | operacoes-posicao-carteira.md | `componente-novo` | LOW | Script utilitário para carga de dados de teste |
| `Dockerfile` / `.dockerignore` | operacoes-posicao-carteira.md | `componente-novo` | MEDIUM | Containerização enxuta multi-estágio otimizada para Koyeb |
| `tests/**` | operacoes-posicao-carteira.md | `componente-novo` | HIGH | Suíte de testes automatizados com 16 cenários de aceitação |
| `README.md` | operacoes-posicao-carteira.md | `componente-novo` | LOW | Guia de execução local, testes e deploy |

---

## 2. Diff conceitual por componente

### Operações e posição da carteira (`operacoes-posicao-carteira.md`)
Implementado o núcleo contábil completo:
- Motor decimal de alta precisão (`Decimal` de 80 casas) que elimina resíduos de ponto flutuante binário.
- Persistência atômica no PostgreSQL com bloqueio exclusivo (`SELECT FOR UPDATE`) na linha da carteira, garantindo serialização estrita para o usuário único.
- Histórico imutável de operações com replay cronológico (`occurred_at`, `order_index`, `id`).
- Projeção de posição por ativo e consolidação em tabela de projeções para leituras O(1) de alta performance sem sobrecarga de CPU.

### Painel móvel da carteira (`painel-movel-carteira.md`)
- Interface web com Jinja2 e CSS responsivo para visualização no celular (a partir de 360px) com exibição de saldo total em USD, caixa USDT, alocação percentual em caixa, lucro realizado líquido e resultado a mercado não realizado.

### Monitoramento de preços e alertas (`monitoramento-precos-alertas.md`)
- Implementada a porta interna `QuoteReader` com suporte a status `available`, `stale` e `unavailable`, além de modo `fixture` para testes e desenvolvimento local sem acoplamento prévio a APIs externas.

---

## 3. Preservadas
*Nenhuma regra de legado pré-existente a preservar (projeto greenfield).*

---

## 4. Modificadas
*Nenhuma regra de legado pré-existente alterada (projeto greenfield).*
