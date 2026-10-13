# PRD: carteira-crypto

> Selo 🟡 PLANEJADO. Documento gerado a partir de ideation + personas.

**Versão:** 1.0
**Data:** 2026-09-27T17:51:42.9399583-03:00
**Autor:** reversa-drafter
**Status:** rascunho

---

## 1. Problema

🟡 Denis recebe semanalmente de seu consultor alvos de compra e venda e percentuais desejados de alocação, mas tem dificuldade para monitorar durante a semana quando as cotações se aproximam desses alvos. A falta de acompanhamento pode levar à perda de oportunidades previstas nas orientações recebidas.

🟡 Também falta uma visão consolidada e verificável do preço médio ponderado, dos ganhos e perdas e do desvio entre a distribuição atual e a alocação vigente. O produto deve apoiar a leitura da carteira; a decisão e a execução de negociações permanecem sob responsabilidade de Denis e ocorrem fora da aplicação.

### Quem sente
🟡 Denis, único usuário previsto, sente o problema ao consultar a carteira pelo celular aproximadamente de hora em hora, quando encontra uma oportunidade durante o dia, e ao atualizar orientações recebidas do consultor.

---

## 2. Personas-alvo

🟡 Referência completa em [`personas.md`](./personas.md). Resumo:

- **Denis:** 🟡 investidor com conhecimento avançado em investimentos, criptomoedas e sistemas, que administra a própria carteira e precisa acompanhar alvos, resultados e alocação sem delegar ao produto suas decisões de investimento.

---

## 3. Métricas de sucesso

🟡 A métrica confirmada mede a latência dos alertas. As demais métricas necessárias para comprovar confiabilidade, exatidão e baixo consumo ainda precisam de metas e métodos de medição.

| Métrica | Unidade | Alvo | Prazo |
|---|---|---|---|
| 🟡 Latência do alerta | 🟡 minutos entre a cotação entrar na faixa e a notificação ser recebida | 🟡 no máximo 30 minutos | 🟡 em cada evento do período de teste |
| 🟡 Cobertura de alertas devidos | 🟡 percentual de eventos detectados e notificados | 🟡 [INDEFINIDO, validar com usuário] | 🟡 [INDEFINIDO, validar com usuário] |
| 🟡 Exatidão dos cálculos | 🟡 divergência entre resultado do produto e exemplos de referência | 🟡 [INDEFINIDO, validar com usuário] | 🟡 antes da aceitação da primeira entrega |
| 🟡 Consumo computacional | 🟡 CPU, memória e armazenamento no ambiente de execução | 🟡 [INDEFINIDO, validar com usuário] | 🟡 durante o período de teste |

---

## 4. Escopo (in)

🟡 A primeira entrega cobre o ciclo pessoal de acompanhamento, da entrada manual dos dados à atualização da carteira após uma operação realizada.

- 🟡 Cadastrar e manter ativos acompanhados.
- 🟡 Registrar manualmente o histórico e as novas operações efetivamente realizadas, incluindo ao menos data, ativo, natureza da operação, quantidade e preço; demais campos permanecem sujeitos à definição das regras de cálculo.
- 🟡 Atualizar manualmente alvos de compra e venda quando o consultor fornecer novas orientações.
- 🟡 Atualizar manualmente os percentuais desejados de alocação quando o consultor os alterar, mantendo identificável qual orientação está vigente.
- 🟡 Consultar cotações por meio de uma API externa gratuita, dentro dos limites e intervalos suportados.
- 🟡 Apresentar interface adequada ao uso pelo celular ao longo do dia.
- 🟡 Exibir posição por ativo, preço médio ponderado, ganhos e perdas e distribuição atual da carteira.
- 🟡 Comparar a distribuição atual com os percentuais de alocação vigentes e exibir os desvios.
- 🟡 Detectar quando uma cotação entra na faixa de proximidade de um alvo, segundo regra ainda a definir.
- 🟡 Enviar alertas por um único canal e registrar os horários da cotação, da detecção e da entrega ou falha.
- 🟡 Recalcular posição e indicadores somente após o registro de uma operação efetivamente realizada.
- 🟡 Permitir exportar os dados necessários para evitar dependência do formato interno; formato e cobertura permanecem [INDEFINIDO, validar com usuário].

---

## 5. Não-objetivos (out)

🟡 Os itens abaixo estão explicitamente fora da primeira entrega:

- 🟡 Integração automática com corretoras ou carteiras.
- 🟡 Execução de ordens de compra ou venda.
- 🟡 Suporte a múltiplos usuários.
- 🟡 Registro de intenções ou decisões de investimento que não tenham produzido uma operação.
- 🟡 Tomada automática de decisão, recomendação personalizada ou substituição do julgamento de Denis e das orientações de seu consultor.

---

## 6. Restrições

🟡 A solução deve operar com baixo consumo de recursos e aproveitar a infraestrutura já utilizada por Denis.

| Tipo | Descrição |
|---|---|
| 🟡 Técnica | 🟡 Aplicação executada em container no Koyeb. |
| 🟡 Dados | 🟡 Supabase com PostgreSQL como banco de dados. |
| 🟡 Recursos | 🟡 Consumo mínimo de CPU, memória e armazenamento; limites numéricos [INDEFINIDO, validar com usuário]. |
| 🟡 Cotações | 🟡 Uso de API externa gratuita, respeitando cobertura, intervalo e limites do provedor. |
| 🟡 Alertas | 🟡 Entrega em até 30 minutos após a cotação entrar na faixa de proximidade. |
| 🟡 Uso | 🟡 Um único usuário, com uso frequente pelo celular. |
| 🟡 Prazo | 🟡 Nenhum prazo limite declarado inicialmente. |
| 🟡 Compliance | 🟡 [INDEFINIDO, validar com usuário] quanto a requisitos específicos de privacidade, retenção e LGPD para os dados financeiros. |
| 🟡 Orçamento | 🟡 Nenhum orçamento máximo declarado inicialmente; dependências gratuitas são preferidas para cotações. |

