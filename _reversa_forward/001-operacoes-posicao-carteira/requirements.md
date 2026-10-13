# Requirements: Operações e posição da carteira

> Identificador: `001-operacoes-posicao-carteira`
> Data: `2026-09-27`
> Pasta da extração reversa: `_reversa_sdd/`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO / herdado de fonte planejada, 🔴 LACUNA

## 1. Resumo executivo

🟡 Permitir que Denis registre ativos e operações realizadas e consulte quantidade, custo, preço médio ponderado e ganhos e perdas em dólares americanos (USD). A posição será reconstruída a partir do histórico, substituindo os cálculos manuais da planilha. Esta entrega fornece a base para alocação, alertas e painel móvel.

## 2. Contexto a partir do legado

Projeto novo, sem código legado documentado. Não existem architecture.md, domain.md, inventory.md, code-analysis.md, adendos ou princípios locais. As fontes são as especificações planejadas; sua marcação amarela não comprova implementação. As decisões da sessão de esclarecimentos abaixo prevalecem sobre a spec e o PRD quando restringem o escopo. As demais definições da spec prevalecem sobre pendências anteriores do PRD.

| Fonte | Trecho relevante | Confidência |
|---|---|---|
| `_reversa_sdd/sdd/operacoes-posicao-carteira.md#6-requisitos-funcionais` | Cadastro, seis operações, posição e resultados | 🟡 |
| `_reversa_sdd/sdd/operacoes-posicao-carteira.md#7-requisitos-não-funcionais` | Precisão, integridade e rastreabilidade | 🟡 |
| `_reversa_sdd/sdd/operacoes-posicao-carteira.md#11-edge-cases-e-tratamento-de-erros` | Retroatividade, duplicidade e falhas | 🟡 |
| `_reversa_sdd/sdd/operacoes-posicao-carteira.md#12-segurança-e-privacidade` | Acesso restrito e auditoria | 🟡 |
| `_reversa_sdd/sdd/operacoes-posicao-carteira.md#14-open-questions` | Exportação, referências e eventos externos pendentes | 🟡 |
| `_reversa_sdd/prd.md#5-não-objetivos-out` | Sem integração automática, execução de ordens ou múltiplos usuários | 🟡 |
| `_reversa_sdd/personas.md#persona-1-denis` | Uso pessoal frequente pelo celular | 🟡 |

## 3. Personas e cenários de uso

| Persona | Objetivo | Cenário-chave |
|---|---|---|
| 🟡 Denis | Conferir posição e resultados da própria carteira | Registra o histórico inicial e operações concluídas; consulta pelo celular aproximadamente a cada hora, quando disponível. |

## 4. Regras de negócio novas ou alteradas

Todas as regras são novas. Origem: `_reversa_sdd/sdd/operacoes-posicao-carteira.md#6-requisitos-funcionais`, exceto onde indicado.

1. **RN-01 🟡:** Somente operações realizadas e persistidas alteram a posição. Intenções não são registradas como operações.
2. **RN-02 🟡:** USDT representa caixa, valorizado em 1 USD por unidade nesta versão. Caixa é contado uma única vez no saldo total.
3. **RN-03 🟡:** Compra acrescenta quantidade e custo de aquisição, incluindo taxas. Preço médio ponderado é custo remanescente dividido pela quantidade mantida.
4. **RN-04 🟡:** Venda reduz o custo pela quantidade vendida multiplicada pelo preço médio anterior. Resultado realizado é receita líquida de taxas menos esse custo. Venda parcial preserva o preço médio remanescente.
5. **RN-05 🟡:** Transferência entre locais do próprio usuário é neutra para quantidade e custo globais, exceto taxas. Referência de transferência não pode ser duplicada.
6. **RN-06 🟡:** Resultado não realizado é quantidade vezes cotação menos custo remanescente. Mudanças de cotação não alteram resultados realizados.
7. **RN-07 🟡:** Valor atual em cripto é a soma das posições cotadas; saldo total é esse valor mais caixa. Percentual em caixa é caixa dividido pelo saldo total, multiplicado por 100. Custo remanescente e valor de mercado devem ter rótulos distintos.
8. **RN-08 🟡:** Inclusão, correção ou exclusão retroativa exige reavaliar todo o histórico posterior. Nenhuma venda pode produzir quantidade negativa em qualquer instante. Origem adicional: `_reversa_sdd/sdd/operacoes-posicao-carteira.md#11-edge-cases-e-tratamento-de-erros`.
9. **RN-09 🟡:** Cotação ausente não equivale a zero. Quantidade, custo e resultado realizado continuam disponíveis; valor atual e resultado não realizado ficam indisponíveis. Total dependente de preço ausente deve indicar incompletude, sem apresentar subtotal como total completo.
10. **RN-10 🟡:** Com quantidade zerada, custo remanescente é zero e preço médio não é aplicável; resultado realizado permanece no histórico. Com saldo total zero, percentual em caixa não é aplicável. A regra de posição encerrada é uma inferência explícita para evitar divisão por zero.

