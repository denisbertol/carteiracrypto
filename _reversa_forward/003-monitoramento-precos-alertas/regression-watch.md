# Regression watch — 003-monitoramento-precos-alertas

## Watch principal

Nenhum item. A âncora disponível é greenfield (`prd.md` + specs SDD), sem regras 🟢 extraídas de código anterior para promover a watch de regressão.

| ID | Origem (arquivo, seção) | Regra esperada após mudança | Tipo de verificação | Sinal de violação |
|---|---|---|---|---|
| — | — | Nenhuma regra legada classificada nesta entrega. | — | — |

## Histórico de re-extrações

Vazio. Preencher quando `/reversa` revalidar estas regras no código.

## Arquivadas

Vazio.

## Observações sem peso de regressão

As regras abaixo vêm da spec `_reversa_sdd/sdd/monitoramento-precos-alertas.md`; são registros de implementação planejada, não regras 🟢 antigas:

- **RF-01/RF-02:** endpoints e formulários de alvos/faixa global estão implementados; validação integrada de CA-01/02 ainda pendente.
- **RF-03/RF-04:** domínio decimal tem evidência unitária anterior registrada no progresso.
- **RF-05/RF-08:** ciclos, leases, recuperação e scheduler do navegador estão implementados; cadência, bloqueio, duas abas e retomada ainda não foram validados juntos.
- **RF-06/RF-07/RF-11:** criação de notificações, ACK e retenção têm evidência anterior de serviço; toasts, central paginada e ACK visual permanecem sem prova no navegador.
- **RF-09:** carteira e alocação usam o mesmo resumo no dashboard; concorrência PostgreSQL e visualização móvel permanecem pendentes.
- **RF-10:** mapeamentos e estado de cobertura são apresentados; cobertura real de três ativos ainda não foi verificada.

Reavaliar estas observações numa extração futura antes de promovê-las para o watch principal.

## Atualização de evidências — 2026-10-03

O watch principal continua vazio: esta âncora greenfield ainda não contém regras legadas extraídas. As observações acima recebem a seguinte evidência complementar, sem promover RFs a W-items:

- RF-01/RF-02/RF-10: Chrome com API simulada verificou dois alvos independentes, desativação, limite 0%/100%, mapeamento pendente/válido, conflito de versão e idempotência; provedor e PostgreSQL reais permanecem pendentes.
- RF-05/RF-08: oito cenários de Chrome verificaram timer de 300 s, bloqueio antes da reserva, cooldown, suspensão, rede indisponível e duas abas; ciclos reais de cinco minutos permanecem pendentes.
- RF-06/RF-07/RF-11: toast por notificação, ACK visual, leitura e histórico sem toast retroativo passaram no Chrome com API simulada; limpeza física PostgreSQL permanece pendente.
- RF-09: captura de 360 px mostra frescor desatualizado/indisponível, fonte, horário e atribuição; concorrência PostgreSQL permanece pendente.

A validação integrada de CA-01 a CA-12 ainda não foi aprovada.

## Atualização de evidências — 2026-10-03 (rodada de coding)

O watch principal permanece vazio. Os 8/8 cenários Chrome com API simulada reforçam RF-01/RF-02/RF-05/RF-06/RF-08/RF-09/RF-10, mas não promovem nenhuma observação a regra legada. PostgreSQL, sessão real, provedor e ciclos reais continuam pendentes.

## Retomada de coding — 2026-10-03

Nenhum W-item foi criado. A repetição dos cenários Chrome não altera o watch greenfield nem substitui as validações reais pendentes.
