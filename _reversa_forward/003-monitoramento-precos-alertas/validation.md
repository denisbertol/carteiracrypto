# Validação integrada — monitoramento de preços e alertas

**Estado: parcial, sem aprovação integrada.** Atualizado em 2026-10-03 (America/Sao_Paulo).

Este registro separa evidência anterior de implementação, checagens pendentes e prova real. A lista `progress.jsonl` mantém os resultados por ação; lacunas desta execução não são tratadas como aprovação.

## Evidência disponível

- Ações backend T001–T022 e T035 têm evidências unitárias registradas no histórico. T018 e T036 permanecem `unverified`: os respectivos testes PostgreSQL não foram executados.
- T023 e T024 haviam sido implementadas na retomada anterior. T025–T029 e T031 foram fechadas após testes de navegador com API simulada, revisão do layout em 360 px e dois testes de sanitização de logs.
- Em 2026-10-03, `node --test tests/browser_monitoring.cjs` passou em 8 de 8 cenários no Chrome headless. Foram exercitados alvos, limites 0/100%, cobertura, conflito de versão, `blocked` antes da reserva, cooldown, suspensão, perda de rede, duas abas, toast, ACK, leitura e histórico sem toast retroativo. A captura está em `validation-360.png`.
- Em 2026-10-03, `py -m unittest discover -s tests -p test_monitoring_logs.py -v` passou em 2 de 2 testes. A interface usa `GET /api/v1/dashboard` para obter posição e alocação no mesmo snapshot. Esses testes não substituem uma sessão autenticada real nem o PostgreSQL integrado.
- Em 2026-10-03, os testes de serviço passaram em 5 de 5 cenários de retenção, 6 de 6 de notificações e 3 de 3 de alvos/configuração. Eles usam cursores simulados e não comprovam a execução no PostgreSQL.

## Critérios de aceitação

| Critério | Estado | Lacuna restante |
|---|---|---|
| CA-01 — criar, editar e desativar vários alvos | Evidência anterior de API/serviço e navegador com API simulada | Persistência PostgreSQL integrada ainda não exercitada |
| CA-02 — faixa global de 0% a 100% | Navegador com API simulada validou 0%, 100%, versão e idempotência | Persistência e conflito concorrente no banco ainda não exercitados |
| CA-03 — fórmula decimal da distância | Evidência unitária anterior | Sem fluxo completo pelo navegador nesta retomada |
| CA-04 — repetição, saída e retorno de alertas | Evidência unitária anterior; toast e ACK exercitados com API simulada no Chrome | Sequência de ciclos reais ainda não executada |
| CA-05 — uma cotação por ativo e alvos independentes | Evidência de serviço anterior | Sem ciclo real nesta retomada |
| CA-06 — cadência de 300 s | Scheduler e `next_due_at` exercitados em navegador com temporizadores controlados | Sem seis ciclos reais em intervalos de 300 s |
| CA-07 — falha preserva cotação antiga sem alertar | Evidência de serviço anterior; UI de frescor antigo revisada a 360 px | Sem prova integrada de provedor e banco |
| CA-08 — lacuna ao retomar sem retroatividade | Chrome simulou aba suspensa, rede indisponível e duas abas, inclusive requisição em curso | Sem sessão autenticada real e sem deduplicação de banco nessa execução |
| CA-09 — posição e alocação com o mesmo snapshot | Evidência unitária anterior | Concorrência PostgreSQL de T036 não foi executada |
| CA-10 — autenticação e privacidade | Evidência anterior de API | O fixture de navegador simulou a sessão; login, renovação e logout reais permanecem pendentes |
| CA-11 — histórico de 30 dias, ACK e leitura | Evidência anterior de serviço; central, ACK visual, leitura e ausência de toast retroativo exercitados no Chrome | Limpeza física PostgreSQL e paginação integrada ainda pendentes |
| CA-12 — cobertura explícita por ativo | Navegador simulou estados pendente/válido e erro de versão | Catálogo real não foi consultado com chave do operador |

## Banco e navegador

- `TEST_DATABASE_URL` não está configurada e o Docker Desktop local não iniciou o daemon. Os cenários de concorrência, RLS, limpeza física e snapshot PostgreSQL de T018/T036 continuam sem verificação.
- O Chrome headless executou os cenários de interface com API e sessão simuladas em 360 px, incluindo duas abas, suspensão e retomada. Nenhuma sessão autenticada real foi usada.
- Nenhuma conta foi criada, nenhum segredo foi consultado e nenhuma chamada real ao provedor foi feita.

## Resultado

Não é uma aprovação integrada de CA-01 a CA-12. Banco real, sessão autenticada, provedor configurado e prova real de seis ciclos continuam pendentes; a prova está registrada separadamente em `live-validation.md`.

## Verificação de execução — 2026-10-03

- `node --test tests/browser_monitoring.cjs`, com o Playwright compartilhado e Chrome instalado no host, passou em 8 de 8 cenários. A execução cobriu 360 px, duas abas, suspensão, retomada, notificações, ACK, histórico e cobertura usando API/sessão simuladas.
- Os testes puros de retenção passaram em 5 de 5 casos. As suítes Python que importam o serviço completo não puderam ser carregadas neste runtime porque `fastapi` e `httpx` não estão instalados; essa limitação não converte a evidência anterior em aprovação nova.
- `TEST_DATABASE_URL` continua ausente. O Docker Desktop permanece sem daemon disponível mesmo após tentativa de inicialização; T018 e T036 seguem sem teste PostgreSQL concorrente.
- Nenhuma chave CoinGecko foi lida e nenhuma chamada externa foi feita. T032 e T033 seguem abertas.

## Retomada de coding — 2026-10-03

O Chrome headless foi repetido com o runtime compartilhado e passou novamente em 8 de 8 cenários. Não houve alteração nas condições de ambiente: PostgreSQL, dependências Python do serviço, sessão autenticada real e provedor CoinGecko continuam indisponíveis; as cinco ações abertas não foram marcadas como concluídas.
