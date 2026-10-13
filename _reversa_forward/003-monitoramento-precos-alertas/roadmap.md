# Roadmap: Monitoramento de preços e alertas

> Identificador: `003-monitoramento-precos-alertas`
> Data: 2026-09-27
> Requirements: `_reversa_forward/003-monitoramento-precos-alertas/requirements.md`
> 🟢 Confirmado; 🟡 proposta técnica; 🔴 impedimento identificado.

## 1. Resumo da abordagem

🟡 Evoluir o serviço existente com integração CoinGecko Demo, cache persistido de cotações, cadastro de alvos e motor decimal de proximidade. O navegador autenticado solicita ciclos a cada 300 segundos; o servidor coordena ciclos entre abas e impede consultas duplicadas. Leituras de carteira e alocação passam a consumir o cache, sem chamar o provedor. Avaliações e notificações persistem por 30 dias. A entrega de alerta só é confirmada após reconhecimento de exibição pelo navegador. Corrigir os caminhos de autenticação incompatíveis com a privacidade antes de habilitar o monitoramento.

## 2. Princípios aplicados

Não existe `.reversa/principles.md`. Hooks before-plan e after-plan vazios. A política atual permite edições irrestritas (`allowLegacyEdits=true`, lista vazia); este turno cria somente documentação Reversa.

| Restrição | Aplicação | Estado |
|---|---|---|
| Uso pessoal e aplicação leve | Mesmo processo, HTTP em lote, nenhuma consulta de mercado sem pedido autenticado | respeita |
| 5 minutos e API gratuita | Cadência 300 s com quota contabilizada e indisponibilidade explícita | respeita sob condições documentadas |
| Histórico por 30 dias | Filtro de expiração imediato e limpeza física em lotes | respeita |
| Dados apenas na sessão autenticada | Página pública e tokens de teste atuais violam a intenção dos requisitos | 🔴 corrigir antes da entrega |

## 3. Decisões técnicas

| ID | Decisão | Justificativa | Alternativa descartada | Confidência |
|---|---|---|---|---|
| D-01 | CoinGecko Demo com chave apenas no servidor e atribuição na tela | Preço USD, múltiplos IDs por chamada, quota mensal compatível com um lote | Preços de uma corretora não cobrem necessariamente o catálogo | 🟡 |
| D-02 | Mapeamento explícito ativo → ID CoinGecko | Símbolos podem ser ambíguos; preservar external_id existente | Adivinhar moeda pelo ticker | 🟡 |
| D-03 | Primeiro ciclo ao abrir, seguintes após 300 s; servidor mantém next_due_at | Evitar consumo extra ao recarregar ou abrir outra aba | Um cron de preços permanente | 🟡 |
| D-04 | Reserva de ciclo em transação curta e chamada HTTP fora da transação | Não segurar o pool durante rede externa | HTTP dentro de get_portfolio_summary | 🟡 |
| D-05 | QuoteReader lê cache por carteira; snapshot compartilhado por posição e alocação | Consistência e nenhuma chamada extra para exportar ou consultar | Cada consumidor consultar preços | 🟡 |
| D-06 | Histórico de notificações com created/displayed/read separados | Resposta HTTP não prova exibição | Considerar criação como entrega | 🟡 |
| D-07 | Retenção lógica de 30 dias e limpeza física na inicialização e horária enquanto processo estiver executando | Pequeno trabalho local sem consulta externa; remove expirados após restart | Manter dados indefinidamente quando aplicativo fecha | 🟡 |
| D-08 | Fixture somente com injeção de dependência em teste ou modo de desenvolvimento explícito | Evitar preço fictício em produção | Fixture por padrão em produção | 🟡 |
| D-09 | Remover bypass test-token do verificador runtime; página inicial só entrega shell público | Necessário para RF-01/08/11 privados | Reutilizar falhas atuais | 🔴 |

## 4. Premissas

Não há dúvidas de produto aceitas como premissas. Condições técnicas ainda não comprovadas em ambiente real:

