# Roadmap: Operações e posição da carteira

> Identificador: `001-operacoes-posicao-carteira`
> Data: `2026-09-27`
> Requirements: `_reversa_forward/001-operacoes-posicao-carteira/requirements.md`
> Confidência: 🟢 CONFIRMADO, 🟡 PROPOSTA TÉCNICA, 🔴 BLOQUEIO

## 1. Resumo da abordagem

🟡 Adicionar a primeira aplicação do projeto: serviço Python/FastAPI com HTML renderizado por Jinja2, CSS responsivo e JavaScript mínimo na mesma origem. Um processo Uvicorn atende a interface e API; PostgreSQL persiste operações e projeções. Um motor puro em Python Decimal reconstrói a posição em ordem cronológica. Cada mutação trava a carteira, valida o histórico e grava operações, projeções e auditoria na mesma transação. Supabase Auth identifica Denis; o servidor usa um papel restrito de banco. O serviço roda em container no Koyeb. Não haverá filas, Redis ou processo permanente de cotações nesta feature.

## 2. Princípios aplicados

Não existe `.reversa/principles.md`; não há conflito com princípios formalizados. Restrições efetivamente observadas:

| Princípio | Como a feature se relaciona | Status |
|---|---|---|
| 🟢 Uso pessoal e leve | Um processo, pool de até 3 conexões e cálculo sob demanda | respeita |
| 🟢 Infraestrutura indicada | Container no Koyeb e PostgreSQL/Supabase | respeita |
| 🟢 AGENTS.md: política de escrita | Este plano escreve somente em `_reversa_forward/` | respeita |
| 🔴 Código fora do Reversa | `allowLegacyEdits: false` impede criar app/, tests/, migrations/ e arquivos de execução | bloqueio futuro, não impede planejar |

A configuração pertence exclusivamente ao usuário. Não será modificada pelo agente. Antes do coding, Denis deverá habilitar os caminhos pretendidos em `.reversa/reversa-config.json`, conforme AGENTS.md.

## 3. Decisões técnicas

| ID | Decisão | Justificativa | Alternativas descartadas | Confidência |
|---|---|---|---|---|
| D-01 | Python 3.13, FastAPI, Jinja2, psycopg 3 com pool, PyJWT com suporte criptográfico; versões exatas fixadas no coding | Motor decimal nativo e interface simples no mesmo container | SPA e múltiplos serviços aumentam componentes | 🟡 |
| D-02 | Decimal com precisão 80; numeric sem escala fixa para derivados; entradas limitadas a 18 casas e 18 dígitos inteiros | Preservar valores e evitar float no domínio; rejeitar precisão excedente em vez de truncar | float binário | 🟡 |
| D-03 | Lock da linha da carteira antes de toda mutação; replay integral inicialmente | Consistência com um usuário e correções retroativas | Atualização parcial sem replay perde validação histórica | 🟡 |
| D-04 | Projeções persistidas por revisão; leitura não recalcula operações | Consultas frequentes com pouco trabalho | Replay em cada consulta | 🟡 |
| D-05 | Supabase Auth por senha, conta previamente criada e cadastro público desabilitado; JWT validado e sub igual a OWNER_USER_ID | Acesso exclusivo de Denis | Implementar armazenamento de senhas próprio | 🟡 |
| D-06 | Papel SQL próprio sem BYPASSRLS; schema privado; RLS e identidade local à transação | Defesa contra acesso indevido ao banco e isolamento de requisições | Uso de credencial administrativa no runtime | 🟡 |
| D-07 | Idempotency-Key por intenção de mutação e revisão otimista da carteira | Reenvio seguro após timeout e edição por duas abas | Repetir requisições sem identificação | 🟡 |
| D-08 | Cotação por porta interna QuoteReader; sem provedor externo nesta entrega | Contrato com Monitoramento de preços e alertas; posição histórica funciona sem preço | Acoplar a API ainda não escolhida | 🟡 |
| D-09 | CSV separado por recurso, UTF-8, vírgula e ponto decimal | Conferência e precisão; arquivos abertos conforme escolha do usuário | XLSX como único formato | 🟢 |
| D-10 | Não rastrear custódia por local nesta feature; origem e destino são rótulos nas transferências | Posição pedida é global | Contabilidade completa por corretora | 🟡 |

## 4. Premissas

Nenhuma premissa oriunda de dúvida não resolvida. RN-14 (despesas) e RN-16 (saldo não negativo) são inferências já explicitadas nos requisitos. Stack, limites e metas abaixo são propostas técnicas, não aprovações explícitas de Denis.

Metas iniciais para 100 ativos e 10.000 operações, um usuário e processo aquecido: leitura p95 ≤ 500 ms e mutação com replay p95 ≤ 2 s, medidos em 30 execuções; memória residente ≤ 256 MiB; CPU média ociosa < 1% de um núcleo em 5 minutos. Registrar máquina, latência do banco e consumo no teste; não prometer esses números sem medição. Ajustar projeto se a meta falhar, antes de aceitar a entrega.

## 5. Delta arquitetural

Não existe architecture.md nem aplicação legada; todos os componentes abaixo são adições.

