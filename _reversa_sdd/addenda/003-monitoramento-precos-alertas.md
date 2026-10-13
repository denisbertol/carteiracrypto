# Adendo: Monitoramento de preços e alertas

> Identificador: 003-monitoramento-precos-alertas  
> Data: 2026-09-30  
> Cenário: greenfield

---

## Vigência

Vigente desde 2026-09-30.

---

## Resumo da entrega

A feature permite configurar vários alvos de compra e venda por ativo e uma faixa global de proximidade, acompanhar cotações em USD durante uma sessão aberta, registrar avaliações e notificações por ciclo válido e usar a cotação válida mais recente na posição e no rebalanceamento. Não executa operações.

A sincronização é parcial: 25 das 36 ações estão marcadas como concluídas em actions.md. Permanecem abertas T018, T025–T033 e T036. O código e o progresso registram componentes implementados, mas ainda faltam validações de PostgreSQL concorrente, navegador a 360 px, fluxos integrados e múltiplas abas, cobertura real do provedor e a prova de seis ciclos reais. A ausência de TEST_DATABASE_URL e da credencial do provedor foi registrada como pendência, não como aprovação.

---

## Impacto por artefato da extração

| Artefato | Seção | Tipo de impacto | Delta |
|---|---|---|---|
| _reversa_sdd/prd.md | 4. Escopo (in); 9. Critérios de aceite (alto nível) | componente-novo | O escopo de monitoramento agora tem implementação parcial para alvos, cotações, avisos e uso do cache na carteira. A entrega permanece parcial até fechar as ações abertas e registrar as validações. |
| _reversa_sdd/sdd/monitoramento-precos-alertas.md | 6. Requisitos Funcionais; 9. Modelo de Dados; 10. Integrações e Dependências | componente-novo | Há implementação de alvos e configurações (RF-01/02), cálculo decimal (RF-03/04), infraestrutura de ciclos e recuperação (RF-05/08), serviço de notificações e retenção (RF-06/07/11), cliente e mapeamentos do provedor (RF-10). Validação do scheduler e da interface, concorrência PostgreSQL, cobertura real e execução real continuam pendentes. |
| _reversa_sdd/sdd/operacoes-posicao-carteira.md | 6. Requisitos Funcionais; 10. Integrações e Dependências | componente-novo | A posição usa o cache local de cotações com origem e frescor, sem HTTP nas leituras normais; USDT permanece em USD 1. A consistência sob concorrência PostgreSQL continua sem verificação integrada. |
| _reversa_sdd/sdd/alocacao-rebalanceamento.md | 6. Requisitos Funcionais; 10. Integrações e Dependências | componente-novo | O rebalanceamento recebe o mesmo resumo da carteira e mapa de preços do painel (RF-09). O teste de concorrência PostgreSQL para o snapshot continua pendente. |
| _reversa_sdd/sdd/painel-movel-carteira.md | 6. Requisitos Funcionais; 8. Design e Interface; 12. Segurança e Privacidade | componente-novo | A interface contém sessão autenticada, painel agregado, formulários de alvos/configuração/mapeamento, scheduler e central de notificações. A validação real em 360 px, entre abas e dos fluxos de exibição/ACK ainda não foi concluída. |

---

## Regras sob vigilância

Nenhum item W ativo. A feature foi classificada como greenfield e o arquivo de origem não registra regras legadas na watch principal. Consulte [regression-watch.md](../../_reversa_forward/003-monitoramento-precos-alertas/regression-watch.md).

---

## Fontes

- _reversa_forward/003-monitoramento-precos-alertas/requirements.md
- _reversa_forward/003-monitoramento-precos-alertas/actions.md
- _reversa_forward/003-monitoramento-precos-alertas/progress.jsonl
- _reversa_forward/003-monitoramento-precos-alertas/legacy-impact.md
- _reversa_forward/003-monitoramento-precos-alertas/regression-watch.md

## Atualização 2026-10-03

Desde a sincronização de 2026-09-30, foram concluídas T025, T026, T027, T028, T029 e T031. O plano registra agora 31 das 36 ações concluídas. Permanecem abertas T018, T030, T032, T033 e T036; a entrega e a validação integrada continuam parciais.

| Artefato | Seção | Tipo de impacto | Delta novo |
|---|---|---|---|
| _reversa_sdd/sdd/monitoramento-precos-alertas.md | 6. Requisitos Funcionais; 8. Design e Interface; 12. Segurança e Privacidade | componente-novo | Formulários versionados, agendamento conforme horários do servidor, central de notificações com exibição/ACK e sanitização de logs foram implementados. Oito cenários de navegador passaram com API e sessão simuladas; persistência PostgreSQL, autenticação real, provedor e ciclos reais ainda carecem de validação. |
| _reversa_sdd/sdd/painel-movel-carteira.md | 8. Design e Interface | componente-novo | O layout a 360 px exibe frescor, indisponibilidade, fonte, horário e atribuição CoinGecko, com avisos que não bloqueiam os formulários. A verificação em Chrome headless cobriu duas abas e interrupções com API simulada; não equivale a aprovação em sessão real. |

Os testes de navegador passaram em 8 de 8 cenários; os testes de serviço passaram em 5 de 5 cenários de retenção, 6 de 6 de notificações e 3 de 3 de alvos/configuração, com cursores simulados; a sanitização de logs passou em 2 de 2 testes. A validação de PostgreSQL, a sessão Supabase real, a chave do operador e a prova de seis ciclos de cinco minutos permanecem pendentes. Nenhum item W novo foi registrado em regression-watch.md.

Fontes desta atualização: _reversa_forward/003-monitoramento-precos-alertas/actions.md, progress.jsonl, legacy-impact.md, regression-watch.md e validation.md.

## Atualização 2026-10-03 — evidências da rodada de coding

Nenhuma ação foi fechada nesta rodada: o plano permanece em 31 de 36 ações concluídas, com T018, T030, T032, T033 e T036 abertas. A implementação existente foi rechecada; os novos registros distinguem evidência local e validação ainda dependente de ambiente real.

| Artefato | Seção | Tipo de impacto | Delta novo |
|---|---|---|---|
| _reversa_sdd/sdd/monitoramento-precos-alertas.md | 6. Requisitos Funcionais; 9. Modelo de Dados; 10. Integrações e Dependências | componente-novo | A limpeza de histórico e o snapshot autenticado continuam implementados, com 5/5 testes puros de retenção e compilação estática confirmada; o teste PostgreSQL concorrente de T018/T036 segue sem execução porque não há TEST_DATABASE_URL nem daemon Docker disponível. |
| _reversa_sdd/sdd/painel-movel-carteira.md | 8. Design e Interface; 12. Segurança e Privacidade | componente-novo | O Chrome headless passou em 8/8 cenários com API e sessão simuladas, incluindo 360 px, duas abas, suspensão, retomada, notificações e ACK; sessão autenticada real, provedor e ciclos de cinco minutos permanecem pendentes. |

Não foram criados itens W: `regression-watch.md` continua sem regras legadas. O adendo registra a entrega como parcial e não transforma mocks, compilação ou testes unitários em aprovação integrada.

Fontes desta atualização: _reversa_forward/003-monitoramento-precos-alertas/progress.jsonl, validation.md, provider-validation.md, live-validation.md, legacy-impact.md e regression-watch.md.