11. **RN-11 🟢:** Compras e vendas liquidam exclusivamente em USDT. Compra debita do caixa o valor negociado mais a taxa; venda credita o valor negociado menos a taxa. Trocas diretas entre criptos ficam fora desta versão. Origem: resposta 1 da sessão de esclarecimentos.
12. **RN-12 🟢:** Depósitos e saques externos aceitam somente USDT e representam aportes e retiradas, sem gerar lucro ou prejuízo. Transferências entre locais do próprio usuário continuam permitidas para os ativos já mantidos. O histórico inicial de cripto é reconstruído por compras e vendas. Origem: resposta 2.
13. **RN-13 🟢:** Todas as taxas são pagas em USDT; taxas em outro ativo são rejeitadas nesta versão. Taxas vinculadas a compra e venda seguem RN-03 e RN-04. Origem: resposta 3.
14. **RN-14 🟡:** Taxas avulsas e de transferência debitam o caixa e são despesas realizadas da carteira, separadas do lucro de vendas; o resultado realizado líquido agregado deduz essas despesas uma única vez. Não alteram o custo das posições cripto. Esta convenção é uma inferência de cálculo, não uma resposta explícita do usuário.
15. **RN-15 🟢:** Operações são ordenadas por data/hora e, em caso de empate, pela ordem de cadastro. Denis pode ajustar manualmente a ordem dos eventos empatados, com recálculo posterior. Origem: resposta 4.
16. **RN-16 🟡:** Qualquer alteração que deixe caixa ou quantidade de ativo negativos em algum ponto do histórico é rejeitada integralmente, inclusive taxa, saque ou reordenação. Regra derivada da integridade, sem suporte a saldo devedor nesta versão.

## 5. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de aceite | Confidência |
|---|---|---|---|---|
| RF-01 | Cadastrar ativo por identificador único, nome e símbolo de cotação | Must | Cadastro válido fica disponível; identificador repetido é rejeitado | 🟡 |
| RF-02 | Registrar compra, venda, depósito, saque, transferência e taxa, com data/hora, ativo, quantidade, preço e campos aplicáveis | Must | Os seis tipos aparecem no histórico; campos ausentes e quantidade não positiva são rejeitados; depósitos e saques externos aceitam somente USDT; negociações liquidam em USDT; empate de horário permite reordenação manual | 🟡 |
| RF-03 | Manter caixa em USDT | Must | Depósito de 100 e saque de 40 resultam em caixa de USD 60 | 🟡 |
| RF-04 | Incorporar taxas ao custo de compra e deduzi-las da receita de venda | Must | Taxas em USDT reproduzem CA-04; outra moeda é rejeitada; taxas avulsas e de transferência seguem RN-14 | 🟡 |
| RF-05 | Calcular preço médio ponderado | Must | Compras do cenário CA-04 produzem preço médio de USD 160 | 🟡 |
| RF-06 | Apurar resultado realizado e custo após venda | Must | Venda de CA-04 produz lucro de USD 35, custo remanescente de USD 320 e quantidade 2 | 🟡 |
| RF-07 | Registrar transferência interna e vincular sua taxa | Must | Transferência sem taxa preserva posição e custo; referência duplicada é rejeitada; taxa em USDT tem vínculo rastreável e reduz somente o caixa e o resultado líquido agregado | 🟡 |
| RF-08 | Calcular resultado não realizado com cotação identificada por instante | Must | Cotação de USD 180 para 2 unidades com custo USD 320 produz ganho de USD 40 | 🟡 |
| RF-09 | Exibir quantidade, cotação, valor atual, preço médio, custo e resultados por ativo | Must | Todos os campos calculáveis ficam visíveis; campos indisponíveis são identificados | 🟡 |
| RF-10 | Exibir valor atual em cripto, custo remanescente agregado, caixa, saldo total e percentual em caixa | Must | Cripto USD 360 e caixa USD 140 resultam em total USD 500 e 28% em caixa | 🟡 |
| RF-11 | Corrigir e excluir operações com recálculo cronológico | Should | Mudança válida atualiza resultados; mudança que invalida venda posterior é rejeitada integralmente | 🟡 |
| RF-12 | Exportar ativos, operações e resultados em CSV (valores separados por delimitador) | Should | Exportação contém IDs, datas, quantidades, preços, taxas, resultados e instante das cotações, em CSV, preservando precisão dos valores de origem e ordem dos eventos | 🟡 |

## 6. Requisitos Não Funcionais