- A chave Demo será configurada no deploy, sem ser solicitada no chat. Sua quota será confirmada no painel do provedor; nenhuma conta foi criada neste turno.
- Cobertura universal não é prometida: todos os ativos cadastrados entram na verificação; ativos não suportados ou ambíguos ficam indisponíveis. Catálogo real não foi consultado em banco.
- Até 515 IDs cabem no lote documentado, sujeito também ao tamanho da URL. Um lote a cada 5 minutos durante 31 dias soma 8.928 chamadas; catálogo e falhas também consomem orçamento. Múltiplos lotes aumentam o consumo e exigem revalidar viabilidade antes de habilitar, sem reduzir a cadência silenciosamente.
- Browser suspenso, aba congelada, dispositivo bloqueado, rede ou sessão expirada interrompem a cobertura. Ao retornar, informar lacuna e retomar sem alertas retroativos. Aplicação aberta não garante execução do navegador em segundo plano.
- Nova para o ciclo significa resposta coletada com sucesso nesse ciclo e timestamp válido com idade até 300 s; preço pode ser igual ao anterior. Último valor de cache isoladamente nunca produz alerta. Timestamp futuro acima de 60 s ou ausente invalida o dado.

## 5. Delta arquitetural

Não existem architecture.md, c4-context.md, state-machines.md, dependencies.md ou code-analysis.md. Adendos 001/002 estão vigentes; discrepâncias observadas no código são listadas em investigation.md.

| Componente | Fonte SDD | Delta |
|---|---|---|
| Monitoramento de preços e alertas | `_reversa_sdd/sdd/monitoramento-precos-alertas.md` | Adicionar serviço de ciclos, domínio, cache, alvos, central e endpoints |
| Operações e posição da carteira | `_reversa_sdd/addenda/001-operacoes-posicao-carteira.md#impacto-por-artefato-da-extração` | Substituir origem das cotações, mantendo cálculo contábil |
| Alocação e rebalanceamento | `_reversa_sdd/addenda/002-alocacao-rebalanceamento.md#resumo-da-entrega` | Consumir mesmo snapshot e mostrar desatualização |
| Painel móvel da carteira | `_reversa_sdd/sdd/painel-movel-carteira.md` | Acrescentar login, alvos, ciclo, cobertura e notificações |

Modificar: app/auth.py, app/config.py, app/main.py, app/services/quotes.py, app/services/portfolio.py, app/services/allocation.py, app/templates/index.html, app/static/style.css, rotas de leitura/exportação afetadas, .env.example, README.md e testes existentes afetados.
Adicionar: migrations/003_price_monitoring.sql, app/domain/monitoring.py, app/services/monitoring.py, app/services/coingecko.py, app/services/retention.py, app/routes/monitoring.py, app/static/auth.js, app/static/monitoring.js, testes de domínio, provedor, ciclos, autenticação web e retenção. Código ainda não alterado.

## 6. Delta no modelo de dados

Adicionar mapeamentos, configurações, alvos versionados, cache atual, ciclos, avaliações, notificações e orçamento de chamadas. Nenhuma mudança nas operações ou percentuais de alocação. Detalhes em data-delta.md.

## 7. Delta de contratos externos

| Contrato | Tipo | Detalhe |
|---|---|---|
| Alvos, ciclos, cache e notificações | HTTP autenticado | interfaces/http.md |
| CoinGecko Demo | HTTPS externo | interfaces/coingecko.md |

Manter endpoints das Features 001/002. Adicionar quote_snapshot_at e freshness às respostas quando necessário; clientes atuais continuam recebendo campos existentes. Cotações obsoletas podem compor valores indicativos, sempre marcados como tal, sem disparar alertas. Complete não equivale a fresh.

## 8. Plano de migração

1. Auditar os impedimentos de segurança e a compatibilidade de cache; decompor correções necessárias em tarefas explícitas antes do coding.
2. Aplicar migração aditiva em banco de teste com controle existente; configurar RLS forçada, grants mínimos e FKs por carteira. Não executar migração remota neste plano.
3. Inicializar configuração com 10%, ciclo 300 s e retenção 30 dias; mapeamentos existentes ficam pendentes até validar ID; não copiar preços fixture para cache real.
4. Implementar motor e adapter com relógio/HTTP controláveis; conectar cache e endpoints após autenticação corrigida.
5. Ativar interface autenticada, callbacks de exibição, coordenação entre abas e limpeza.
6. Testar regressões e prova real com chave/configuração do operador. Só então habilitar QUOTE_MODE=coingecko. Sem chave, modo indisponível explícito.
7. Rollback: desabilitar monitoramento; manter tabelas e histórico. Usar release compatível com as correções de autenticação, nunca reintroduzir bypass. Não apagar operações nem baixar schema automaticamente.

