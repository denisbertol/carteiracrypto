# Investigação — Feature 003

Data: 2026-09-27. Pesquisa documental e leitura local; sem acesso ao banco de produção, credenciais ou testes vivos da API.

## Provedor e viabilidade

🟡 Escolha proposta: CoinGecko Demo. A [página oficial de planos](https://www.coingecko.com/en/api/pricing) anuncia 10.000 chamadas/mês, 100/minuto e atribuição obrigatória. Uma chamada por ciclo de 5 minutos produz 288/dia e 8.928 em 31 dias contínuos; sobram 1.072 para catálogo e outros consumos. Uso intermitente reduz esse total. Contar todas as tentativas conservadoramente. Confirmar o orçamento efetivo no painel da chave; se compartilhada, contabilizar chamadas de outros clientes também. Não assumir cobertura ou disponibilidade garantidas.

A [referência Demo de preços](https://docs.coingecko.com/demo/reference/simple-price) permite até 515 IDs, USD e last_updated_at. Deduplicar IDs, usar precision=full e interpretar números via Decimal. Testar URL real quando catálogo crescer. Preços idênticos em ciclos diferentes não são erro; timestamp antigo ou ausente não é cotação fresca.

[Autenticação Demo](https://docs.coingecko.com/demo/reference/authentication): chave no header do servidor. [Catálogo](https://docs.coingecko.com/demo/reference/coins-list): fonte de IDs. Cachear catálogo por 24 h; buscar somente quando necessário para resolver mapeamento. Incluir atribuição com link na interface. O uso pretendido é pessoal; nova publicação/comercialização exige rever termos do plano.

Alternativas avaliadas arquiteturalmente: feeds de corretoras são limitados a mercados listados e pares; USDT de corretora não deve ser apresentado automaticamente como USD externo. Outros agregadores permanecem alternativas se a prova CoinGecko falhar; não há comparação de quotas deles verificada nesta etapa. Não implementar fallback silencioso que mude a fonte do preço.

## Evidências locais que exigem auditoria

🔴 app/auth.py, TokenVerifier.verify_token: aceita prefixo test-token- sem checar ambiente; fallback HS256 usa chave publicável como segredo e desliga validação de issuer. Não transportar esses caminhos para endpoints de alvos. Remover bypass do runtime; injetar verificador falso apenas nos testes. Validar assinatura/issuer/audience/exp e proprietário; legado simétrico deve consultar endpoint autenticado de usuário ou ser rejeitado, nunca usar chave pública como segredo.

🔴 app/main.py, home: carrega carteira usando OWNER_USER_ID sem validar identidade da requisição. A interface não contém sessão cliente que resolva o problema. Proposta: shell público sem valores, login e leitura autenticada via API. Não tratar isso como mera configuração RLS.

🟡 QuoteReader retorna fixture por configuração e há default fixture no config. Produção deve recusar fixture explicitamente. PortfolioService chama QuoteReader enquanto usa cursor; substituir por leitura local do cache, jamais fazer fetch externo nesse caminho. AllocationService e exports precisam compartilhar snapshot coerente.

🟡 Os adendos afirmam entregas completas, mas não são prova de segurança ou desempenho. Não repetimos aqui as alegações de RAM/testes como medições novas. Não há architecture.md nem principles.md; adendos 001/002 vigentes são as fontes de contexto.

## Estados e interpretação

Ciclo: reserved → running → completed/partial/failed. Lease vencido vira failed; não reconstruir alertas do intervalo. Avaliação: outside/inside/error/superseded. Notificação: created → displayed → read; created não significa entregue. Histórico mantém 30 dias, sem reenviar toasts antigos ao reabrir; ciclos novos continuam notificando.

Propostas a auditar: frescor máximo 300 s; tolerância de relógio futuro 60 s; lease de ciclo 60 s; timeout HTTP total 10 s; sem retry HTTP no mesmo ciclo; cooldown por Retry-After. Cadência solicitada não é silenciosamente ampliada quando falha: apresentar indisponibilidade.
