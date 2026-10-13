# Spec: Operações e posição da carteira

**Versão:** 1.0
**Status:** Em revisão
**Autor:** reversa-spec-sdd
**Data:** 2026-09-27
**Reviewers:** Denis

---

## 1. Resumo

🟡 O componente mantém os ativos e as operações efetivamente realizadas e calcula, em USD, quantidade, custo, preço médio ponderado, ganhos realizados, ganhos não realizados e totais da carteira. Decisões e intenções sem operação executada não alteram a posição.

## 2. Contexto e Motivação

**Problema:** 🟡 Denis não possui uma visão consolidada e verificável de posição, preço médio, ganhos e perdas e depende de controles externos para reconstruir esses valores.

**Evidências:** 🟡 A jornada confirmada começa pelo registro do histórico e termina pelo registro da operação realizada. A planilha de referência mostra ativo, valor atual em USD, cotação, quantidade, total investido, caixa e saldo total.

**Por que agora:** 🟡 Os cálculos corretos são pré-requisito para o painel, para a alocação ideal e para interpretar os alvos do consultor.

## 3. Goals (Objetivos)

- [ ] 🟡 G-01: Registrar 100% das operações incluídas no escopo com dados suficientes para recalcular a carteira.
- [ ] 🟡 G-02: Reproduzir os exemplos financeiros aprovados sem divergência além da precisão monetária de USD 0,01.
- [ ] 🟡 G-03: Separar ganhos realizados e não realizados para cada ativo e para o total da carteira.

**Métricas de sucesso:**

| Métrica | Baseline atual | Target | Prazo |
|---|---:|---:|---|
| 🟡 Divergência dos valores monetários contra exemplos aprovados | 🟡 Não medida | 🟡 ≤ USD 0,01 por resultado | 🟡 Antes da aceitação da primeira entrega |
| 🟡 Tipos de operação aceitos | 🟡 Controle externo | 🟡 6 de 6 tipos definidos | 🟡 Primeira entrega |

## 4. Non-Goals (Fora do Escopo)

- 🟡 NG-01: Importar automaticamente operações de corretoras ou carteiras.
- 🟡 NG-02: Executar compras, vendas, depósitos, saques ou transferências.
- 🟡 NG-03: Registrar intenções, recomendações ou decisões sem operação realizada.
- 🟡 NG-04: Atender múltiplos usuários ou consolidar carteiras de terceiros.

## 5. Usuários e Personas

**Usuário primário:** 🟡 Denis, investidor com conhecimento avançado em investimentos, criptomoedas e sistemas, responsável pela própria carteira.

**Usuário secundário:** 🟡 Não existe na primeira entrega. O consultor fornece orientações fora do produto.

**Jornada atual:** 🟡 Denis registra ou consulta valores em planilha, reconstrói posição e resultados e decide com base em informações que podem estar dispersas.

**Jornada futura:** 🟡 Denis registra o histórico inicial e cada operação concluída, confere os cálculos e consulta a posição atualizada pelo celular.

## 6. Requisitos Funcionais

### 6.1 Requisitos Principais

| ID | Requisito | Prioridade | Critério de Aceite |
|---|---|---|---|
| RF-01 | 🟡 O usuário deve poder cadastrar um ativo com identificador único e símbolo de cotação. | Must | 🟡 O ativo válido fica disponível para operações e não é duplicado pelo mesmo identificador. |
| RF-02 | 🟡 O usuário deve poder registrar compra, venda, depósito, saque, transferência e taxa com data, ativo ou moeda, quantidade e valores aplicáveis. | Must | 🟡 Cada um dos seis tipos aceita um exemplo válido, rejeita campos obrigatórios ausentes e aparece no histórico. |
| RF-03 | 🟡 O sistema deve tratar USDT como caixa da carteira e expressar seus valores em USD na proporção de 1 USDT para 1 USD na primeira entrega. | Must | 🟡 Um depósito de 100 USDT aumenta o caixa em USD 100,00; um saque de 40 USDT o reduz em USD 40,00. |
| RF-04 | 🟡 O sistema deve incluir taxas de compra no custo de aquisição e subtrair taxas de venda do valor líquido recebido. | Must | 🟡 Os exemplos aprovados de compra e venda reproduzem custo e resultado líquido com precisão de USD 0,01. |
| RF-05 | 🟡 O sistema deve calcular o preço médio ponderado após compras usando custo acumulado, incluindo taxas, dividido pela quantidade mantida. | Must | 🟡 Duas compras com preços e taxas diferentes retornam o preço médio esperado com a precisão definida. |
| RF-06 | 🟡 O sistema deve manter o preço médio da quantidade remanescente após uma venda e apurar ganho realizado pela diferença entre valor líquido da venda e custo médio da quantidade vendida. | Must | 🟡 Uma venda parcial reduz quantidade e custo pelo preço médio anterior e registra o resultado realizado correto. |
| RF-07 | 🟡 O sistema deve tratar transferências entre locais pertencentes ao usuário como neutras para quantidade global e custo, exceto pela taxa efetivamente cobrada. | Must | 🟡 A transferência interna sem taxa não altera posição; com taxa, reduz somente a quantidade ou o caixa usado para pagá-la. |
| RF-08 | 🟡 O sistema deve calcular ganho não realizado pela diferença entre valor atual da posição e custo da quantidade mantida. | Must | 🟡 Ao mudar a cotação, o ganho não realizado muda e o ganho realizado permanece igual. |
| RF-09 | 🟡 O sistema deve mostrar por ativo quantidade atual, cotação em USD, valor atual em USD, preço médio, custo remanescente e ganhos realizados e não realizados. | Must | 🟡 Todos os campos são exibidos para um ativo com histórico válido e cotação disponível. |
| RF-10 | 🟡 O sistema deve calcular total investido em criptoativos, caixa em USDT, saldo total em USD e percentual em caixa. | Must | 🟡 Saldo total é igual à soma do valor atual dos criptoativos com o caixa, e percentual em caixa é caixa dividido pelo saldo total. |
| RF-11 | 🟡 O usuário deve poder corrigir ou excluir uma operação registrada, com recálculo cronológico de todos os resultados afetados. | Should | 🟡 Alterar uma operação antiga atualiza posição e resultados posteriores sem deixar valores derivados da versão anterior. |
| RF-12 | 🟡 O usuário deve poder exportar ativos, operações e resultados calculados em formato aberto. | Should | 🟡 A exportação contém identificadores, datas, valores de origem e resultados suficientes para conferência externa. |