---

## 7. Dependências externas

🟡 O produto depende de serviços e informações fora de seu controle direto:

- 🟡 Koyeb para executar a aplicação em container.
- 🟡 Supabase/PostgreSQL para persistência.
- 🟡 API gratuita de cotações: provedor e cobertura [INDEFINIDO, validar com usuário].
- 🟡 Serviço ou mecanismo de notificação: canal e fornecedor [INDEFINIDO, validar com usuário].
- 🟡 Orientações fornecidas pelo consultor, inseridas manualmente por Denis.
- 🟡 Histórico de operações e preços fornecido por Denis.

---

## 8. Riscos

🟡 Os riscos abaixo afetam diretamente a utilidade e a confiança no produto.

| Risco | Impacto | Probabilidade | Mitigação proposta |
|---|---|---|---|
| 🟡 Alerta atrasado, ausente ou duplicado | 🟡 alto | 🟡 média | 🟡 Registrar horários e estados de cada avaliação e entrega; testar poucos ativos por alguns dias, incluindo falhas simuladas. |
| 🟡 API gratuita indisponível, limitada ou sem cobertura | 🟡 alto | 🟡 média | 🟡 Validar ativos, moeda, frequência e limites antes de comprometer a implementação; manter a dependência substituível. |
| 🟡 Preço médio, resultados ou alocação incorretos | 🟡 alto | 🟡 média | 🟡 Definir eventos e regras de cálculo e compará-los com exemplos conhecidos antes da aceitação. |
| 🟡 Dados financeiros expostos | 🟡 alto | 🟡 baixa | 🟡 Restringir acesso, evitar valores sensíveis em logs e notificações e definir retenção e exportação. |
| 🟡 Manutenção manual excessiva | 🟡 médio | 🟡 média | 🟡 Reduzir passos de entrada e testar o fluxo com a rotina semanal real de Denis. |
| 🟡 Consumo incompatível com a infraestrutura disponível | 🟡 médio | 🟡 média | 🟡 Medir CPU, memória, armazenamento e volume de consultas durante o teste e ajustar frequência e retenção. |
| 🟡 Alocação comparada contra orientação desatualizada | 🟡 médio | 🟡 média | 🟡 Identificar a orientação vigente e registrar quando novos percentuais passam a valer. |

---

## 9. Critérios de aceite (alto nível)

🟡 Os critérios descrevem resultados observáveis para a persona principal; detalhes de cálculo e notificação ainda dependem das pendências registradas.

- 🟡 **Dado** um histórico conhecido de operações cadastradas, **Quando** Denis consulta um ativo, **Então** vê sua posição, seu preço médio ponderado e seus ganhos e perdas calculados conforme as regras aprovadas.
- 🟡 **Dado** um conjunto de percentuais vigentes fornecidos pelo consultor, **Quando** Denis consulta a carteira, **Então** vê a distribuição atual e o desvio de cada ativo em relação à alocação recomendada.
- 🟡 **Dado** um novo conjunto de alvos ou percentuais, **Quando** Denis o registra, **Então** a aplicação passa a usar as orientações vigentes sem alterar o histórico das operações realizadas.
- 🟡 **Dado** que uma cotação entra na faixa de proximidade de um alvo, **Quando** a rotina de monitoramento avalia o ativo, **Então** registra o evento e entrega uma notificação pelo canal escolhido em até 30 minutos.
- 🟡 **Dado** que a API de cotações ou o canal de notificação falha, **Quando** uma execução não consegue concluir, **Então** a falha fica registrada de forma observável e não é contabilizada como alerta entregue.
- 🟡 **Dado** que Denis decide e executa uma negociação fora do produto, **Quando** registra a operação realizada, **Então** a posição, os cálculos e a alocação são atualizados; nenhuma intenção não executada altera a carteira.
- 🟡 **Dado** o uso pelo celular, **Quando** Denis acessa as funções da primeira entrega, **Então** consegue consultar a carteira e registrar os dados previstos sem depender de interface de desktop.

---

## Pendências de cobertura

- 🟡 [INDEFINIDO, validar com usuário] Regra de proximidade do alvo, incluindo se será percentual, valor absoluto ou faixa por ativo.
- 🟡 [INDEFINIDO, validar com usuário] Canal de notificação e comportamento com a aplicação fechada.
- 🟡 [INDEFINIDO, validar com usuário] Tipos de movimentação, taxas, transferências, moedas e método de apuração de resultados realizados e não realizados.
- 🟡 [INDEFINIDO, validar com usuário] API de cotação, ativos cobertos, moeda de referência e limites aplicáveis.
- 🟡 [INDEFINIDO, validar com usuário] Limites mensuráveis de CPU, memória, armazenamento e custo operacional.
- 🟡 [INDEFINIDO, validar com usuário] Exemplos de referência, tolerância e alvo para exatidão dos cálculos.
- 🟡 [INDEFINIDO, validar com usuário] Meta de cobertura, duração e volume mínimo do teste dos alertas.
- 🟡 [INDEFINIDO, validar com usuário] Formato e cobertura da exportação de dados.
- 🟡 [INDEFINIDO, validar com usuário] Requisitos específicos de privacidade, retenção e conformidade dos dados financeiros.

---

Gerado por reversa-drafter em 2026-09-27T17:51:42.9399583-03:00
Fontes: ideation.md, personas.md; contexto complementar: brainstorms/001-carteira-crypto/pre-spec.md
