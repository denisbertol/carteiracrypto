# Primeiro teste da feature

🟡 Roteiro para executar depois do coding. Os comandos e telas abaixo são contratos de entrega ainda não existentes; não foram executados nesta etapa de planejamento.

## Preparação

1. Antes do coding, Denis deve liberar os caminhos de código em `.reversa/reversa-config.json`. Estado atual: allowLegacyEdits=false. O agente não edita essa política.
2. Usar banco/projeto de teste, nunca histórico real no primeiro teste. Instalar Python 3.13, uv e Docker para os comandos planejados.
3. Copiar `.env.example` para `.env` e preencher DATABASE_URL do papel runtime, SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, OWNER_USER_ID e APP_ENV=development. Não commitar secrets. MIGRATION_DATABASE_URL é usada apenas no comando de migração.
4. Criar a conta de teste autorizada no Supabase Auth e desabilitar cadastro público. Anotar usuário/senha fora dos arquivos versionados.
5. Executar `uv sync --frozen`, `uv run python -m app.migrate` (usa MIGRATION_DATABASE_URL), `uv run pytest`, `uv run uvicorn app.main:app --host 127.0.0.1 --port 8000`.
6. Abrir http://127.0.0.1:8000, autenticar e conferir carteira vazia. Outro usuário e visitante devem receber acesso negado.

## Conferência manual

1. Cadastrar ativo fictício TEST; depositar 1000 USDT antes das compras.
2. Comprar 2 TEST a USD 100 com taxa 10 USDT; comprar 1 a USD 250 com taxa 20. Esperado: 3 TEST, custo USD 480, média USD 160, caixa 520 USDT.
3. Vender 1 TEST a USD 200, taxa 5. Esperado: 2 TEST, custo USD 320, lucro realizado USD 35 e caixa 715 USDT.
4. Sem cotação, valor atual e resultado não realizado ficam indisponíveis. Para teste isolado, reiniciar com QUOTE_MODE=fixture e DEMO_QUOTE_USD=180 (permitidos somente em development/test). Esperado: valor USD 360, ganho não realizado USD 40, total USD 1075; indicação visível de preço fictício.
5. Registrar transferência interna de 1 TEST, referência única e taxa 2 USDT. Quantidade/custo não mudam; caixa 713; despesas USD 2 e resultado realizado líquido USD 33; saldo com fixture USD 1073.
6. Tentar venda de 3 TEST, saque maior que caixa, taxa em outro ativo e referência duplicada: todos rejeitados sem alterar dados.
7. Testar em conjunto separado compra 2 a 100 e venda 1 a 150, sem taxas. Corrigir compra para 120: custo restante 120 e lucro 30. Excluir venda: 2 unidades, custo 240 e lucro zero. Usar aportes suficientes.
8. Empatar horários de compra/venda e ajustar ordem. Reordenação inválida deve ser rejeitada.
9. Exportar assets, operations e results em CSV e comparar números, datas e ordem; resultado ausente deve ser campo vazio com status explicativo, não zero.
10. Inspecionar interface em 360 px e desktop; preservar preenchimento após falha de rede. Teste automatizado deve cobrir reenvio após resposta perdida e vendas simultâneas.

## Container e operação

Executar `docker build -t carteira-crypto:local .` e `docker run --rm --env-file .env -e PORT=8000 -p 8000:8000 carteira-crypto:local`. Container sem secrets embutidos, processo não root, um worker. Verificar /health/live e /health/ready. No Koyeb, porta deve coincidir com PORT e health check HTTP; configurar secrets pelo ambiente. Deploy e migração remota são etapas posteriores, não realizadas por este plano.

Executar benchmark definido no roadmap e registrar resultados. Sair do modo fixture antes de qualquer uso real; produção deve recusar QUOTE_MODE=fixture. Remover somente banco de teste descartável após conferência. Preservar backup e exportação antes de carregar histórico real.
