# Prova real de ciclos

**Estado: pendente; T033 não concluída.** Atualizado em 2026-09-30 (America/Sao_Paulo).

A prova exige seis ciclos reais de cinco minutos com três ativos mapeados, banco isolado e chave/configuração válida do operador. O ambiente desta retomada não possui `COINGECKO_DEMO_API_KEY`, `.env` ou `TEST_DATABASE_URL`; nenhum ciclo real foi solicitado ou iniciado.

| Item da prova | Resultado |
|---|---|
| Ciclos previstos | 6, em intervalos de 300 s |
| Ativos mapeados | Não verificado |
| Coleta e avaliação real | Não executada |
| Notificações exibidas e ACK | Não executados |
| Chamadas e quota do provedor | Não medidas |
| Fechamento e retomada do navegador | Não exercitados |

Não há evidência de sucesso com mocks ou código estático que substitua essa prova. T033 permanece aberta até a execução isolada; nenhuma conta ou ambiente de produção deve ser criado para completá-la.

## Verificação em 2026-10-03

A validação de navegador com respostas simuladas cobriu agendamento, notificações e lacunas de cobertura, mas não executou seis ciclos reais. Sem banco isolado e chave do operador, T033 permanece aberta.

## Verificação de execução — 2026-10-03

O Chrome headless passou em 8 de 8 cenários com respostas simuladas, mas a execução não usou sessão autenticada, banco ou provedor reais. Sem `TEST_DATABASE_URL` e `COINGECKO_DEMO_API_KEY`, nenhum dos seis ciclos de cinco minutos foi iniciado; T033 permanece aberta.