| Tipo | Requisito | Evidência ou justificativa | Confidência |
|---|---|---|---|
| Precisão | Apresentar USD com duas casas; preservar precisão intermediária; divergência máxima de USD 0,01 por resultado frente aos exemplos de referência | Spec, seção 7 | 🟡 |
| Integridade | Persistência e recálculo devem produzir um único estado consistente; falha não pode deixar efeitos parciais | Spec, seção 11 | 🟡 |
| Retentativa e concorrência | Reenvio da mesma submissão não duplica operação; escritas simultâneas não podem permitir venda acima do saldo | Derivado da integridade; proposta de comportamento | 🟡 |
| Segurança | Somente Denis autenticado pode ler, modificar ou exportar a carteira; requisições não autorizadas são negadas | Spec, seção 12; mecanismo será definido no plano | 🟡 |
| Privacidade e auditoria | Proteger dados em trânsito e armazenamento; registrar criação, correção e exclusão sem expor valores financeiros em logs operacionais | Spec, seção 12 | 🟡 |
| Rastreabilidade | Toda posição deve ser reproduzível pelas operações persistidas e pela cotação identificada | Spec, seção 7 | 🟡 |
| Usabilidade | Formulário e histórico utilizáveis pelo celular; falha de gravação preserva preenchimento e não mostra sucesso | Spec, seções 8 e 11 | 🟡 |
| Recursos | Evitar processamento contínuo desta feature sem alteração de operações ou cotações; metas quantitativas serão estabelecidas no plano | PRD, seção 6; comportamento proposto | 🟡 |

## 7. Critérios de Aceitação

Denis aceitou exemplos fictícios como referência inicial para validar os cálculos e confirmou exportação em CSV. CA-03 a CA-08 constituem essa referência; cenários adicionais cobrem as regras esclarecidas e as inferências explicitadas.

```gherkin
Cenário: CA-01 Cadastro de ativo (RF-01)
  Dado que um identificador ainda não existe
  Quando Denis cadastra o ativo com nome e símbolo
  Então ele fica disponível para operações
  E uma segunda inclusão com o mesmo identificador é rejeitada

Esquema do Cenário: CA-02 Tipos de operação (RF-02)
  Dado um histórico compatível e campos válidos segundo a regra do tipo
  Quando Denis registra <tipo>
  Então a operação aparece uma única vez no histórico
  E ausência de campo obrigatório ou quantidade não positiva é rejeitada
  Exemplos:
    | tipo |
    | compra |
    | venda |
    | depósito |
    | saque |
    | transferência |
    | taxa |

Cenário: CA-03 Caixa (RF-03)
  Dado caixa inicialmente zerado
  Quando Denis registra depósito de 100 USDT e saque de 40 USDT
  Então o caixa é USD 60

Cenário: CA-04 Compras e venda parcial (RF-04, RF-05, RF-06)
  Dado caixa suficiente e posição inicialmente zerada
  Quando são registradas compra de 2 unidades a USD 100 com taxa USD 10
  E compra de 1 unidade a USD 250 com taxa USD 20
  Então a quantidade é 3, custo USD 480 e preço médio USD 160
  Quando é registrada venda de 1 unidade a USD 200 com taxa USD 5
  Então o resultado realizado é USD 35
  E restam 2 unidades, custo USD 320 e preço médio USD 160

Cenário: CA-05 Transferência (RF-07)
  Dado um ativo mantido em local pertencente a Denis
  Quando ele registra transferência interna sem taxa
  Então quantidade global, custo e resultado realizado não mudam
  E reutilizar a referência é rejeitado
  Quando a transferência inclui taxa de 2 USDT e há caixa suficiente
  Então o caixa e o resultado realizado líquido da carteira diminuem em USD 2
  E quantidade e custo do criptoativo transferido permanecem iguais

Cenário: CA-06 Cotação e detalhe (RF-08, RF-09)
  Dado 2 unidades com custo USD 320 e resultado realizado USD 35
  Quando a cotação é USD 180
  Então são exibidos quantidade 2, cotação USD 180 e valor atual USD 360
  E preço médio USD 160, custo USD 320 e resultado não realizado USD 40
  E o resultado realizado permanece USD 35

Cenário: CA-07 Totais e carteira vazia (RF-10)
  Dado valor atual em cripto de USD 360 e caixa de USD 140
  Quando Denis consulta os totais
  Então o saldo é USD 500 e caixa representa 28%
  Dado carteira sem posições e sem caixa
  Então saldo é zero e percentual em caixa não é aplicável

Cenário: CA-08 Correção e exclusão (RF-11)
  Dado compra de 2 unidades a USD 100 e venda posterior de 1 a USD 150, sem taxas
  Quando o preço da compra é corrigido para USD 120
  Então o custo remanescente é USD 120 e lucro realizado USD 30
  Quando a venda é excluída
  Então a posição retorna a 2 unidades, custo USD 240 e resultado realizado zero

Cenário: CA-09 Exportação (RF-12)
  Dado histórico válido com resultados calculados
  Quando Denis exporta os dados
  Então obtém CSV com ativos, operações, taxas e resultados com identificadores, datas e ordem dos eventos
  E resultados dependentes de preço incluem instante da cotação

Cenário: CA-10 Histórico inválido
  Dado saldo de 2 unidades
  Quando é submetida venda de 3 unidades
  Então a operação é rejeitada e o saldo permanece 2
  E uma correção retroativa que cause esse mesmo déficit é rejeitada integralmente

Cenário: CA-11 Cotação ausente
  Dado posição com quantidade e custo conhecidos
  Quando não há cotação disponível
  Então quantidade, preço médio, custo e resultado realizado continuam disponíveis
  E valor atual e resultado não realizado não são substituídos por zero
  E os totais dependentes desse preço são indicados como incompletos

Cenário: CA-12 Falha, reenvio e concorrência
  Dado uma operação preenchida
  Quando a persistência falha ou excede o tempo de espera
  Então o preenchimento é preservado sem confirmação de sucesso
  Quando a mesma submissão é reenviada após sucesso não confirmado
  Então apenas uma operação é mantida
  Dado duas vendas simultâneas que juntas excedem a posição
  Então somente a quantidade disponível pode ser efetivamente vendida no histórico

Cenário: CA-14 Liquidação em USDT
  Dado caixa de 1000 USDT e posição cripto zerada
  Quando são registradas as compras e a venda de CA-04
  Então o caixa após as compras é 520 USDT
  E o caixa após a venda é 715 USDT
  E uma troca direta entre criptoativos é rejeitada

Cenário: CA-15 Limites e taxas avulsas
  Dado caixa de 10 USDT
  Quando é registrada taxa avulsa de 2 USDT
  Então o caixa passa a 8 USDT e a despesa realizada da carteira é USD 2
  E não há alteração no custo dos criptoativos
  Quando é submetido saque de 9 USDT
  Então o saque é rejeitado integralmente
  E depósitos ou saques externos em cripto e taxas em outro ativo são rejeitados

Cenário: CA-16 Ordem no mesmo instante
  Dado compra e venda no mesmo horário, cadastradas nessa ordem
  Então o cálculo considera primeiro a compra
  Quando Denis altera a ordem de eventos empatados
  Então o histórico posterior é recalculado
  E a alteração é rejeitada se produzir quantidade ou caixa negativos

Cenário: CA-13 Acesso restrito
  Dado acesso sem identidade autorizada
  Quando são solicitados consulta, alteração ou exportação
  Então nenhum dado financeiro é retornado e nenhuma operação é alterada
```

