# Delta de dados

🟡 Modelo novo, sem tabelas legadas para alterar. Schema proposto: `portfolio_private`, não exposto na Data API. Migração única inicial `migrations/001_initial.sql` e tabela de controle de versões. Identificadores UUID; datas timestamptz UTC; apresentação America/Sao_Paulo. Sem dados reais na migração.

## Tabelas adicionadas

| Tabela | Campos principais | Restrições e índices |
|---|---|---|
| portfolios | id, owner_id, revision bigint, created_at | singleton por configuração; owner único; linha travada em mutações |
| assets | id, portfolio_id, external_id, symbol, name, active | unique(portfolio_id, external_id); USDT reservado; símbolo não é identidade global |
| operations | id, portfolio_id, asset_id, kind, occurred_at, order_index bigint, quantity numeric, unit_price_usd numeric nullable, fee_usdt numeric default 0, transfer_ref nullable, source_label, destination_label, note, deleted_at, created_at, updated_at | índice (portfolio_id, occurred_at, order_index, id); referência de transferência única entre não excluídas; vínculos compostos impedem ativo de outra carteira |
| position_projections | portfolio_id, asset_id, quantity, remaining_cost_usd, realized_sales_usd, revision | chave composta; valores numeric; média derivada de custo/quantidade |
| portfolio_projection | portfolio_id, cash_usdt, deposits_usdt, withdrawals_usdt, standalone_expenses_usdt, realized_sales_usd, revision | uma linha por carteira; resultado líquido = vendas realizadas - despesas avulsas/transferência |
| operation_audit | id, portfolio_id, operation_id, action, actor_id, before_data jsonb, after_data jsonb, created_at, revision | acesso somente autorizado; contém dados financeiros protegidos, nunca copiados a logs operacionais |
| mutation_receipts | portfolio_id, key uuid, request_hash, response_status, response_body jsonb, created_at | unique(portfolio_id,key); guardar enquanto histórico existir para reenvio durável |

RLS habilitada e forçada em todas as tabelas. Papel runtime sem privilégio de proprietário, superuser ou BYPASSRLS, sem DDL e sem acesso a auth.users. Políticas verificam owner_id da carteira contra identidade local validada pelo backend (`set_config` com parâmetro e escopo local à transação). Requisição sem identidade não retorna dados. Revogar acessos de anon/authenticated ao schema privado. Migração com credencial separada.

## Regras por tipo

- buy/sell: ativo diferente de USDT; quantity e preço positivos; fee_usdt ≥ 0; débito/crédito de caixa calculado pelo motor, nunca recebido como valor derivado do cliente.
- deposit/withdrawal: asset_id de USDT; quantity positiva; preço ausente; taxa vinculada zero nesta versão (se houver taxa, registrar operação fee separada).
- transfer: ativo mantido, quantidade positiva ≤ posição global; origem e destino distintos e não vazios; transfer_ref obrigatório; fee_usdt opcional. Não rastrear saldos por local; transferência é um evento único e não dois lançamentos independentes.
- fee: asset_id de USDT, quantity é valor da despesa; fee_usdt zero para impedir dupla contagem; preço ausente.
- Rejeitar valores não finitos, negativos, excesso de precisão e campos incompatíveis. Entradas até 18 casas decimais e menos de 10^18; precisão excedente gera erro, não arredondamento oculto.

## Algoritmo e transação

1. Autenticar antes de abrir transação. Adquirir conexão do pool e definir identidade local. Travar portfolios com SELECT FOR UPDATE (lock_timeout 2 s).
2. Consultar recibo de idempotência antes de checar revisão: mesma chave/hash devolve resposta anterior; conteúdo diferente retorna conflito.
3. Verificar revisão If-Match. Carregar operações não excluídas, aplicar alteração candidata e ordenar por occurred_at, order_index, id. Cadastro empatado vai ao final; reorder recebe todos os IDs do instante e atribui índices consecutivos.
4. Replay integral em Decimal precisão 80. Compra soma custo e quantidade; venda usa custo proporcional e, ao liquidar posição inteira, baixa todo custo residual. Taxas de compra/venda entram apenas no custo/receita; demais taxas são despesas separadas.
5. Rejeitar a transação se houver déficit em qualquer momento. Persistir evento, projeções, auditoria, nova revisão e recibo de sucesso juntos. DELETE é exclusão lógica com replay.
6. Commit único; falha implica rollback. Leituras e exportações usam snapshot transacional consistente. Nenhuma chamada de rede de autenticação/cotação dentro do lock.

Dados de cotação são externos às projeções contábeis; QuoteReader entrega lote com timestamps. Sem preço, derivados de mercado null. Sem posição, preço médio null e custo zero. Backups precisam incluir auditoria/recibos; exclusão física futura requer política própria, não faz parte desta entrega.
