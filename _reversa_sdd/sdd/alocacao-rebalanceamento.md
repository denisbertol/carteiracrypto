# Spec: Alocação e rebalanceamento

**Versão:** 1.0
**Status:** Em revisão
**Autor:** reversa-spec-sdd
**Data:** 2026-09-27
**Reviewers:** Denis

---

## 1. Resumo

🟡 O componente registra os percentuais de alocação informados pelo consultor e compara, em USD, a posição atual com a posição ideal calculada sobre o saldo total. USDT representa o caixa, integra a carteira e participa dos mesmos 100% distribuídos entre todos os ativos.

## 2. Contexto e Motivação

**Problema:** 🟡 Denis precisa enxergar quanto possui e quanto deveria possuir em cada ativo para acompanhar o equilíbrio da carteira sem depender da planilha compartilhada.

**Evidências:** 🟡 A planilha de referência apresenta saldo ideal, valor atual, alocação, desvio em USD e desvio percentual por ativo. Ela também mostra USDT como caixa, mas o exemplo soma percentuais de criptoativos a 100% antes de acrescentar USDT; a regra confirmada corrige essa inconsistência ao exigir 100% incluindo USDT.

**Por que agora:** 🟡 O balanceamento orienta decisões pessoais de compra e venda e precisa usar a mesma base de saldo das demais métricas da carteira.

## 3. Goals (Objetivos)

- [ ] 🟡 G-01: Garantir que a alocação vigente some exatamente 100,00%, incluindo USDT.
- [ ] 🟡 G-02: Reconciliar a soma das posições ideais com o saldo total, com diferença máxima de USD 0,01 após arredondamento.
- [ ] 🟡 G-03: Mostrar o ajuste necessário em USD para 100% dos ativos da orientação vigente.

**Métricas de sucesso:**

| Métrica | Baseline atual | Target | Prazo |
|---|---:|---:|---|
| 🟡 Soma da alocação vigente | 🟡 Planilha de referência inconsistente no exemplo | 🟡 100,00% | 🟡 A cada publicação da orientação |
| 🟡 Reconciliação da posição ideal | 🟡 Não automatizada | 🟡 Diferença absoluta ≤ USD 0,01 | 🟡 A cada atualização de saldo ou orientação |

## 4. Non-Goals (Fora do Escopo)

- 🟡 NG-01: Executar automaticamente o rebalanceamento.
- 🟡 NG-02: Emitir recomendação de comprar, vender ou manter.
- 🟡 NG-03: Otimizar percentuais ou substituir a orientação do consultor.
- 🟡 NG-04: Manter alocações separadas para múltiplos usuários ou carteiras de terceiros.

## 5. Usuários e Personas

**Usuário primário:** 🟡 Denis, que recebe novos percentuais do consultor e toma suas próprias decisões a partir da posição atual e ideal.

**Usuário secundário:** 🟡 Não existe na primeira entrega. O consultor não acessa nem edita o produto.

**Jornada atual:** 🟡 Denis atualiza percentuais em planilha e compara manualmente saldos ideais e atuais.

**Jornada futura:** 🟡 Denis registra uma nova orientação, consulta a posição atual e ideal em USD e usa o ajuste necessário como informação para decidir fora da aplicação.

## 6. Requisitos Funcionais

### 6.1 Requisitos Principais

| ID | Requisito | Prioridade | Critério de Aceite |
|---|---|---|---|
| RF-01 | 🟡 O usuário deve poder criar uma orientação de alocação com data de vigência e um percentual para cada ativo, incluindo USDT. | Must | 🟡 A orientação válida registra data, ativos e percentuais e fica identificável como vigente. |
| RF-02 | 🟡 O sistema deve aceitar uma orientação como vigente somente quando a soma dos percentuais for 100,00%. | Must | 🟡 Somatórios diferentes de 100,00% são rejeitados com a diferença informada; 100,00% é aceito. |
| RF-03 | 🟡 O sistema deve preservar as orientações anteriores quando uma nova versão entrar em vigor. | Must | 🟡 A orientação anterior continua consultável e deixa de ser usada nos cálculos atuais. |
| RF-04 | 🟡 O sistema deve calcular o saldo total como o valor atual de todos os criptoativos somado ao caixa em USDT. | Must | 🟡 O saldo total reconcilia com a soma das posições atuais em USD. |
| RF-05 | 🟡 O sistema deve calcular a posição ideal em USD de cada ativo multiplicando o saldo total pelo percentual vigente. | Must | 🟡 Para saldo de USD 10.000,00 e alvo de 20%, a posição ideal é USD 2.000,00. |
| RF-06 | 🟡 O sistema deve calcular o ajuste necessário em USD como posição ideal menos posição atual. | Must | 🟡 Resultado positivo indica valor faltante; resultado negativo indica excesso, sem rótulo de ação. |
| RF-07 | 🟡 O sistema deve calcular o desvio percentual como posição atual dividida pela posição ideal, menos um, quando a posição ideal for maior que zero. | Must | 🟡 Atual de USD 900,00 e ideal de USD 1.000,00 resulta em -10,00%. |
| RF-08 | 🟡 O sistema deve mostrar ativo, percentual vigente, posição atual, posição ideal, ajuste necessário e desvio percentual, todos com unidade explícita. | Must | 🟡 A visão contém todas as colunas para cada ativo da orientação. |
| RF-09 | 🟡 O sistema deve recalcular as posições ideais e os desvios quando mudar uma cotação, uma operação ou a orientação vigente. | Must | 🟡 Alterar cada uma das três origens atualiza os valores dependentes. |
| RF-10 | 🟡 O sistema deve identificar a cotação e o instante usados para calcular a posição atual. | Should | 🟡 A visão permite distinguir valor atual de valor desatualizado. |

