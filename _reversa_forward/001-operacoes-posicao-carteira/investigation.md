# Investigação técnica

Data: 2026-09-27. 🟡 Decisões propostas para aplicação nova. Nenhuma biblioteca instalada, conta externa alterada ou medição de desempenho executada nesta etapa.

## Evidências locais

Raiz contém framework e documentação, sem código de aplicação. Não existem architecture.md, c4-context.md, state-machines.md, dependencies.md, code-analysis.md, addenda ou principles.md. Hooks before-plan/after-plan vazios. Configuração de escrita bloqueia código fora das pastas Reversa. requirements.md não contém dúvidas pendentes; esclarecimentos restringem negociações e taxas a USDT.

## Alternativas

- Python com HTML no servidor: escolhido como proposta por motor Decimal nativo e pequeno conjunto de componentes. A economia de recursos é hipótese a medir.
- SPA com servidor separado: possível, mas não necessária para formulários e consultas de um usuário.
- Funções SQL para toda regra: atomicidade viável, mas motor puro facilita exemplos e testes sem banco. PostgreSQL continua garantindo transações e locks.
- Replay a cada leitura: descartado; projetar resultados na mutação evita custo a cada consulta.
- Filas/cache distribuído: sem justificativa nesta feature.

## Fontes primárias consultadas

- [Python Decimal](https://docs.python.org/3/library/decimal.html): aritmética decimal com contexto de precisão e arredondamento. Proposta: precisão 80 e ROUND_HALF_UP somente na apresentação USD.
- [PostgreSQL numeric](https://www.postgresql.org/docs/current/datatype-numeric.html): numeric evita representação binária inexata. Derivados sem escala fixa; validar limites de entrada e rejeitar NaN/infinito.
- [PostgreSQL locks](https://www.postgresql.org/docs/current/explicit-locking.html): lock de linha serializa mutações da carteira. Todas as rotas de escrita devem adquirir o mesmo lock.
- [Conexões Supabase](https://supabase.com/docs/guides/database/connecting-to-postgres): escolher conexão direta quando alcançável ou pooler de sessão para IPv4. Validar papel customizado e DSN no ambiente; nunca assumir conectividade antes do teste.
- [Supabase RLS](https://supabase.com/docs/guides/database/postgres/row-level-security): políticas restringem linhas. Como o backend usa SQL direto, ele precisa estabelecer identidade validada na transação; não há propagação automática do JWT nessa conexão.
- [Supabase JWT](https://supabase.com/docs/guides/auth/jwts): validar assinatura por biblioteca adequada. Usar PyJWT/JWKS com algoritmos permitidos explicitamente, issuer, audience e exp; configuração legada sem chave assimétrica usa validação pelo endpoint de usuário, falhando de modo fechado.
- [FastAPI Docker](https://fastapi.tiangolo.com/deployment/docker/): aplicação pode ser empacotada em imagem própria. Proposta de um worker deve ser medida.
- [Koyeb health checks](https://www.koyeb.com/docs/run-and-scale/health-checks): configurar verificação HTTP na porta exposta; usar /health/live e readiness separado com consulta curta ao banco.

## Validação prevista

Confirmar compatibilidade e fixar versões exatas no início do coding. Testar conexão SSL/papel runtime, políticas de acesso e rotação de chaves antes de dados reais. Benchmark com 10.000 operações, 100 ativos, 30 leituras/mutações aquecidas. Testar conservação: valor total menos aportes líquidos deve igualar resultado realizado líquido mais não realizado quando todas as cotações estão disponíveis. Aportar e retirar caixa não produz rendimento.
