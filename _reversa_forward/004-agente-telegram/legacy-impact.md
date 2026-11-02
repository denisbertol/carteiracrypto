# Impacto no Legado / Arquitetura: Agente Telegram

> Identificador: `004-agente-telegram`  
> Data: `2026-11-01`  
> Política de edição: `allowLegacyEdits: true`, `allowedPaths: []` (liberação irrestrita)  
> Feature greenfield, sem legado pré-existente. Âncora: `prd.md` + specs SDD.

## Arquivos Afetados

| Arquivo afetado | Componente | Tipo | Severidade | Justificativa |
|-----------------|------------|------|------------|---------------|
| `migrations/007_telegram_agent.sql` | `banco-de-dados` | delta-de-dados | MEDIUM | Criação das tabelas de contas vinculadas, rascunhos e atualizações aplicadas. |
| `app/config.py` | `configuracao` | regra-nova | LOW | Suporte às variáveis `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_USERS` e `VERBOSE`. |
| `app/services/telegram_intent.py` | `agente-telegram` | componente-novo | LOW | Normalização da intenção em linguagem natural e complementação de rascunho. |
| `app/services/telegram_alarm.py` | `agente-telegram` | componente-novo | LOW | Leitura sob demanda de alarmes (notificações não lidas + sinais Comprar/Vender). |
| `app/services/telegram_draft.py` | `agente-telegram` | componente-novo | LOW | Gerenciamento de rascunhos de operações e idempotência de mensagens. |
| `app/services/telegram_access.py` | `agente-telegram` | componente-novo | MEDIUM | Controle de whitelist e vínculo exclusivo da conta Telegram de Denis. |
| `app/services/telegram_launch.py` | `agente-telegram` | componente-novo | MEDIUM | Encaminhamento atômico de lançamento completo ao Ledger contábil. |
| `app/services/telegram_voice.py` | `agente-telegram` | componente-novo | LOW | Download de áudio com sandboxing em `./temp` e transcrição STT com higiene efêmera. |
| `app/services/telegram_reply.py` | `agente-telegram` | componente-novo | LOW | Redator de mensagens em português claro, conciso e sem vazamento de segredos. |
| `app/services/telegram_poll.py` | `agente-telegram` | componente-novo | MEDIUM | Consumidor único (Single Consumer lock) de long-polling da Telegram Bot API. |
| `app/main.py` | `servidor` | regra-nova | LOW | Inicialização do polling em segundo plano no ciclo de vida (lifespan) da aplicação. |
| `.env.example` | `documentacao` | regra-nova | LOW | Exemplo documentado das variáveis de ambiente do Telegram. |

## Diff Conceitual por Componente

### Agente Telegram (Novo)
- Opera como interface móvel conversacional acoplada à aplicação existente, sem duplicar o motor contábil nem o banco de dados.
- Implementa o padrão Sandeclaw da Aula 4 (Prof. Sandeco): separação estrita entre mensageria (Telegram), raciocínio/intenção (Agent Loop), ferramentas (Ledger/Portfolio/Notifications) e segurança (Whitelist + Sandboxing).

### Banco de Dados (`portfolio_private`)
- Três novas tabelas criadas pela migração 007 (`telegram_accounts`, `telegram_drafts`, `telegram_updates`).
- Nenhuma alteração nas tabelas existentes de operações, posições ou histórico.

### Servidor (`main.py`)
- O polling é executado como tarefa assíncrona desacoplada durante o lifespan da aplicação somente se `TELEGRAM_BOT_TOKEN` estiver preenchido.
- Se o Telegram estiver desligado ou sofrer indisponibilidade de rede, o painel web continua funcionando normalmente.

## Preservadas

Feature greenfield, sem legado pré-existente. Âncora: prd.md + specs SDD.
Todas as regras contábeis do ledger (FIFO ponderado, recálculo atômico, USDT como caixa) permanecem 100% preservadas.

## Modificadas

Nenhuma regra pré-existente foi modificada ou extinta.