### 6.2 Fluxo Principal (Happy Path)

1. 🟡 O usuário recebe novos percentuais do consultor.
2. 🟡 O usuário cria uma orientação com data de vigência e percentuais para todos os ativos, incluindo USDT.
3. 🟡 O sistema valida que a soma é 100,00% e torna a nova orientação vigente.
4. 🟡 O sistema obtém o saldo total atual em USD.
5. 🟡 O sistema calcula posição ideal, ajuste necessário e desvio para cada ativo.
6. 🟡 O usuário consulta os valores e toma sua decisão fora do produto.

### 6.3 Fluxos Alternativos

**Fluxo Alternativo A — Orientação inválida:**
1. 🟡 O usuário informa percentuais cuja soma não é 100,00%.
2. 🟡 O sistema preserva a orientação vigente e informa quanto falta ou excede para 100,00%.

**Fluxo Alternativo B — Cotação desatualizada:**
1. 🟡 O sistema conserva a última cotação conhecida e identifica seu instante.
2. 🟡 O sistema sinaliza os valores derivados como desatualizados, sem apresentá-los como atuais.

## 7. Requisitos Não-Funcionais

| ID | Requisito | Valor alvo | Observação |
|---|---|---|---|
| RNF-01 | 🟡 Reconciliação | 🟡 Soma ideal difere do saldo total em no máximo USD 0,01 | 🟡 Eventual diferença de arredondamento deve ser visível e determinística. |
| RNF-02 | 🟡 Precisão percentual | 🟡 Armazenar precisão suficiente e exibir ao menos duas casas decimais na validação | 🟡 Não aceitar 99,99% ou 100,01% como 100,00%. |
| RNF-03 | 🟡 Atualização | 🟡 Recalcular após cada mudança confirmada nas dependências | 🟡 Não exibir resultados de versões misturadas. |
| RNF-04 | 🟡 Rastreabilidade | 🟡 Identificar orientação e cotação vigentes em 100% dos cálculos | 🟡 Necessário para conferência. |

## 8. Design e Interface

**Componentes afetados:** 🟡 Editor de orientação e tabela comparativa de alocação.

**Comportamento esperado:** 🟡 A tabela usa USD para posição atual, ideal e ajuste, e percentual para alocação e desvio. O ajuste aparece como número assinado, sem texto prescritivo de compra ou venda.

**Estados da UI:**
- 🟡 Estado vazio: solicitar a primeira orientação completa.
- 🟡 Estado de carregamento: manter identificável a orientação vigente e sinalizar recálculo.
- 🟡 Estado de erro: preservar a versão anterior e explicar soma inválida ou dado indisponível.
- 🟡 Estado de sucesso: apresentar a nova versão vigente e os valores reconciliados.

## 9. Modelo de Dados

🟡 Entidades comportamentais necessárias:

```text
Orientação de alocação: identificador, início de vigência, estado, data de criação
Item da orientação: orientação, ativo, percentual
Comparação calculada: ativo, saldo total, posição atual, posição ideal, ajuste necessário, desvio percentual, instante da cotação
```

**Migrações necessárias:** 🟡 Não há legado de aplicação. A primeira orientação será registrada manualmente.

## 10. Integrações e Dependências

| Dependência | Tipo | Impacto se indisponível |
|---|---|---|
| 🟡 Posição calculada da carteira | 🟡 Obrigatória | 🟡 Não calcular valores atuais, ideais ou desvios. |
| 🟡 Cotações atuais | 🟡 Obrigatória para criptoativos | 🟡 Exibir o último instante conhecido e sinalizar resultado desatualizado. |
| 🟡 Percentuais fornecidos pelo consultor | 🟡 Entrada manual obrigatória | 🟡 Manter a orientação vigente anterior até uma nova versão válida. |