| Componente | Arquivo de origem | Tipo | Resumo |
|---|---|---|---|
| Operações e posição da carteira | `_reversa_sdd/sdd/operacoes-posicao-carteira.md` | componente-novo | Motor decimal, cadastro, histórico, transações, exportação e tela básica |
| Monitoramento de preços e alertas | `_reversa_sdd/sdd/monitoramento-precos-alertas.md` | contrato-novo | Porta de leitura de cotações; implementação do monitoramento fica para sua feature |
| Painel móvel da carteira | `_reversa_sdd/sdd/painel-movel-carteira.md` | contrato-novo | Posições e totais prontos para consumo; esta feature só entrega sua interface básica |
| Alocação e rebalanceamento | `_reversa_sdd/sdd/alocacao-rebalanceamento.md` | contrato-novo | Disponibilizar saldo e posição sem implementar percentuais ideais |

Arquivos previstos para criação no coding: `pyproject.toml`, `uv.lock`, `Dockerfile`, `.dockerignore`, `.env.example`, `README.md`, `app/main.py`, `app/config.py`, `app/auth.py`, `app/db.py`, `app/domain/ledger.py`, `app/services/portfolio.py`, `app/services/quotes.py`, `app/routes/{assets,operations,portfolio,exports}.py`, `app/templates/`, `app/static/`, `migrations/001_initial.sql`, `tests/`, `scripts/seed_demo.py`. A lista é planejamento, não autorização de escrita. Confirmar novamente a política antes de criar cada grupo.

## 6. Delta no modelo de dados

Adicionar carteira única, ativos, operações, revisões auditadas, projeções e registro de idempotência em schema privado. Valores derivados são reconstruíveis, cotações não alteram custo. Não remover campos existentes: não há schema de aplicação implantado conhecido. Detalhes em `data-delta.md`.

## 7. Delta de contratos externos

| Contrato | Tipo | Arquivo |
|---|---|---|
| Carteira e autenticação do cliente | HTTP | `interfaces/http.md` |
| Exportação | arquivo/HTTP | `interfaces/csv.md` |
| Supabase Auth | HTTPS/JWT | `interfaces/auth.md` |

A ligação QuoteReader é interna: `get_quotes(asset_ids)` retorna preço USD decimal, instante, fonte e estado available/stale/unavailable. Não há endpoint público para fabricar preços. Em produção inicial usa indisponível até integração; fixtures somente em teste/local, visivelmente identificadas. Preço com mais de 30 minutos é stale e total também sinaliza desatualização. Ausência de preço em posição positiva torna total dependente null/incompleto; posições zeradas não impedem total.

## 8. Plano de migração

1. No coding, verificar liberação de escrita; fixar dependências e construir motor puro com testes CA-01 a CA-16.
2. Em banco de teste, executar migração versionada: schema privado, tabelas, índices, RLS, grants e papel runtime restrito. Credenciais de migração nunca entram no container.
3. Criar conta Denis no Auth, desabilitar cadastro público e configurar OWNER_USER_ID. Validar usuário diferente e requisição anônima rejeitados.
4. Validar atomicidade e reenvio contra PostgreSQL real, incluindo duas conexões concorrentes e falha antes do commit.
5. Implementar API, formulários móveis, CSV e fixture de preço apenas para ambiente de teste.
6. Validar container e health check; configurar secrets e conexão SSL no ambiente de destino. Não migrar ou publicar produção automaticamente nesta etapa.
7. Carga manual começa por aportes USDT anteriores às compras. Reproduzir dados fictícios antes do histórico real; não modificar a planilha de origem.
8. Rollback da aplicação para imagem anterior, mantendo dados. Nesta primeira entrega, desligar serviço se necessário; nunca apagar schema com dados reais como rollback automático. Exportação para conferência não substitui backup; testar backup/restauração antes da carga real.

## 9. Riscos e mitigações

| Risco | Impacto | Probabilidade | Mitigação |
|---|---|---|---|
| Replay lento em histórico grande | médio | média | Benchmark definido; medir antes de introduzir checkpoints |
| Arredondamento acumulado | alto | média | Decimal, nenhum arredondamento de apresentação reutilizado, zerar custo ao liquidar toda posição, testes de conservação |
| Duplicação após timeout | alto | média | Resultado e chave persistidos na transação; retry usa mesma chave |
| Bypass de autorização | alto | baixa | Validar token e proprietário; grants mínimos; RLS; testes negativos |
| Cotação ainda não integrada | médio | certa nesta etapa | Mostrar indisponível; fixtures testam valores sem alegar cotação real |
| Histórico inicial sem aporte | médio | média | Orientar aporte real anterior; rejeitar déficit sem criar saldo fictício |
| Bloqueio de escrita do código | alto para coding | certa atualmente | Usuário altera política antes da implementação; documentação pode seguir |

## 10. Critério de pronto

- [ ] Todas as ações futuras de `actions.md` concluídas.
- [ ] RF-01 a RF-12 e CA-01 a CA-16 verificados; Should incluídos nesta proposta.
- [ ] Testes do motor, transações, RLS, idempotência, correção/exclusão e ordem temporal passam.
- [ ] Totais incompletos, histórico vazio, falha de rede e sessão expirada tratados na interface móvel.
- [ ] CSV preserva precisão e neutraliza fórmulas em campos textuais.
- [ ] Metas de recursos medidas e relatório com resultados reais.
- [ ] Container funcional e onboarding executado em ambiente isolado.
- [ ] `cross-check.md`, se executado, sem CRITICAL/HIGH; `regression-watch.md` gerado no coding.
- [ ] Re-extração recomendada após entrega; não é condição para este plano.

## 11. Histórico de alterações

| Data | Alteração | Autor |
|---|---|---|
| 2026-09-27 | Plano inicial após esclarecimentos; documentação apenas | reversa-plan |
