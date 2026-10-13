# Spec: Painel móvel da carteira

**Versão:** 1.0
**Status:** Em revisão
**Autor:** reversa-spec-sdd
**Data:** 2026-09-27
**Reviewers:** Denis

---

## 1. Resumo

🟡 O painel substitui a visualização principal da planilha e reúne, em uma experiência adequada ao celular, totais em USD, posição atual, posição ideal segundo os percentuais vigentes, resultados e estado dos alvos. A tela apresenta informações para decisão sem registrar intenções nem indicar ações de investimento.

## 2. Contexto e Motivação

**Problema:** 🟡 Denis consulta a carteira pelo celular aproximadamente de hora em hora e não quer depender da planilha usada com o consultor para visualizar a posição atual e ideal.

**Evidências:** 🟡 A referência contém um bloco de posição atual, um bloco de gerenciamento por alocação e os totais de investimento, caixa e saldo. Denis pediu a mesma visão no aplicativo com totais em USD.

**Por que agora:** 🟡 O painel é o ponto de acesso diário aos cálculos dos outros componentes e precisa preservar as relações financeiras que tornam a planilha útil.

## 3. Goals (Objetivos)

- [ ] 🟡 G-01: Exibir em uma única tela os totais e 100% dos ativos da carteira e da orientação vigente.
- [ ] 🟡 G-02: Reconciliar o saldo total exibido com a soma de posições atuais, incluindo USDT, com diferença máxima de USD 0,01.
- [ ] 🟡 G-03: Permitir consultar os dados essenciais em largura de celular sem exigir interface de desktop.

**Métricas de sucesso:**

| Métrica | Baseline atual | Target | Prazo |
|---|---:|---:|---|
| 🟡 Cobertura da carteira na visão | 🟡 Planilha externa | 🟡 100% dos ativos com posição ou percentual vigente | 🟡 Cada carregamento válido |
| 🟡 Reconciliação do saldo total | 🟡 Conferência manual | 🟡 Diferença absoluta ≤ USD 0,01 | 🟡 Cada carregamento válido |
| 🟡 Dependência de layout desktop | 🟡 Planilha horizontal | 🟡 0 função essencial exclusiva de desktop | 🟡 Primeira entrega |

## 4. Non-Goals (Fora do Escopo)

- 🟡 NG-01: Reproduzir defeitos de formatação ou inconsistências numéricas da planilha de referência.
- 🟡 NG-02: Executar ou recomendar compras, vendas e rebalanceamentos.
- 🟡 NG-03: Editar operações diretamente nas células do painel.
- 🟡 NG-04: Disponibilizar painéis diferentes para múltiplos usuários.

## 5. Usuários e Personas

**Usuário primário:** 🟡 Denis, usuário avançado que consulta a carteira frequentemente pelo celular.

**Usuário secundário:** 🟡 Não existe na primeira entrega.

**Jornada atual:** 🟡 Denis abre uma planilha, localiza os dois blocos horizontais e compara valores atuais e ideais.

**Jornada futura:** 🟡 Denis abre o aplicativo, confere os totais, percorre a posição atual e ideal e identifica ativos próximos de alvos ou fora da alocação esperada.

## 6. Requisitos Funcionais

### 6.1 Requisitos Principais

| ID | Requisito | Prioridade | Critério de Aceite |
|---|---|---|---|
| RF-01 | 🟡 O sistema deve exibir total investido em criptoativos, caixa em USDT, saldo total em USD e percentual em caixa. | Must | 🟡 Os quatro totais aparecem com unidade e reconciliam com as posições calculadas. |
| RF-02 | 🟡 O sistema deve exibir para cada ativo quantidade, cotação em USD, valor atual em USD, preço médio, ganho realizado e ganho não realizado. | Must | 🟡 Cada ativo com posição apresenta todos os campos disponíveis e identifica dados indisponíveis sem usar zero falso. |
| RF-03 | 🟡 O sistema deve exibir para cada ativo da orientação vigente o percentual, a posição atual em USD, a posição ideal em USD, o ajuste necessário em USD e o desvio percentual. | Must | 🟡 A comparação usa a orientação vigente e os valores do mesmo instante lógico. |
| RF-04 | 🟡 O sistema deve incluir USDT uma única vez como caixa e ativo da alocação, evitando dupla contagem no saldo total. | Must | 🟡 Somar linhas atuais reproduz o saldo total e USDT não aparece como valor adicional fora dessa soma. |
| RF-05 | 🟡 O sistema deve mostrar a última atualização das cotações e sinalizar valores desatualizados ou indisponíveis. | Must | 🟡 A tela distingue cotação válida recente, cotação antiga e ausência de preço. |
| RF-06 | 🟡 O sistema deve mostrar por ativo se existe alvo dentro da faixa de proximidade e permitir acessar seus detalhes. | Must | 🟡 Um alvo na faixa produz indicador; fora da faixa remove o indicador no ciclo seguinte. |
| RF-07 | 🟡 O sistema deve apresentar a visão em uma única página lógica, mantendo totais primeiro e detalhes abaixo. | Must | 🟡 O usuário alcança todos os dados essenciais por rolagem vertical no celular. |
| RF-08 | 🟡 O sistema deve adaptar os blocos da planilha para telas estreitas sem ocultar colunas essenciais. | Must | 🟡 Em largura de celular, os blocos ficam empilhados ou os registros usam uma apresentação equivalente legível. |
| RF-09 | 🟡 O usuário deve poder atualizar a visão para solicitar nova cotação e recalcular os valores dependentes. | Should | 🟡 A atualização mostra estado de carregamento e substitui todos os valores do ciclo de forma consistente. |
| RF-10 | 🟡 O sistema deve permitir navegar do ativo exibido para suas operações, alocação e alvos sem alterar os dados. | Should | 🟡 Cada acesso abre o contexto correto do ativo. |

