# Actions: Monitoramento de preços e alertas

> Identificador: `003-monitoramento-precos-alertas`
> Data: `2026-09-27`
> Roadmap: `_reversa_forward/003-monitoramento-precos-alertas/roadmap.md`

## Resumo

| Métrica | Valor |
|---|---|
| Total de ações | 36 |
| Paralelizáveis (`[//]`) | 6 |
| Maior cadeia de dependência | 17 ações |

Cada descrição inclui a evidência de conclusão esperada. Status indica execução, não aprovação do planejamento. Marcadores de paralelismo identificam tarefas independentes com arquivos distintos; não autorizam delegação. As demais tarefas seguem suas dependências, não necessariamente a ordem numérica das fases. Os testes da fase 2 são escritos antes do núcleo e devem passar ao concluir as tarefas que os implementam.

## Fase 1, Preparação

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|---|---|---|---|---|---|---|
| [//] T001 | Definir configuração do provedor, quota/janela, limites e modo indisponível; produção rejeita fixture e segredos nunca são retornados; documentar variáveis em .env.example (D-01/D-08) | - | [//] | app/config.py | 🟡 | [X] |
| [//] T002 | Criar migração 003 com entidades, índices, FKs por carteira, RLS forçada e grants mínimos de data-delta; aplicação repetida pelo migrador não altera dados anteriores (D-02/D-04/D-07) | - | [//] | migrations/003_price_monitoring.sql | 🟡 | [X] |

## Fase 2, Testes

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|---|---|---|---|---|---|---|
| [//] T003 | Especificar testes decimais de alvo positivo, 0/100%, bordas e repetição/saída/retorno usando relógio controlado; cobrir CA-02/03/04 (D-03) | - | [//] | tests/test_monitoring_domain.py | 🟡 | [X] |
| [//] T004 | Especificar testes HTTP simulados de resposta parcial, timestamp, lote, 429, timeout e ausência de retries; cobrir CA-07/12 (D-01/D-02) | - | [//] | tests/test_coingecko.py | 🟡 | [X] |
| [//] T005 | Especificar regressões que rejeitam test-token, assinatura inválida, issuer incorreto e usuário terceiro; injetar verificador falso somente em testes (D-09/CA-10) | - | [//] | tests/test_auth.py | 🔴 | [X] |
| [//] T006 | Especificar testes de retenção com relógio controlado na fronteira de 30 dias e preservação da última cotação/cadastro; cobrir CA-11 (D-07) | - | [//] | tests/test_monitoring_retention.py | 🟡 | [X] |
| T007 | Preparar testes PostgreSQL isolados para migração, RLS, FKs e duas conexões concorrentes; execução sem banco deve ser reportada como não verificada, nunca aprovada | T002 | - | tests/test_monitoring_db.py | 🟡 | [X] |

## Fase 3, Núcleo

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|---|---|---|---|---|---|---|
| T008 | Corrigir verificador runtime: remover bypass test-token e fallback com chave pública; validar assinatura/issuer/audience/exp/proprietário e passar T005 (D-09) | T005 | - | app/auth.py | 🔴 | [X] |
| T009 | Implementar motor puro de distância/classificação e validação decimal; repetir eventos por ciclo sem confundir igualdade de preço com dado inválido; passar T003 (RF-03/04/06/07) | T003 | - | app/domain/monitoring.py | 🟡 | [X] |
| T010 | Implementar cliente CoinGecko com chave no header, parse Decimal, lotes e timeout total; tratar erros por ativo sem retry cego; passar T004 (RF-10) | T001, T004 | - | app/services/coingecko.py | 🟡 | [X] |
| T011 | Implementar mapeamentos e provider_catalog persistido por 24 h, lease concorrente e orçamento antes do HTTP; testar refresh único, expiração e pending sem quota; preservar external_id (D-02/CA-12/A004) | T002, T010, T013 | - | app/services/price_mappings.py | 🟡 | [X] |
| T012 | Implementar cadastro/versionamento de alvos e settings com idempotência, histórico de mudanças e padrão 10%; conflito mantém versão anterior (RF-01/02/CA-01/02/10) | T002, T009 | - | app/services/price_targets.py | 🟡 | [X] |
| T013 | Implementar reserva persistente de orçamento compartilhada por preços e catálogo; respeitar janela da chave, cooldown e consumo desconhecido conservador; testar corrida entre duas reservas (D-01/D-04) | T001, T002, T007 | - | app/services/provider_budget.py | 🟡 | [X] |
| T014 | Implementar reserva durável de ciclo com next_due_at, lease e deduplicação entre abas; ciclo vencido vira falha sem reexecução retroativa; validar concorrência de T007 (RF-05/08) | T002, T007, T013 | - | app/services/monitoring.py | 🟡 | [X] |
| T015 | Conectar ciclo ao provedor fora da transação; snapshot de alvos/settings/mapeamentos é revalidado antes de persistir resultados, cache e avaliações; testar desativação durante fetch e commit falho (D-04/CA-05/07/08) | T009, T010, T011, T012, T014 | - | app/services/monitoring.py | 🟡 | [X] |
| T016 | Implementar criação única de notificação por avaliação, ACK de exibição/leitura idempotentes e histórico paginado com expiração; separar criado de entregue (D-06/CA-04/11) | T015 | - | app/services/notifications.py | 🟡 | [X] |
| T017 | Evoluir QuoteReader para ler cache por carteira sem HTTP e calcular frescor; USDT continua USD 1, fixture não entra no cache de produção (D-05/D-08/CA-09) | T002, T015 | - | app/services/quotes.py | 🟡 | [X] |
| T018 | Implementar limpeza em lotes de até 1000 com exclusão por referência e lock singleton; preservar última cotação, orçamento, receipts e cadastros; passar T006 e teste de banco (D-07) | T002, T006, T007, T016 | - | app/services/retention.py | 🟡 | [ ] |

## Fase 4, Integração

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|---|---|---|---|---|---|---|
| T019 | Integrar snapshot de cache à posição, alocação e resultados exportados; preservar campos existentes e distinguir completo de atualizado; validar CA-09 sem chamada externa nas leituras | T017 | - | app/services/portfolio.py; app/services/allocation.py; app/routes/exports.py | 🟡 | [X] |
| T020 | Expor rotas de alvos, settings e mappings conforme contrato: Bearer, versões, idempotência, decimais e erros; testar CA-01/02/10/12 | T008, T011, T012 | - | app/routes/monitoring.py | 🟡 | [X] |
| T021 | Expor ciclos, estado, quotes, avaliações, notificações e ACKs; impor autenticação, paginação, expiração e no-store; testar CA-05/06/07/11 | T016, T017, T020 | - | app/routes/monitoring.py | 🟡 | [X] |
| T022 | Registrar routers e ciclo de vida de reconciliação/limpeza; GET / retorna apenas shell sem consulta financeira, falhas não retornam dados privados; testar acesso anônimo (D-07/D-09) | T008, T018, T021, T035, T036 | - | app/main.py | 🔴 | [X] |
| T023 | Implementar login/renovação/logout com tokens em memória e cliente fetch autenticado; sessão expirada limpa dados e interrompe acompanhamento (D-09/CA-10) | T008 | - | app/static/auth.js | 🟡 | [X] |
| T024 | Adaptar template para shell/login e resposta agregada /dashboard, substituindo carteira/alocação juntas; downloads CSV via fetch com Bearer; confirmar que HTML público não contém valores | T019, T022, T023, T036 | - | app/templates/index.html; app/static/portfolio.js | 🔴 | [X] |
| T025 | Adicionar formulários de alvos, limite e mapeamento com mensagens de erro e versão; incluir estados sem alvo e ativo sem cobertura; validar CA-01/02/12 | T020, T024 | - | app/templates/index.html; app/static/targets.js | 🟡 | [X] |
| T026 | Implementar agendamento de 300 s respeitando next_due_at/next_retry_at; testar primeiro pedido blocked sem ciclo, cooldown e suspensão por config_required sem loop; tratar duas abas/offline sem ciclos retroativos (D-03/CA-06/08/A005) | T021, T023 | - | app/static/monitoring.js | 🟡 | [X] |
| T027 | Renderizar central e toasts por notification_id com ACK após exibição, leitura e histórico sem toast retroativo; alvo desativado não publica novos avisos (D-06/CA-04/11) | T025, T026 | - | app/static/monitoring.js; app/templates/index.html | 🟡 | [X] |

As tarefas adicionais abaixo pertencem à integração e preservam os IDs anteriores:

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|---|---|---|---|---|---|---|
| T035 | Implementar reconciliação no startup e a cada 60 s sem requisições, antes da retenção; testar restart, lease vencida, finalização tardia e ausência de HTTP/alertas retroativos (A002/RF-08) | T014, T018 | - | app/services/monitoring_recovery.py; tests/test_monitoring_recovery.py | 🟡 | [X] |
| T036 | Expor /dashboard autenticado com transação REPEATABLE READ e mapa único de preços; testar atualização concorrente entre leituras sem divergência de posição/alocação e CSV consistente individualmente (A001/CA-09) | T008, T019 | - | app/routes/dashboard.py; tests/test_dashboard_snapshot.py | 🟡 | [ ] |

## Fase 5, Polimento

| ID | Descrição | Dependências | Paralelismo | Arquivo alvo | Confidência | Status |
|---|---|---|---|---|---|---|
| T028 | Ajustar interface a 360 px, estados stale/indisponível, fonte/horário e atribuição CoinGecko; alertas não bloqueiam formulários (RF-09/11) | T024, T025, T027 | - | app/static/style.css; app/templates/index.html | 🟡 | [X] |
| T029 | Verificar logs de ciclo/falha e remover exposição de chave, token, estratégia ou saldo desnecessário; produzir teste de sanitização | T015, T021, T022 | - | app/logging.py; tests/test_monitoring_logs.py | 🟡 | [X] |
| T030 | Executar validação integrada de CA-01 a CA-12, browser 360 px, duas abas e regressões 001/002; anexar resultados distinguindo mocks, banco e navegador | T007, T008, T009, T010, T018, T019, T021, T022, T027, T028, T029 | - | _reversa_forward/003-monitoramento-precos-alertas/validation.md | 🟡 | [ ] |
| T031 | Documentar configuração, quota/reset, cobertura, atribuição, retenção, interrupções de navegador e rollback preservando autenticação; exemplos não contêm secrets | T028, T029 | - | README.md | 🟡 | [X] |
| T032 | Verificar chave/configuração do operador e cobertura de três ativos em ambiente isolado disponível; registrar consumo projetado e limitações sem criar conta ou publicar produção | T010, T011, T013, T031 | - | _reversa_forward/003-monitoramento-precos-alertas/provider-validation.md | 🟡 | [ ] |
| T033 | Executar prova real de seis ciclos de 5 minutos com três ativos; registrar coleta/avaliação/exibição, chamadas e comportamento ao fechar; sem credencial/ambiente, registrar pendência e não marcar concluída | T030, T032 | - | _reversa_forward/003-monitoramento-precos-alertas/live-validation.md | 🟡 | [ ] |
| T034 | Registrar arquivos impactados e regras de regressão RF-01 a RF-11, usando evidências de T030/T033; nenhuma lacuna de execução pode ser apresentada como aprovação | T030, T031, T033 | - | _reversa_forward/003-monitoramento-precos-alertas/legacy-impact.md; _reversa_forward/003-monitoramento-precos-alertas/regression-watch.md | 🟡 | [X] |

## Rastreabilidade

| Origem | Ações |
|---|---|
| D-01 / D-02 | T001, T004, T010, T011, T013, T032 |
| D-03 / D-04 | T003, T007, T014, T015, T026 |
| D-05 | T017, T019, T030 |
| D-06 | T016, T021, T027 |
| D-07 | T002, T006, T018, T022 |
| D-08 / D-09 | T001, T005, T008, T017, T022, T023, T024 |
| RF-01 / RF-02 | T012, T020, T025 |
| RF-03 / RF-04 | T003, T009 |
| RF-05 / RF-06 / RF-07 | T014, T015, T016, T026, T027 |
| RF-08 / RF-09 | T015, T017, T019, T021, T028, T029 |
| RF-10 / RF-11 | T010, T011, T013, T016, T018, T027, T032, T033 |

## Pontos para a auditoria antes do coding

- Segurança: D-09 é correção obrigatória, não evidência de acesso já protegido. Conferir cobertura de todos os consumidores do shell/exports.
- O plano menciona snapshot capturado no início, mas data-delta lista apenas settings_revision no ciclo; validar como valores e versões são preservados entre reserva e finalização, inclusive após alteração concorrente.
- Reauditar A001–A005: agregado /dashboard (T036), reconciliação sem cliente (T035), completed_at uniforme, provider_catalog com quota (T011/T013) e blocked antes da reserva (T014/T021/T026).
- Prova real exige chave e banco isolado disponíveis. Preparação não autoriza criação de conta, gasto ou deploy. T032/T033 não são concluídas por simples ausência de ambiente.

## Notas de execução

Nenhuma ação de implementação executada. Antes de escrever código, reler a política vigente de arquivos. O relatório de auditoria é produzido por `/reversa-audit`, não por estas tarefas.

## Histórico de alterações

| Data | Alteração | Autor |
|---|---|---|
| 2026-09-27 | Decomposição inicial em cinco fases, com dependências e rastreabilidade | reversa-to-do |
| 2026-09-27 | Revisão documental A001–A005, preservando IDs e acrescentando T035/T036; reauditoria pendente | revisão autorizada |
