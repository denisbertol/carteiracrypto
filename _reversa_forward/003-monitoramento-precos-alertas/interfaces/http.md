# Contrato HTTP — Monitoramento

🟡 Base /api/v1. Todos os endpoints abaixo exigem Bearer validado e sub=OWNER_USER_ID. RLS com identidade da requisição; nunca inferir autorização por OWNER_USER_ID apenas. Decimais em strings e horários ISO 8601 UTC. Respostas privadas no-store; sem dados financeiros no shell GET /.

| Método e rota | Entrada | Saída |
|---|---|---|
| GET /price-targets | cursor/limit até 100 | items, next_cursor |
| POST /price-targets | asset_id, kind buy/sell, price_usd, active, orientation opcional | 201 target com id e version |
| PATCH /price-targets/{id} | preço/tipo/active/orientation; If-Match da versão | 200 versão nova; asset_id imutável |
| GET /monitoring/settings | — | proximity_percent, interval_seconds=300, retention_days=30, version |
| PATCH /monitoring/settings | proximity_percent; If-Match | 200 nova versão |
| GET /monitoring/mappings | — | mapeamentos e cobertura por ativo |
| PUT /monitoring/mappings/{asset_id} | provider_coin_id e If-Match (0 para criação) | estado pending; validado via catálogo cacheado, sem guessing |
| POST /monitoring/cycles | client_request_id UUID | 200 ciclo concluído reutilizado, 201 ciclo executado ou 202 ciclo em andamento, next_due_at |
| GET /monitoring/cycles/{id} | — | status, started_at, completed_at, erros seguros |
| GET /dashboard | — | portfolio, allocation, quotes, computed_at, portfolio_revision, freshness; snapshot único conforme abaixo |
| GET /monitoring/quotes | — | lista do cache com source, quoted_at, fetched_at, freshness e erro de cobertura |
| GET /monitoring/evaluations | cursor/limit, target_id opcional | histórico dentro de 30 dias |
| GET /notifications | cursor/limit, cycle_id opcional | snapshots e created/displayed/read, apenas dentro de 30 dias |
| POST /notifications/{id}/displayed | sem corpo | timestamp de primeira confirmação, idempotente |
| POST /notifications/{id}/read | sem corpo | timestamp de primeira leitura, idempotente |

Limites: preço >0 finito até 18 casas/18 dígitos inteiros; proximity 0..100 com até 2 casas; orientação 1000 caracteres. Corpo até 64 KiB. Alvo zero/negativo, NaN, porcentagem inválida ou ativo alheio são rejeitados. PATCH/POST de cadastro usam Idempotency-Key UUID e hash canônico; mesma chave/conteúdo retorna resposta anterior, divergência 409. ACK é idempotente por recurso. Ciclos são deduplicados pelo estado persistido da carteira; recarregar não força nova consulta.

Erros: 401 sem sessão; 403 terceiro; 404 entidade ausente; 409 versão/chave em conflito; 422 campos inválidos; 428 If-Match ausente; 503 banco indisponível. Falhas do provedor são resultados de ciclo failed/partial com error_code, sem contabilizar alerta exibido. Não devolver stack trace ou credenciais.

Cliente programa solicitação pelo next_due_at. Se outra aba já executou ciclo, reutiliza resultado. Toast uma vez por notification_id por documento ativo; abas podem mostrar o mesmo evento, mas não criam avaliações adicionais. GET de histórico não dispara toast antigo. Ao receber resposta nova, renderizar antes de enviar displayed ACK. ACK prova confirmação do cliente, não leitura humana. Desativar alvo elimina próximas emissões; snapshots passados continuam no histórico.

Cliente usa timeout de 20 s; pode consultar estado de ciclo já reservado após resposta perdida. Servidor não mantém conexão SQL durante rede do provedor. Suspensão, offline ou atraso detectado interrompe indicação de acompanhamento; ao visibilitychange/pageshow/online consultar estado e retomar sem compensar ciclos perdidos.

Login/renovação usam Supabase Auth e tokens em memória; não acrescentar armazenamento permanente de tokens. Exportações existentes devem ser baixadas por fetch autenticado, pois links simples não enviam Bearer. Nenhum alvo no HTML público.

## Consistência do painel (A001)

GET /dashboard calcula posição e alocação em uma única transação read-only REPEATABLE READ, usando o mesmo mapa de cotações carregado uma vez. computed_at é o instante de cálculo, não a idade dos preços; quotes preserva quoted_at/fetched_at por ativo. portfolio_revision identifica a revisão contábil, não uma versão histórica recuperável do cache. A interface substitui os dois blocos juntos somente após receber a resposta completa. Os endpoints antigos permanecem compatíveis, mas requisições separadas não têm garantia de snapshot comum. Cada CSV usa um snapshot consistente próprio; downloads independentes podem representar instantes diferentes do painel.

## Bloqueio antes da reserva (A005)

POST /monitoring/cycles pode retornar HTTP 429 com state=blocked, reason=quota_exhausted ou provider_cooldown, cycle_id=null, next_due_at e next_retry_at UTC. next_retry_at é o fim da janela ou cooldown conhecido; Retry-After informa segundos até esse instante. Sem configuração confiável de quota/reset, retornar HTTP 503, reason=config_required e next_retry_at=null. Não criar ciclo, avaliações ou notificações, nem apresentar um ciclo antigo como resultado dessa tentativa. Registrar somente log operacional seguro. RF-08 aplica-se aos ciclos efetivamente reservados.

O cliente agenda pelo maior instante entre next_due_at e next_retry_at, sem repetição imediata; config_required suspende tentativas automáticas até correção e retomada explícita. Já um 429 do provedor após reserva termina o ciclo durável como failed (ou partial se houver resultados válidos) e atualiza cooldown; não se confunde com o bloqueio anterior à reserva.
