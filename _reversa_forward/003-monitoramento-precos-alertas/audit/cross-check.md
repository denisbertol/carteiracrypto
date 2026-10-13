# Cross-check: Monitoramento de preços e alertas

> Feature: `003-monitoramento-precos-alertas`
> Data: 2026-09-27 — segunda auditoria, após revisão A001–A005.
> Escopo: consistência documental; não certifica implementação, segurança operacional ou deploy.

Artefatos: [requirements.md](../requirements.md), [roadmap.md](../roadmap.md), [actions.md](../actions.md). Complementos: data-delta.md, interfaces/http.md, interfaces/coingecko.md, investigation.md, onboarding.md e adendos vigentes 001/002. Hooks before-audit e after-audit vazios.

## Resumo

| Severidade | Achados abertos |
|---|---:|
| CRITICAL | 0 |
| HIGH | 0 |
| MEDIUM | 1 |
| LOW | 0 |

**Veredito: planejamento sem impedimentos CRITICAL/HIGH; pode seguir para coding, com ressalva documental A006.** Os cinco achados originais foram resolvidos no desenho. Isso não significa que suas soluções estejam implementadas ou testadas.

## Findings abertos

| ID | Severidade | Eixo | Descrição | Onde está |
|---|---|---|---|---|
| A006 | MEDIUM | Consistência | O roteiro ainda exige carteira, alocação e CSV com o mesmo snapshot. O contrato revisado garante snapshot comum apenas na resposta agregada; CSVs independentes têm consistência própria e podem diferir do painel. O roteiro pode reprovar indevidamente uma implementação correta. | onboarding.md passo 8 versus interfaces/http.md seção Consistência do painel, data-delta.md e actions.md T036 |

Direção para A006: alinhar o passo 8 do roteiro ao contrato, validando igualdade entre os blocos do painel e consistência interna de cada CSV. Quando for necessária comparação exata entre downloads, usar dados congelados no teste. Não acrescentar promessa de snapshot recuperável entre requisições. Este relatório não modifica o roteiro.

## Reavaliação dos achados originais

| ID | Severidade anterior | Resultado | Evidência documental |
|---|---|---|---|
| A001 | HIGH | Resolvido no planejamento | GET /dashboard em uma transação read-only REPEATABLE READ e mapa único; atualização conjunta da interface em T024, teste concorrente em T036; escopo de CSV explícito no HTTP e modelo. Ressalva residual do roteiro registrada separadamente em A006. |
| A002 | HIGH | Resolvido no planejamento | Reconciliação no startup e a cada 60 s sem cliente, antes da retenção; token/lease impedem commits tardios; T035 e integração T022, sem HTTP nem alertas retroativos. |
| A003 | MEDIUM | Resolvido no planejamento | GET do ciclo e modelo usam completed_at. |
| A004 | MEDIUM | Resolvido no planejamento | provider_catalog persistido com validade, lease e token; refresh autenticado, quota antes da rede, pending para concorrentes; T011 depende de T013. |
| A005 | MEDIUM | Resolvido no planejamento | HTTP 429 blocked anterior à reserva com cycle_id=null e next_retry_at; configuração inválida retorna 503 e suspende tentativas; contrato distingue falha posterior à reserva. Roadmap atribui testes a T014/T021 e T026 cobre o cliente. |

## Verificações aprovadas

### Cobertura

- RF-01/02: D-02/D-04, T012/T020/T025; RF-03/04: motor decimal T003/T009.
- RF-05/06/07: D-03/D-04/D-06 e T014–T016/T026/T027.
- RF-08/09: persistência, apresentação e recuperação em T015/T017/T019/T021/T028/T029/T035/T036.
- RF-10/11: provedor, cobertura e retenção em T010/T011/T013/T016/T018/T027/T032/T033.
- CA-01 a CA-12 têm ações de validação e consolidação em T030. D-01 a D-09 possuem ações correspondentes.
- Agregado autenticado e reconciliação têm dependências transitivas na validação integrada via T022. Não precisam ser repetidos como dependências diretas de T030.
- Contratos HTTP e CoinGecko aparecem no roadmap; o agregado está detalhado na revisão de D-05.

### Consistência e grafo de tarefas

- 36 IDs únicos T001–T036, todos abertos; nenhuma tarefa foi marcada como executada.
- Dependências existentes, grafo sem ciclos; maior cadeia de 17 tarefas, conforme cálculo e resumo.
- Seis tarefas paralelizáveis sem dependências entre si ou arquivo alvo compartilhado. Essa marcação não autoriza delegação.
- Referência a T013 em T011 é válida: ordem de execução segue dependências, não numeração.
- Cadência 300 s, proximidade inicial 10%, faixa inclusiva, alertas repetidos e retenção de 30 dias preservados.
- Manutenção local de leases não consulta preços e não cria ciclos de mercado com aplicativo fechado.
- Bloqueio anterior à reserva não é ciclo iniciado; falha do provedor após reserva permanece auditável em ciclo durável.

### Coerência com contexto existente

- domain.md e architecture.md não existem; não foi alegada comparação com esses documentos. Adendos 001/002 são as referências disponíveis.
- Desenho preserva contabilidade decimal, USDT a USD 1, percentuais de alocação e contratos existentes.
- Correções de autenticação já planejadas em D-09/T005/T008/T022/T024 continuam obrigatórias. A auditoria documental não as considera corrigidas.
- Snapshot de configurações pode permanecer em memória durante a execução, com revalidação de versões e descarte após perda da lease; ciclo interrompido não será retomado.

## Limites e integridade

Nenhum código, banco ou API externa foi executado nesta reauditoria. Quota/cobertura do provedor não foram novamente verificadas na internet; avaliou-se a coerência dos contratos locais. T032/T033 continuam exigindo evidência real, sem aprovação por ausência de ambiente.

Nenhum artefato analisado foi alterado. Única saída persistida: este relatório, substituído atomicamente. Hashes SHA-256 dos três documentos auditados:

| Artefato | SHA-256 |
|---|---|
| requirements.md | 6A0F8BCF3845FCD58214BA7FAB5F740967570C6B4D62C795D403D34D683A4840 |
| roadmap.md | 37CB786C5C9AB7C1CEB16737FB56AF7AAE6028809A91557C850A4C1B246697BC |
| actions.md | 2730CB1C720F7B99DD37274319DF1BB9A3E46FA3B462231F496F55800E05540A |

## Próximo passo

Seguir para `/reversa-coding`, observando A006 ao preparar a validação e alinhando o roteiro ao contrato vigente. Não há necessidade de nova decisão de produto para esse ajuste. Nenhum teste ou entrega deve ser considerado aprovado apenas por este relatório.