## 11. Edge Cases e Tratamento de Erros

| Cenário | Trigger | Comportamento esperado |
|---|---|---|
| EC-01: Soma diferente de 100% | 🟡 Percentuais totalizam valor distinto de 100,00% | 🟡 Rejeitar ativação e informar a diferença. |
| EC-02: Ativo sem cotação | 🟡 Não há preço atual nem último preço válido | 🟡 Marcar posição atual, ideal comparável, ajuste e desvio como indisponíveis; não usar zero. |
| EC-03: Posição ideal zero | 🟡 Percentual vigente do ativo é 0% | 🟡 Exibir posição ideal zero, ajuste igual ao negativo da posição atual e desvio percentual como não aplicável. |
| EC-04: Saldo total zero | 🟡 Carteira sem valor atual | 🟡 Exibir posições ideais zero e desvios percentuais como não aplicáveis. |
| EC-05: Arredondamento | 🟡 Posições ideais arredondadas não somam exatamente o saldo total exibido | 🟡 Preservar cálculo com maior precisão e mostrar uma reconciliação com diferença máxima de USD 0,01. |
| EC-06: Nova orientação incompleta | 🟡 Um ativo da orientação vigente é omitido sem percentual explícito | 🟡 Exigir confirmação do percentual zero ou inclusão do ativo antes de ativar a versão. |
| EC-07: Posição indisponível | 🟡 Timeout ou falha ao obter posição ou cotações dependentes | 🟡 Manter a orientação vigente consultável, marcar a comparação como indisponível e não exibir ajustes derivados de dados incompletos. |

## 12. Segurança e Privacidade

- **Autenticação:** 🟡 Apenas o usuário autenticado acessa orientações e valores.
- **Autorização:** 🟡 O consultor não possui acesso na primeira entrega.
- **Dados sensíveis:** 🟡 Percentuais e saldos revelam a estratégia e o patrimônio e devem seguir a proteção aplicada à carteira.
- **Auditoria:** 🟡 Registrar criação e ativação de cada versão de orientação.

## 13. Plano de Rollout

- **Estratégia:** 🟡 Cadastrar a orientação da planilha como amostra após corrigir a soma para incluir USDT dentro dos 100%.
- **Como reverter (rollback):** 🟡 Reativar a versão anterior da orientação sem apagar o histórico.
- **Monitoramento pós-deploy:** 🟡 Conferir soma de percentuais, saldo total, posições ideais e reconciliação nas primeiras 24 a 48 horas.

## 14. Open Questions

| # | Pergunta | Impacto | Dono | Prazo |
|---|---|---|---|---|
| OQ-01 | ⚠️ ABERTO: O usuário poderá programar uma orientação futura ou apenas ativá-la imediatamente? | 🟡 Baixo | 🟡 Denis | 🟡 Antes do planejamento da interface |
| OQ-02 | ⚠️ ABERTO: Ativos mantidos com percentual zero devem aparecer sempre ou somente quando houver posição? | 🟡 Médio | 🟡 Denis | 🟡 Antes da implementação do painel |

## 15. Decisões Tomadas (Decision Log)

| Decisão | Alternativas consideradas | Racional |
|---|---|---|
| 🟡 Incluir USDT nos 100% | 🟡 Tratar caixa como reserva adicional | 🟡 Denis confirmou que USDT equivale ao caixa e integra a distribuição total. |
| 🟡 Usar saldo total como base | 🟡 Usar somente valor investido em criptoativos | 🟡 Denis confirmou inclusão de criptoativos e caixa na base. |
| 🟡 Exibir somente valor de ajuste | 🟡 Exibir comprar, vender ou manter | 🟡 Denis solicitou apenas o valor em USD. |

## Apêndice

### Referências
- 🟡 `../prd.md`
- 🟡 `../personas.md`
- 🟡 Planilha de referência `Planilha sem título.xlsx`, aba `Página1`, intervalo `F3:M15`.

### Histórico de Revisões
| Versão | Data | Autor | Mudanças |
|---|---|---|---|
| 🟡 1.0 | 🟡 2026-09-27 | 🟡 reversa-spec-sdd | 🟡 Criação inicial. |

## Relatório de avaliação

🟡 **Score total:** 100/100 — ⭐ Excelente, pronta para implementação.

| Dimensão | Score |
|---|---:|
| 🟡 Completude | 🟡 100% |
| 🟡 Testabilidade | 🟡 100% |
| 🟡 Clareza | 🟡 100% |
| 🟡 Escopo | 🟡 100% |
| 🟡 Casos de borda | 🟡 100% |

🟡 **Gaps críticos:** nenhum.

🟡 **Sugestões:** nenhuma.

🟡 **Iterações:** 2.