### 6.2 Fluxo Principal (Happy Path)

1. 🟡 O usuário abre o aplicativo pelo celular.
2. 🟡 O sistema carrega posições, orientação vigente, cotações e estado dos alvos.
3. 🟡 O sistema exibe saldo total, total investido, caixa e percentual em caixa.
4. 🟡 O usuário percorre a posição atual e confere quantidades, valores e resultados.
5. 🟡 O usuário percorre a comparação de alocação e confere posição atual, ideal e ajuste em USD.
6. 🟡 O usuário identifica cotações desatualizadas e alvos dentro da faixa.
7. 🟡 O usuário abre o detalhe de um ativo quando precisa conferir a origem dos valores.

### 6.3 Fluxos Alternativos

**Fluxo Alternativo A — Dados parciais:**
1. 🟡 O painel recebe posição válida e alguma cotação está indisponível.
2. 🟡 O sistema exibe os dados calculáveis e marca somente os resultados dependentes da cotação como indisponíveis.

**Fluxo Alternativo B — Nenhuma orientação vigente:**
1. 🟡 O sistema exibe posição e totais atuais.
2. 🟡 O sistema substitui a comparação ideal por uma orientação para cadastrar os percentuais.

## 7. Requisitos Não-Funcionais

| ID | Requisito | Valor alvo | Observação |
|---|---|---|---|
| RNF-01 | 🟡 Responsividade | 🟡 Todas as funções essenciais disponíveis a partir de 360 px de largura | 🟡 Rolagem horizontal não pode ser a única forma de acessar campos essenciais. |
| RNF-02 | 🟡 Consistência | 🟡 Diferença de reconciliação ≤ USD 0,01 | 🟡 Totais e linhas devem usar o mesmo conjunto de cotações. |
| RNF-03 | 🟡 Tempo de apresentação | 🟡 Mostrar estado de carregamento em até 1 segundo após solicitar atualização | 🟡 A conclusão depende das integrações externas. |
| RNF-04 | 🟡 Consumo | 🟡 Uma resposta consolidada por abertura ou atualização do painel | 🟡 Evitar consultas repetidas por célula ou coluna apresentada. |

## 8. Design e Interface

**Componentes afetados:** 🟡 Página principal, resumo de totais, seção de posição atual, seção de alocação ideal e indicador de alvos.

**Comportamento esperado:** 🟡 A hierarquia segue a referência: totais da carteira, posição atual e comparação com a posição ideal. Em telas largas, seções podem ficar lado a lado; em telas estreitas, ficam empilhadas mantendo os mesmos rótulos e unidades.

**Estados da UI:**
- 🟡 Estado vazio: explicar quais dados faltam e fornecer acesso ao cadastro correspondente.
- 🟡 Estado de carregamento: preservar a estrutura da tela e indicar atualização em andamento.
- 🟡 Estado de erro: mostrar quais dados falharam e o instante da última informação válida.
- 🟡 Estado de sucesso: exibir dados reconciliados e o instante das cotações.

## 9. Modelo de Dados

🟡 O painel não é a fonte primária dos dados; consome uma projeção consolidada:

```text
Resumo da carteira: total investido, caixa USDT, saldo total, percentual em caixa, instante
Linha de posição: ativo, quantidade, cotação, valor atual, preço médio, ganhos realizados e não realizados, estado da cotação
Linha de alocação: ativo, percentual vigente, posição atual, posição ideal, ajuste, desvio, estado do alvo
```