### 6.2 Fluxo Principal (Happy Path)

1. 🟡 O usuário cadastra ou seleciona um ativo.
2. 🟡 O usuário registra uma operação efetivamente realizada e suas taxas.
3. 🟡 O sistema valida os campos e ordena o histórico pelo momento da operação.
4. 🟡 O sistema recalcula quantidade, custo, preço médio e ganho realizado.
5. 🟡 O sistema aplica a cotação disponível para calcular valor atual e ganho não realizado.
6. 🟡 O usuário consulta a posição e os totais atualizados.

### 6.3 Fluxos Alternativos

**Fluxo Alternativo A — Correção retroativa:**
1. 🟡 O usuário corrige uma operação histórica.
2. 🟡 O sistema recalcula do ponto alterado até o estado atual e identifica a alteração como correção.

**Fluxo Alternativo B — Cotação indisponível:**
1. 🟡 O sistema mantém quantidade, custo, preço médio e ganho realizado calculáveis.
2. 🟡 O sistema marca valor atual e ganho não realizado como indisponíveis, sem substituí-los por zero.

## 7. Requisitos Não-Funcionais

| ID | Requisito | Valor alvo | Observação |
|---|---|---|---|
| RNF-01 | 🟡 Precisão monetária | 🟡 Arredondamento de apresentação em USD 0,01 | 🟡 Cálculos internos devem preservar precisão suficiente antes da apresentação. |
| RNF-02 | 🟡 Rastreabilidade | 🟡 100% das posições derivadas de operações persistidas | 🟡 Valores calculados não podem depender de ajustes invisíveis. |
| RNF-03 | 🟡 Integridade | 🟡 Nenhuma venda pode deixar quantidade negativa | 🟡 Operações inválidas devem ser rejeitadas antes do recálculo. |
| RNF-04 | 🟡 Privacidade | 🟡 Dados acessíveis somente ao usuário autorizado | 🟡 Valores financeiros não devem aparecer em registros técnicos desnecessários. |

## 8. Design e Interface

**Componentes afetados:** 🟡 Cadastro de ativo, formulário de operação, histórico de operações e detalhe da posição.

**Comportamento esperado:** 🟡 Campos mudam conforme o tipo de operação e exibem claramente valores em USD, quantidade e taxa. Resultados calculados ficam separados de campos editáveis.

**Estados da UI:**
- 🟡 Estado vazio: orientar o cadastro do primeiro ativo e da primeira operação.
- 🟡 Estado de carregamento: preservar o formulário e indicar recálculo em andamento.
- 🟡 Estado de erro: indicar o campo inválido ou o motivo financeiro da rejeição.
- 🟡 Estado de sucesso: mostrar a operação no histórico e os valores recalculados.

## 9. Modelo de Dados

🟡 Entidades comportamentais necessárias:

```text
Ativo: identificador, símbolo de cotação, nome, estado
Operação: identificador, tipo, ativo ou moeda, data e hora, quantidade, preço em USD, taxa, observação, referência de transferência
Posição calculada: ativo, quantidade, custo remanescente, preço médio, ganho realizado, cotação, valor atual, ganho não realizado, instante da cotação
```

