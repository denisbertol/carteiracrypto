# Contrato externo — CoinGecko Demo

🟡 Base fixa `https://api.coingecko.com/api/v3`. GET /simple/price com ids únicos separados por vírgula, vs_currencies=usd, include_last_updated_at=true, precision=full. Header x-cg-demo-api-key vindo do secret COINGECKO_DEMO_API_KEY; nunca em URL, navegador, logs ou exportação.

Resposta esperada: objeto por ID, contendo usd numérico positivo e last_updated_at Unix. Parse decimal direto do JSON. Ausência de um ID é erro isolado; JSON inválido/401/403/5xx é falha de lote. Timestamp obrigatório; idade máxima de alerta 300 s; futuro >60 s inválido. Cache antigo pode continuar visível, marcado stale, sem gerar alertas.

GET /coins/list fornece IDs para validação. Cache 24 h; uma única atualização coordenada, fora do ciclo quando possível. Mapeamento explícito persiste por ativo; não selecionar pelo primeiro ticker correspondente. USDT contábil não é consultado.

Timeout: conexão 3 s, prazo total 10 s por chamada, resposta limitada a 5 MiB. GET é idempotente semanticamente, mas consome quota: sem retry automático dentro do ciclo. 429 usa Retry-After válido, ou espera mínima de 300 s se ausente; retornar motivo à aplicação. Não substituir preço por zero. Origem e momento real da cotação ficam separados do momento da coleta.

No máximo 515 IDs por chamada e divisão adicional se URL exceder limite operacional de 8 KiB. Projeção de consumo usa número efetivo de lotes, antes da ativação. Um lote em 31 dias contínuos: 8928 chamadas; mais chamadas de catálogo/testes/falhas. Budget persistente bloqueia chamadas acima do limite configurado e informa indisponibilidade, sem mudar frequência prometida. Janela de reset deve corresponder à conta, não ser presumida pelo calendário local.

Documentação: [preços Demo](https://docs.coingecko.com/demo/reference/simple-price), [autenticação](https://docs.coingecko.com/demo/reference/authentication), [catálogo](https://docs.coingecko.com/demo/reference/coins-list), [plano e atribuição](https://www.coingecko.com/en/api/pricing). Parâmetros e quota verificados documentalmente em 2026-09-27; chave e ativos reais ainda não testados.
