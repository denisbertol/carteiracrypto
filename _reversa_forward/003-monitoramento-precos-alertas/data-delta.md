# Delta de dados — Feature 003

🟡 Migração aditiva `migrations/003_price_monitoring.sql`. Reutilizar schema portfolio_private e RLS baseada na identidade validada da transação. Nenhuma alteração destrutiva das migrações 001/002.

## Novas entidades

| Tabela | Campos principais e invariantes |
|---|---|
| monitoring_settings | portfolio_id PK, proximity_percent numeric(5,2) default 10 check 0..100, revision, updated_at; intervalo 300 e retenção 30 constantes nesta versão |
| asset_price_mappings | portfolio_id, asset_id PK composta, provider, provider_coin_id, status pending/valid/unsupported, updated_at, version; FK composta para ativo da carteira |
| price_targets | id, portfolio_id, asset_id, kind buy/sell, price_usd numeric positivo/finito, active, orientation, version, created_at, updated_at |
| monitoring_changes | id, portfolio_id, entity_kind, entity_id, old_value/new_value protegidos, actor_id, created_at; alterações de alvo/configuração rastreáveis |
| monitoring_state | portfolio_id PK, next_due_at, current_cycle_id, lease_until, last_cleanup_at; lock curto coordena clientes |
| monitoring_cycles | id, portfolio_id, started_at, completed_at, status, lease_token, error_code, settings_revision; unique portfolio/id |
| latest_quotes | portfolio_id, asset_id PK composta, price_usd, quoted_at, fetched_at, provider, source_cycle_id nullable, last_attempt_at, last_error; cache não é histórico de preço completo |
| price_evaluations | id, portfolio_id, cycle_id, target_id, target_version, target_price/type/orientation snapshot, proximity_percent, price_usd, quoted_at, evaluated_at, distance_percent nullable, result, error_code, created_at; unique(cycle_id,target_id) |
| price_notifications | id, portfolio_id, evaluation_id unique, created_at, displayed_at nullable, read_at nullable; FK composta garante mesma carteira |
| provider_budget | provider/key_fingerprint, window_start/end, attempts, configured_limit, cooldown_until; chave real nunca persistida aqui |
| provider_catalog | provider PK, payload JSONB, fetched_at, expires_at, version, refresh_token nullable, refresh_lease_until nullable, last_error; cache compartilhado privado, acesso apenas pelo serviço |

UUIDs e timestamps UTC. Decimais recebidos em texto/Decimal, valores não finitos rejeitados antes de gravar. ÍNDICES: carteira/data/id para históricos, alvo/active, cycle status/lease, created_at para retenção. Todos os vínculos de entidades privadas devem impedir cruzamento de carteira. Budget é interno e não exposto pela Data API; grants separados se necessário.

## Transações e concorrência

1. Autenticar; transação curta obtém lock monitoring_state, verifica due/cooldown, reserva ciclo e quota conservadora para os lotes necessários. Definir next_due_at=agora+300 s; duplicatas retornam ciclo existente. Persistir antes de consultar provedor.
2. Liberar conexão; fazer HTTP com timeout de 10 s e prazo total inferior a lease de 60 s. Cachear catálogo independentemente e não misturar com transação contábil.
3. Nova transação valida lease_token, lê versões atuais de alvos/configuração e mapeamentos; preço de mapeamento alterado é descartado. Usar configurações capturadas no início; alvo alterado/desativado durante fetch gera superseded sem alerta e entra no próximo ciclo.
4. Gravar resultados por ativo; atualizar cache apenas com dados válidos e não regressivos no tempo. Avaliações registram inclusive falhas por ativo. Registrar inside e criar notificação uma vez por cycle/target. Marcar ciclo completed/partial/failed. Falha de commit não significa entrega.
5. ACK idempotente atribui displayed_at pelo relógio do servidor; read_at é independente. Antes de devolver notificações novas, verificar se alvo ainda está ativo/mesma versão. Histórico retém snapshots mesmo se alvo mudar.
6. Lease vencida: reconciliar no startup e a cada 60 s enquanto o processo estiver ativo, mesmo sem navegador ou requisições. UPDATE condicional por status reservado/em execução e lease vencida marca failed, completed_at e error_code=interrupted, libera estado e invalida token. Finalização tardia exige token vigente, status em execução e lease não vencida, impedindo novos resultados após reconciliação. Não consultar preços, devolver quota ou produzir avaliações retroativas. Enquanto o processo estiver parado, a recuperação aguarda o próximo startup. Executar reconciliação antes da retenção; requisições também podem reconciliar sob a mesma condição atômica.

Edições usam versão otimista de alvo/configuração; replay de POST usa receipt existente com escopo de método/caminho/owner e chave UUID. Não incrementar revisão contábil da carteira a cada cotação. Readers usam snapshot único no banco para cache, carteira e alocação.

O snapshot comum do painel é limitado à resposta agregada GET /dashboard: transação read-only REPEATABLE READ lê operações, recomendação e cache, carregando um único mapa de preços para ambos os cálculos. CSVs e endpoints independentes têm snapshots próprios, sem garantia entre requisições.

O catálogo tem validade de 24 h. Somente pedido autenticado de validação de mapeamento pode iniciar refresh: adquirir lease de 60 s com token/version e reservar orçamento em transação curta; liberar conexão antes do HTTP. Concorrentes mantêm mapeamento pending enquanto refresh estiver ativo. Commit exige token e lease vigentes; falha preserva payload anterior, mas catálogo expirado não aprova novos mapeamentos. Lease vencida permite nova tentativa posterior, sem restituição de quota. Cada tentativa externa consome orçamento, inclusive erro; sem orçamento não ocorre HTTP. O payload e locks não são expostos pela Data API, com grants mínimos ao serviço. Retenção histórica não remove esse cache.

Bloqueio de quota/cooldown anterior à reserva não cria monitoring_cycles. O contrato HTTP define estado blocked e prazo de retomada, inclusive quando nenhum ciclo anterior existe. Testar zero linhas novas e zero chamadas externas nesse caso.

## Retenção

Queries históricas impõem created_at > agora-30 dias, independentemente da execução física da limpeza. Limpeza automática no startup e horária: lotes até 1000 registros, notificações expiradas antes de avaliações; avaliações referenciadas por notificação ainda não expirada permanecem internamente até expiração dela, sem reaparecer no histórico. Remover ciclos/changes expirados somente sem referências vivas; latest_quotes tem snapshot próprio e não depende de ciclo removido. Orçamento mensal e receipts não entram nessa limpeza. Preservar alvos, mapeamentos, settings, operações e última cotação.

Limpeza exige identidade proprietária configurada e role restrito, não credencial administrativa. Singleton por lock para evitar duplicação entre processos. Enquanto container está parado não há limpeza física; no próximo startup ela retoma. Isso não mantém histórico expirado acessível.