## 8. Prioridade MoSCoW

| Item | MoSCoW | Justificativa |
|---|---|---|
| RF-01 a RF-10 | Must | Base de registro e cálculo da carteira |
| RF-11 e RF-12 | Should | Correção histórica e conferência externa |
| Precisão, integridade, segurança e rastreabilidade | Must | Necessários para confiar nos resultados |
| Usabilidade e recursos | Must | Uso frequente pelo celular em aplicação leve |
| Integração automática, execução de ordens, múltiplos usuários | Won't | Exclusões explícitas da primeira versão |
| Alertas, alvos e alocação ideal | Won't nesta feature | Pertencem às outras especificações já planejadas |

## 9. Esclarecimentos

### Sessão 2026-09-27

- **Q:** Como serão registradas as negociações?
  **R:** 1 a — Apenas compras e vendas usando USDT.
- **Q:** Depósitos e saques de cripto envolvendo terceiros entram na primeira versão?
  **R:** 2 a — Não; depósitos e saques externos serão apenas em USDT. Transferências entre locais próprios permanecem no escopo.
- **Q:** Em quais moedas serão registradas taxas?
  **R:** 3 a — Somente USDT nesta versão.
- **Q:** Como ordenar operações com o mesmo horário?
  **R:** 4 a — Ordem de cadastro, permitindo ajuste manual.
- **Q:** Podemos usar exemplos fictícios e exportar em CSV?
  **R:** 5 a — Sim, ambos.

As respostas resolvem L-01, L-02 e L-03. As convenções complementares sobre despesas e rejeição de saldo negativo estão explicitadas como inferências em RN-14 e RN-16, sem atribuí-las à confirmação do usuário.

## 10. Lacunas

Nenhuma dúvida pendente nesta sessão. Detalhes técnicos e metas de recursos serão definidos no planejamento.

## 11. Histórico de alterações

| Data | Alteração | Autor |
|---|---|---|
| 2026-09-27 | Versão inicial baseada na spec; revisão de cobertura dos 12 requisitos e registro de três grupos de lacunas | reversa-requirements |
| 2026-09-27 | Integração de cinco respostas; três grupos de lacunas resolvidos; atualização das regras, requisitos e cenários | reversa-clarify |