## 9. Riscos e mitigações

| Risco | Impacto | Mitigação |
|---|---|---|
| Tokens de teste e página pública existentes | alto | Auditoria prioritária, testes negativos e bloqueio da entrega até corrigir |
| Quota/identidade do ativo | alto | Mapeamento explícito, chamada em lote, contador persistido e erro por ativo |
| Aba suspensa | alto | Detecção de gap, mensagem e retomada; nenhuma promessa de segundo plano |
| Duas abas ou restart durante fetch | médio | Reserva durável e lease; uma avaliação por ciclo/alvo, sem retry cego |
| Confundir alerta criado com entregue | alto | ACK de exibição separado, idempotente |
| Crescimento histórico | médio | Índice por data, paginação e limpeza em lotes; 30 dias a 5 min geram até 8.640 avaliações por alvo |
| Alteração de alvo durante consulta | médio | Snapshot revisionado e revalidação antes de publicar notificações |

## 10. Critério de pronto

- [ ] Ações futuras concluídas; cross-check sem CRITICAL/HIGH; regression-watch gerado.
- [ ] CA-01 a CA-12 e regressões contábeis/alocação aprovados.
- [ ] Testar 0/100%, bordas, preço zero/inválido, resposta parcial, quota, timeout, cache antigo, duas abas, retomada, revogação do alvo e ACK repetido.
- [ ] GET / sem dados privados, tokens de teste rejeitados no runtime e JWT válido de terceiro negado.
- [ ] Teste PostgreSQL real comprova unicidade, RLS, reserva concorrente e limpeza sem remover cadastro ou última cotação.
- [ ] Testes com relógio avançado cobrem 30 dias sem esperar tempo real; navegador em 360 px comprova visibilidade e reautenticação.
- [ ] Prova com 3 ativos suportados e pelo menos 6 ciclos reais, registrando latência, consumo e limitações; nenhum sucesso alegado com mocks apenas.
- [ ] Nenhuma chamada de mercado gerada por leitura de posição/alocação ou por aplicativo fechado.

## 11. Histórico de alterações

### Revisão após auditoria A001–A005

- D-05: a interface consome GET /dashboard com posição, alocação e mapa de preços na mesma transação read-only REPEATABLE READ. Respostas independentes e CSVs têm consistência individual; não compartilham necessariamente o instante do painel. T036 cobre atualização concorrente do cache entre leituras.
- D-04/D-07: reconciliar leases de 60 s no startup e a cada 60 s, antes da retenção e sem depender de novas requisições. A tarefa local não consulta mercado; marca ciclos interrompidos como failed com completed_at e bloqueia commits tardios. T035 testa recuperação sem navegador. Processo parado recupera no próximo startup.
- A003: completed_at é o nome único do término no banco e no HTTP.
- D-02: provider_catalog persiste catálogo por 24 h e coordena refresh por lease; T011 depende de T013, reservando quota antes da rede. Cache expirado não valida novos IDs; concorrência mantém pending. Detalhes em data-delta.md.
- D-03: bloqueio antes de reservar ciclo retorna blocked, cycle_id=null e next_retry_at; falta de configuração suspende repetição automática. T014/T021 devem testar primeira solicitação sem ciclo anterior, zero HTTP e zero inserções; T026 testa espera sem loop. 429 recebido após reserva encerra o ciclo persistido conforme seus resultados.

Estas revisões são propostas de implementação e não comprovam execução. O relatório audit/cross-check.md conserva os achados originais até nova auditoria.

| Data | Alteração | Autor |
|---|---|---|
| 2026-09-27 | Plano e pesquisa de quota; impedimentos de autenticação encaminhados à auditoria | reversa-plan |
