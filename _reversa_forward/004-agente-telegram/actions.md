# Actions: Agente de consulta da carteira no Telegram

> Identificador: `004-agente-telegram`
> Data: `2026-11-01`
> Roadmap: `_reversa_forward/004-agente-telegram/roadmap.md`

## Resumo

| Métrica | Valor |
|---------|-------|
| Total de ações | 18 |
| Paralelizáveis (`[//]`) | 13 |
| Maior cadeia de dependência | 7 ações |

Cada ação cabe num turno e tem um arquivo alvo. O marcador `[//]` indica tarefas com arquivos distintos e sem dependência entre si. Status `[X]` significa executada com sucesso.

## Fase 1, Preparação

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| [//] T001 | Criar a migração posterior à 006 com vínculo de uma conta Telegram por carteira, um rascunho de lançamento por conta e o registro da atualização já aplicada; aplicação repetida não altera operação, posição nem notificação (D-05, D-07) | - | [//] | migrations/007_telegram_agent.sql | 🟢 | [X] |
| [//] T002 | Aceitar o token do bot só no servidor, sem devolvê-lo ao navegador nem registrá-lo em log, e tratar ausência do token como agente desligado (D-02, D-07) | - | [//] | app/config.py | 🟢 | [X] |

## Fase 2, Testes

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| [//] T003 | Especificar a intenção estruturada: patrimônio, resultado, lista, saldo, lançamento, alarme e fora de escopo; data ausente não é falta; tipo, ativo, quantidade e preço exigido ausentes são falta (D-03, D-05) | - | [//] | tests/test_telegram_intent.py | 🟢 | [X] |
| [//] T004 | Especificar a verificação de alarme: notificação não lida e sinal Comprar ou Vender entram; Aguardar não entra; a consulta não preenche leitura (D-06) | - | [//] | tests/test_telegram_alarm.py | 🟡 | [X] |
| [//] T005 | Especificar rascunho único por conta, data da mensagem quando a data não vier no texto, descarte ao aceitar ou cancelar, e segunda entrega da mesma atualização sem novo lançamento (D-04, D-05) | - | [//] | tests/test_telegram_draft.py | 🟢 | [X] |
| [//] T006 | Especificar a primeira conta como vínculo e a recusa da conta diferente sem patrimônio, quantidade, lista ou confirmação de lançamento (D-07) | - | [//] | tests/test_telegram_access.py | 🟢 | [X] |

## Fase 3, Núcleo

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| [//] T007 | Implementar a normalização da intenção e passar T003, sem gravar operação (D-03) | T003 | [//] | app/services/telegram_intent.py | 🟢 | [X] |
| [//] T008 | Implementar a leitura de alarme com a regra de sinal do painel e as notificações não lidas, sem marcar leitura, e passar T004 (D-06) | T004 | [//] | app/services/telegram_alarm.py | 🟡 | [X] |
| [//] T009 | Implementar persistência do rascunho e da atualização aplicada sobre a migração T001 e passar T005 (D-04, D-05) | T001, T005 | [//] | app/services/telegram_draft.py | 🟢 | [X] |
| [//] T010 | Implementar o vínculo da primeira conta e a recusa das demais e passar T006 (D-07) | T001, T006 | [//] | app/services/telegram_access.py | 🟢 | [X] |
| [//] T011 | Encaminhar lançamento completo ao registro de operação já existente, com idempotência pela atualização do Telegram; lançamento inválido não altera saldo (D-01, D-04) | T007, T009 | [//] | app/services/telegram_launch.py | 🟢 | [X] |
| [//] T012 | Baixar o áudio do Telegram e transcrever com a leitura já configurada na carteira, devolvendo texto para T007; falha de leitura não grava lançamento (D-03) | T002, T007 | [//] | app/services/telegram_voice.py | 🟢 | [X] |
| [//] T013 | Criar o redator de respostas em português para consulta, pergunta do campo faltante, confirmação, recusa, fora de escopo e falha de leitura, sem incluir segredo (D-07) | - | [//] | app/services/telegram_reply.py | 🟢 | [X] |

## Fase 4, Integração

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T014 | Compor a resposta de patrimônio, resultado, lista, saldo, alarme e lançamento a partir dos serviços já existentes, usando o redator T013 | T007, T008, T010, T011, T013 | - | app/services/telegram_reply.py | 🟢 | [X] |
| T015 | Consumir atualizações com um único consumidor e trava, despachar texto ou voz, e responder uma vez por atualização; não enviar mensagem sem atualização de Denis (D-02) | T002, T008, T010, T011, T012, T014 | - | app/services/telegram_poll.py | 🟡 | [X] |
| T016 | Iniciar o consumidor no ciclo de vida da aplicação somente quando o token existir; falha do Telegram não impede o painel web (D-01, D-02) | T015 | - | app/main.py | 🟢 | [X] |

## Fase 5, Polimento

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|----|-----------|--------------|-------------|--------------|-------------|--------|
| T017 | Documentar o token no exemplo de configuração, com valor vazio e a observação de que a ausência desliga o agente (D-07) | T002 | - | .env.example | 🟢 | [X] |
| T018 | Registrar arquivos tocados e a vigilância das regras de posição, idempotência e notificação não lida | T016 | - | _reversa_forward/004-agente-telegram/regression-watch.md | 🟢 | [X] |

## Rastreabilidade

| Decisão | Ações |
|---------|-------|
| D-01 | T011, T016 |
| D-02 | T002, T015, T016 |
| D-03 | T003, T007, T012 |
| D-04 | T005, T009, T011 |
| D-05 | T001, T003, T005, T009 |
| D-06 | T004, T008 |
| D-07 | T001, T002, T006, T010, T013, T017 |

## Notas de execução

Todas as 18 ações foram executadas com sucesso. A suíte de 19 testes específicos do Telegram foi executada e homologada com 100% de aprovação.

## Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-11-01 | Decomposição inicial em cinco fases | reversa-to-do |
| 2026-11-01 | Execução integral de T001 a T018 no padrão Sandeclaw / SDD | reversa-coding |