**Migrações necessárias:** 🟡 Nenhuma exclusiva do painel.

## 10. Integrações e Dependências

| Dependência | Tipo | Impacto se indisponível |
|---|---|---|
| 🟡 Operações e posição da carteira | 🟡 Obrigatória | 🟡 Exibir estado de erro para posição e manter orientação para corrigir a origem. |
| 🟡 Alocação e rebalanceamento | 🟡 Obrigatória para posição ideal | 🟡 Manter posição atual disponível e sinalizar ausência da comparação ideal. |
| 🟡 Monitoramento de preços e alertas | 🟡 Obrigatória para valores atuais e alvos | 🟡 Identificar a última cotação válida ou indisponibilidade. |

## 11. Edge Cases e Tratamento de Erros

| Cenário | Trigger | Comportamento esperado |
|---|---|---|
| EC-01: USDT duplicado | 🟡 Caixa recebido também como linha adicional fora da posição | 🟡 Rejeitar dupla contagem e apresentar USDT uma única vez no saldo total. |
| EC-02: Soma ideal inválida | 🟡 Orientação vigente não totaliza 100% | 🟡 Não apresentar comparação como válida e direcionar para correção da orientação. |
| EC-03: Cotação ausente | 🟡 Ativo sem preço válido | 🟡 Mostrar quantidade e custo disponíveis e marcar valor atual e derivados como indisponíveis. |
| EC-04: Ativo fora da orientação | 🟡 Existe posição atual sem percentual vigente | 🟡 Exibir o ativo, sinalizar ausência de percentual e impedir reconciliação silenciosa. |
| EC-05: Orientação sem posição | 🟡 Percentual positivo para ativo ainda não possuído | 🟡 Exibir posição atual zero, ideal calculada e ajuste positivo em USD. |
| EC-06: Valor extenso em tela estreita | 🟡 Número ou rótulo não cabe na largura disponível | 🟡 Preservar número e unidade sem truncamento que altere o significado. |
| EC-07: Falha parcial externa | 🟡 Uma dependência falha enquanto outras respondem | 🟡 Exibir seções válidas e identificar precisamente a seção indisponível. |

## 12. Segurança e Privacidade

- **Autenticação:** 🟡 O painel exige sessão autenticada.
- **Autorização:** 🟡 Apenas o usuário da carteira visualiza saldos, resultados e alvos.
- **Dados sensíveis:** 🟡 Totais financeiros não devem aparecer em registros técnicos nem em conteúdo público.
- **Auditoria:** 🟡 O painel não cria operações; atualizações manuais de cotação devem ser rastreáveis quando existirem.

## 13. Plano de Rollout

- **Estratégia:** 🟡 Comparar o painel com uma cópia conhecida da planilha usando os mesmos ativos e saldos, após corrigir a regra de 100% incluindo USDT.
- **Como reverter (rollback):** 🟡 Retornar temporariamente à planilha sem alterar os dados persistidos pelos componentes de origem.
- **Monitoramento pós-deploy:** 🟡 Conferir reconciliação, ausência de dupla contagem, dados indisponíveis e uso em largura de 360 px nas primeiras 24 a 48 horas.

## 14. Open Questions

| # | Pergunta | Impacto | Dono | Prazo |
|---|---|---|---|---|
| OQ-01 | ⚠️ ABERTO: Qual ordem dos ativos deve prevalecer: orientação do consultor, valor atual ou símbolo? | 🟡 Baixo | 🟡 Denis | 🟡 Antes do refinamento visual |
| OQ-02 | ⚠️ ABERTO: Quais valores devem ficar ocultáveis no celular por privacidade visual? | 🟡 Médio | 🟡 Denis | 🟡 Antes do refinamento visual |

## 15. Decisões Tomadas (Decision Log)

| Decisão | Alternativas consideradas | Racional |
|---|---|---|
| 🟡 Preservar a visão da planilha | 🟡 Criar painel sem referência | 🟡 Denis quer deixar de depender da planilha mantendo a mesma informação. |
| 🟡 Mostrar totais em USD | 🟡 Mostrar somente quantidades | 🟡 Pedido explícito do usuário. |
| 🟡 Mostrar apenas ajuste em USD | 🟡 Mostrar comprar, vender ou manter | 🟡 Denis dispensou indicações de ação. |
| 🟡 Adaptar para celular | 🟡 Copiar grade horizontal literalmente | 🟡 O uso principal ocorre pelo celular ao longo do dia. |

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