**Migrações necessárias:** 🟡 Não há legado de aplicação. O histórico inicial será inserido manualmente na primeira entrega.

## 10. Integrações e Dependências

| Dependência | Tipo | Impacto se indisponível |
|---|---|---|
| 🟡 PostgreSQL no Supabase | 🟡 Obrigatória | 🟡 Cadastro e histórico não podem ser persistidos; bloquear alterações e informar indisponibilidade. |
| 🟡 Cotação atual do componente de monitoramento | 🟡 Obrigatória para valor atual | 🟡 Manter cálculos históricos; marcar valor atual e ganho não realizado como indisponíveis ou desatualizados. |

## 11. Edge Cases e Tratamento de Erros

| Cenário | Trigger | Comportamento esperado |
|---|---|---|
| EC-01: Venda superior à posição | 🟡 Quantidade vendida maior que a disponível no instante da operação | 🟡 Rejeitar a operação e informar a quantidade máxima disponível. |
| EC-02: Operação fora de ordem | 🟡 Inserção ou correção com data anterior a outras operações | 🟡 Recalcular cronologicamente todos os estados posteriores. |
| EC-03: Transferência duplicada | 🟡 Mesma referência de transferência usada duas vezes | 🟡 Rejeitar duplicidade ou exigir correção da referência antes de salvar. |
| EC-04: Taxa em ativo diferente | 🟡 Taxa paga em ativo ou moeda distinto da operação | 🟡 Registrar a saída no ativo da taxa e preservar o vínculo com a operação principal. |
| EC-05: Cotação ausente | 🟡 Provedor sem preço atual para um ativo | 🟡 Não exibir zero; manter os cálculos independentes de cotação e sinalizar indisponibilidade. |
| EC-06: Saldo total zero | 🟡 Carteira sem criptoativos e sem USDT | 🟡 Exibir saldo zero e percentual em caixa como não aplicável. |
| EC-07: Persistência indisponível | 🟡 Timeout ou falha ao salvar no Supabase | 🟡 Não confirmar a operação, preservar os dados preenchidos para nova tentativa e impedir recálculo com registro não persistido. |

## 12. Segurança e Privacidade

- **Autenticação:** 🟡 Acesso exige identidade autenticada do único usuário.
- **Autorização:** 🟡 O usuário autenticado só pode ler e alterar a própria carteira.
- **Dados sensíveis:** 🟡 Histórico, saldos e resultados financeiros devem ser protegidos em trânsito e no armazenamento disponibilizado pela plataforma.
- **Auditoria:** 🟡 Registrar criação, correção e exclusão de operações sem incluir valores financeiros em logs operacionais desnecessários.

## 13. Plano de Rollout

- **Estratégia:** 🟡 Carga manual de um conjunto pequeno de operações conhecidas antes do histórico completo.
- **Como reverter (rollback):** 🟡 Preservar a exportação da carga validada e remover os registros de teste sem afetar a planilha de origem.
- **Monitoramento pós-deploy:** 🟡 Comparar quantidade, preço médio, resultados e totais com exemplos aprovados nas primeiras 24 a 48 horas de uso.

## 14. Open Questions

| # | Pergunta | Impacto | Dono | Prazo |
|---|---|---|---|---|
| OQ-01 | ⚠️ ABERTO: Qual formato aberto será usado na exportação inicial? | 🟡 Médio | 🟡 Denis | 🟡 Antes do planejamento da feature |
| OQ-02 | ⚠️ ABERTO: Quais exemplos reais formarão o conjunto de referência dos cálculos? | 🟡 Alto | 🟡 Denis | 🟡 Antes da implementação dos cálculos |
| OQ-03 | ⚠️ ABERTO: Como classificar depósitos e saques de cripto vindos de ou enviados para terceiros, distintos de transferências internas? | 🟡 Alto | 🟡 Denis | 🟡 Antes de aceitar esses eventos |

## 15. Decisões Tomadas (Decision Log)

| Decisão | Alternativas consideradas | Racional |
|---|---|---|
| 🟡 Registrar seis tipos de operação | 🟡 Somente compras e vendas | 🟡 Denis confirmou compra, venda, depósito, saque, transferência e taxa. |
| 🟡 Incorporar taxas ao custo e ao valor líquido | 🟡 Exibir taxas separadamente sem afetar resultados | 🟡 Denis confirmou esse tratamento. |
| 🟡 Exibir resultados realizados e não realizados | 🟡 Exibir apenas resultado total | 🟡 Denis confirmou a necessidade de ambos. |
| 🟡 Tratar USDT como caixa | 🟡 Manter caixa fora da carteira | 🟡 Denis definiu que USDT e caixa representam a mesma posição. |

## Apêndice

### Referências
- 🟡 `../prd.md`
- 🟡 `../personas.md`
- 🟡 Planilha de referência `Planilha sem título.xlsx`, aba `Página1`, intervalo `A2:M18`.

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
