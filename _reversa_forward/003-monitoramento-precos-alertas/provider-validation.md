# Validação de configuração do provedor

**Estado: pendente; T032 não concluída.** Atualizado em 2026-09-30 (America/Sao_Paulo).

## Ambiente disponível

- `COINGECKO_DEMO_API_KEY` no processo: ausente.
- Arquivo local `.env`: ausente.
- `TEST_DATABASE_URL`: ausente.
- Nenhuma chave foi solicitada ou lida, conta foi criada, chamada externa foi enviada ou configuração de produção foi alterada.

## Cobertura

Não foi possível verificar três ativos em banco isolado. Nenhum catálogo foi consultado, então não há cobertura real a registrar. Ativos sem mapeamento válido devem continuar identificados como pendentes ou sem cobertura e não podem gerar alertas.

## Consumo projetado

Com ciclos de 300 segundos, 31 dias contínuos representam `31 × 24 × 60 ÷ 5 = 8.928` ciclos. Se todos os ativos couberem em um único lote, esse é o número projetado de chamadas de preço; lotes adicionais, atualização diária de catálogo e tentativas que consomem quota elevam o total. O exemplo `.env.example` limita o contador a 10.000, deixando no máximo 1.072 chamadas adicionais nesse cenário simplificado. A quota, o método de contabilização e a cobertura dos três ativos não foram confirmados no painel do operador.

**Próximo passo de T032:** disponibilizar banco isolado e configurar a chave/janela aprovada pelo operador; validar três IDs sem criar conta nem publicar em produção. Até essa verificação, manter `QUOTE_MODE=unavailable`.

## Verificação em 2026-10-03

`COINGECKO_DEMO_API_KEY`, `.env` e `TEST_DATABASE_URL` continuam ausentes. O Docker Desktop está instalado, mas o daemon local não ficou disponível. Os testes de navegador com API simulada verificaram somente a apresentação dos estados de cobertura; nenhum catálogo real foi consultado. T032 continua aberta.

## Verificação de execução — 2026-10-03

A tentativa de inicializar o Docker Desktop não disponibilizou o daemon. `COINGECKO_DEMO_API_KEY`, `.env` e `TEST_DATABASE_URL` continuam ausentes; nenhum catálogo real, quota do operador ou endpoint CoinGecko foi consultado. A validação de navegador permanece evidência simulada de apresentação e não fecha T032.
