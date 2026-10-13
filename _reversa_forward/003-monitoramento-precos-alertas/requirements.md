# Requirements: Monitoramento de preços e alertas

> Identificador: `003-monitoramento-precos-alertas`
> Data: `2026-09-27`
> Pasta da extração reversa: `_reversa_sdd/`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO / PLANEJADO, 🔴 LACUNA / DÚVIDA

## 1. Resumo executivo

🟡 Permitir que Denis registre múltiplos alvos de compra e venda por ativo, configure uma faixa global de proximidade e receba alertas dentro da aplicação aberta em cada ciclo válido enquanto a cotação permanecer nessa faixa. A feature substitui o modo demonstrativo de cotações por uma integração gratuita em USD, registra avaliações e falhas e alimenta a posição e o rebalanceamento com a última cotação válida, sem executar ou recomendar operações.

## 2. Contexto a partir do legado

O projeto já possui carteira, catálogo de ativos, posição, alocação e interface móvel. A porta `QuoteReader` existe em modo fixture ou indisponível; esta feature deve evoluí-la preservando os contratos das Features 001 e 002.

| Fonte | Trecho relevante | Confidência |
|---|---|---|
| `_reversa_sdd/sdd/monitoramento-precos-alertas.md#6-requisitos-funcionais` | Onze requisitos de alvos, distância, ciclos, alertas e auditoria | 🟡 |
| `_reversa_sdd/sdd/monitoramento-precos-alertas.md#11-edge-cases-e-tratamento-de-erros` | Limites, falhas do provedor, múltiplos alvos e reconexão | 🟡 |
| `_reversa_sdd/sdd/monitoramento-precos-alertas.md#12-segurança-e-privacidade` | Alvos e notificações restritos à sessão autenticada | 🟡 |
| `_reversa_sdd/addenda/001-operacoes-posicao-carteira.md#resumo-da-entrega` | FastAPI, PostgreSQL/RLS, painel móvel e porta `QuoteReader` já entregues | 🟢 |
| `_reversa_sdd/addenda/001-operacoes-posicao-carteira.md#impacto-por-artefato-da-extração` | `app/services/quotes.py` contém a porta de cotações a ser evoluída | 🟢 |
| `_reversa_sdd/addenda/002-alocacao-rebalanceamento.md#resumo-da-entrega` | Rebalanceamento consome valores atuais da carteira | 🟢 |
| `_reversa_sdd/prd.md#5-não-objetivos-out` | Sem execução de ordens, decisão automática ou múltiplos usuários | 🟡 |
| `_reversa_sdd/personas.md#persona-1-denis` | Uso pessoal pelo celular, aproximadamente de hora em hora | 🟡 |

## 3. Personas e cenários de uso

| Persona | Objetivo | Cenário-chave |
|---|---|---|
| 🟡 Denis | Perceber a aproximação de preços aos alvos semanais e decidir fora do aplicativo | Atualiza alvos recebidos do consultor, abre o aplicativo quando quer acompanhar e recebe alertas repetidos por alvo enquanto o preço estiver na faixa. |

## 4. Regras de negócio novas ou alteradas

1. **RN-01 🟢:** O limite de proximidade é global, configurável de 0,00% a 100,00% inclusive, e começa em 10,00%. Alterações valem a partir do ciclo seguinte e não reescrevem avaliações anteriores.
2. **RN-02 🟡:** Cada alvo pertence a um ativo do catálogo, tem tipo `compra` ou `venda`, preço positivo em USD, orientação textual opcional e estado ativo/inativo. Um ativo pode ter vários alvos de cada tipo.
3. **RN-03 🟡:** A distância percentual é `abs(cotação - alvo) / alvo × 100`. Distância igual ao limite está dentro da faixa. Tipo do alvo não altera essa fórmula.
4. **RN-04 🟢:** Cada alvo ativo dentro da faixa produz uma notificação em cada ciclo válido, inclusive em ciclos consecutivos. Ao sair da faixa ou desativar o alvo, o ciclo seguinte não produz notificação; ao retornar, as notificações recomeçam.
5. **RN-05 🟡:** Um ciclo consulta no máximo uma cotação por ativo e reutiliza esse preço para todos os alvos ativos do ativo. Cada alvo gera avaliação independente.
6. **RN-06 🟡:** Somente cotação válida e nova para o ciclo pode gerar alerta. Erro, resposta inválida ou cotação desatualizada registra falha e preserva a última cotação válida apenas para exibição, sem criar alerta.
7. **RN-07 🟢:** A primeira versão só promete ciclos e alertas enquanto a aplicação estiver aberta em sessão autenticada. Perda de conexão ou fechamento encerra a promessa sobre o período; a retomada não cria alertas retroativos.
8. **RN-08 🟡:** Cada ciclo registra início, término e resultado. Cada avaliação registra alvo, cotação, instante da cotação, instante da avaliação, limite vigente, distância e resultado; falhas registram causa segura. Uma avaliação com alerta deve identificar a notificação exibida.
9. **RN-09 🟡:** A notificação informa ativo, tipo, cotação, alvo, distância e horário, sem saldo ou patrimônio. Vários alvos na faixa geram notificações separadas e identificáveis.
10. **RN-10 🟡:** A última cotação válida integra a posição e a alocação existentes; sua origem, instante e estado atualizado/desatualizado permanecem visíveis. USDT continua fixado em USD 1,00 e não precisa de consulta externa.
11. **RN-11 🟡:** Criar, alterar, ativar e desativar alvo ou configuração exige a mesma identidade proprietária e garantias de consistência usadas pelas features anteriores; falha não pode deixar alteração parcial.
12. **RN-12 🟢:** A cadência solicitada é de 5 minutos durante a sessão aberta e operacional. A escolha técnica do provedor deve verificar a viabilidade dessa frequência sem exceder a quota gratuita; limitação não pode causar redução silenciosa da cadência.
13. **RN-13 🟡:** Interpretar a resposta “Todos” como todos os ativos cadastrados, inclusive novos ativos e ativos sem posição com alvo de compra. Não equivale a consultar todas as criptomoedas do mercado. Ativo sem cobertura ou identificação inequívoca deve aparecer como indisponível e não gerar alerta; a cobertura universal de um provedor não está presumida. USDT segue RN-10.
14. **RN-14 🟢:** Notificações e avaliações persistem entre sessões por 30 dias, com limpeza automática dos registros expirados. Marcar como lido não impede novos alertas em ciclos posteriores.
15. **RN-15 🟡:** A janela de retenção usa o instante de criação de cada registro; ao completar 30 dias ele deixa de aparecer no histórico. A limpeza deve preservar alvos, configuração, operações e a última cotação válida necessária à exibição, mantendo seu instante original. A execução física da limpeza será definida no planejamento.

## 5. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de aceite | Confidência |
|---|---|---|---|---|
| RF-01 | Cadastrar, alterar, ativar e desativar alvos em USD por ativo, com tipo e orientação | Must | Alvo válido é persistido; inativo não é avaliado; múltiplos alvos coexistem | 🟡 |
| RF-02 | Consultar e alterar o percentual global de proximidade, iniciado em 10,00% | Must | Instalação sem configuração usa 10,00%; valor válido entra no ciclo seguinte | 🟢 |
| RF-03 | Calcular a distância pela fórmula de RN-03 | Must | Preços 90 e 110 para alvo 100 produzem 10,00% | 🟡 |
| RF-04 | Classificar distância menor ou igual ao limite como dentro da faixa | Must | A borda exata notifica; valor acima não notifica | 🟡 |
| RF-05 | Executar ciclos de cotação e avaliação a cada 5 minutos durante a sessão aberta | Must | Em sessão operacional e provedor disponível, ciclos são programados a cada 300 segundos; falhas ou suspensão são sinalizadas como interrupção, sem alegar cobertura do intervalo | 🟢 |
| RF-06 | Exibir uma notificação por alvo dentro da faixa em cada ciclo válido | Must | Três ciclos válidos dentro da faixa produzem três notificações para o alvo | 🟢 |
| RF-07 | Cessar e retomar alertas conforme faixa e estado do alvo | Must | Fora da faixa ou inativo não notifica; retorno à faixa recomeça no próximo ciclo | 🟢 |
| RF-08 | Persistir ciclos, cotações, avaliações, falhas e vínculo da notificação | Must | Todos os ciclos iniciados terminam como concluído ou falho, com dados suficientes para auditoria | 🟡 |
| RF-09 | Mostrar na interface a última cotação válida, horário, fonte e estado | Must | Denis distingue preço atual, desatualizado e indisponível; dado antigo não aparece como novo | 🟡 |
| RF-10 | Obter cotações em USD para todos os ativos cadastrados, conforme cobertura verificada de uma API gratuita | Must | Ativos novos entram no acompanhamento; ativo não suportado é identificado sem cotação fictícia; provedor, quota e identificação são validados no planejamento para ciclos de 5 minutos | 🟡 |
| RF-11 | Manter central não bloqueante com notificações e avaliações persistentes por 30 dias e limpeza automática | Should | Histórico continua acessível após nova sessão; alertas podem ser marcados como lidos; registros com 30 dias completos expiram e são removidos automaticamente | 🟢 |

## 6. Requisitos Não Funcionais

| Tipo | Requisito | Evidência ou justificativa | Confidência |
|---|---|---|---|
| Latência | Alerta devido exibido em até 30 minutos da primeira cotação válida observada dentro da faixa; não alegar conhecimento do mercado entre consultas | Spec G-01; limite confirmado pelo usuário | 🟡 |
| Observabilidade | 100% dos ciclos iniciados e avaliações tentadas terminam com resultado ou falha identificável, sem token, segredo ou saldo em logs | Spec G-02 e privacidade | 🟡 |
| Consumo | Uma consulta por ativo por ciclo; nenhum polling no servidor quando não há sessão ativa; reutilizar o processo e pool existentes | Aplicação leve e RNF-03 | 🟡 |
| Segurança | Alvos, configuração, avaliações e notificações acessíveis apenas a Denis; RLS forçada e validação da sessão existente | Adendos 001/002 e spec seção 12 | 🟢 |
| Resiliência | Timeout ou quota não apaga última cotação válida, não gera alerta falso e aplica espera compatível com o provedor | Spec EC-04 | 🟡 |
| Precisão | Valores monetários e percentuais usam decimal; alvo deve ser positivo e limite fica entre 0,00 e 100,00 inclusive | Convenções das features anteriores | 🟡 |
| Usabilidade | Interface funcional a partir de 360 px; alertas não bloqueiam consulta ou formulários; reconexão informa lacuna de cobertura | Persona e spec seção 8 | 🟡 |
| Testabilidade | Provedor substituível por fixture determinística; relógio e ciclos controláveis nos testes | Porta `QuoteReader` já existente | 🟢 |

## 7. Critérios de Aceitação

```gherkin
Cenário: CA-01 Cadastro e manutenção de vários alvos (RF-01)
  Dado um ativo do catálogo
  Quando Denis cria alvos de compra 90 e venda 120 em USD
  Então ambos ficam ativos e independentes
  Quando desativa o alvo 90
  Então somente o alvo 120 participa do ciclo seguinte

Cenário: CA-02 Configuração global (RF-02)
  Dado que ainda não existe configuração
  Então o limite vigente é 10,00%
  Quando Denis altera para 7,50%
  Então o ciclo seguinte registra e usa 7,50%
  E valores abaixo de 0% ou acima de 100% são rejeitados sem alterar o vigente

Esquema do Cenário: CA-03 Distância e borda (RF-03, RF-04)
  Dado alvo ativo de USD 100 e limite 10,00%
  Quando a cotação válida é <cotação>
  Então a distância é <distância> e o resultado é <resultado>
  Exemplos:
    | cotação | distância | resultado |
    | 90      | 10,00%    | dentro    |
    | 110     | 10,00%    | dentro    |
    | 89,99   | 10,01%    | fora      |

Cenário: CA-04 Repetição, saída e retorno (RF-06, RF-07)
  Dado alvo 100 com limite 10% e aplicação aberta
  Quando três ciclos válidos retornam 95, 96 e 97
  Então três notificações são exibidas para esse alvo
  Quando o ciclo seguinte retorna 80
  Então nenhuma notificação é exibida nesse ciclo
  Quando outro ciclo retorna 95
  Então a notificação volta a ser exibida

Cenário: CA-05 Uma cotação e vários alvos (RF-01, RF-08)
  Dado dois alvos ativos do mesmo ativo dentro da faixa
  Quando ocorre um ciclo válido
  Então o provedor é consultado uma vez para o ativo
  E duas avaliações e duas notificações identificáveis são registradas

Cenário: CA-06 Ciclo e cadência (RF-05)
  Dado aplicação aberta, conectada e sessão autenticada
  Quando o acompanhamento permanece ativo por pelo menos três ciclos
  Então os ciclos são programados em intervalos de 300 segundos
  E a validação usa relógio controlado para verificar três ciclos sucessivos
  Quando a aplicação fecha
  Então novos ciclos deixam de ser exigidos

Cenário: CA-07 Provedor falha (RF-08, RF-09, RF-10)
  Dado uma última cotação válida visível
  Quando o provedor excede timeout, quota ou retorna preço inválido
  Então o ciclo e a falha são registrados sem segredo
  E nenhum alerta é exibido com a cotação antiga
  E a última cotação permanece identificada como desatualizada

Cenário: CA-08 Reconexão sem retroatividade (RF-05, RF-08)
  Dado que a aplicação perdeu conexão durante o acompanhamento
  Quando a conexão retorna
  Então a interface informa que o intervalo não foi coberto
  E os ciclos futuros recomeçam sem fabricar avaliações para o período perdido

Cenário: CA-09 Cotação alimenta carteira e alocação (RF-09)
  Dado cotação válida de USD 180 para um ativo com posição
  Quando Denis consulta carteira e rebalanceamento
  Então ambos usam USD 180 com o mesmo instante e fonte
  E USDT permanece em USD 1,00 sem chamada externa

Cenário: CA-10 Privacidade e manutenção atômica (RF-01, RF-02, RF-11)
  Dado requisição anônima ou de usuário diferente de Denis
  Quando tenta consultar ou alterar alvos, configuração, avaliações ou notificações
  Então nenhum dado é retornado ou alterado
  Dado uma alteração válida cuja persistência falha
  Então a versão anterior permanece íntegra

Cenário: CA-11 Central de notificações (RF-11)
  Dado alertas exibidos numa sessão
  Quando Denis abre a central sem sair da página
  Então consulta cada alerta sem bloquear o uso e pode marcá-lo como lido
  Quando Denis fecha e reabre a aplicação autenticada
  Então notificações e avaliações com menos de 30 dias continuam acessíveis
  E registros com 30 dias completos deixam de aparecer e são removidos pela limpeza automática
  E a limpeza não remove alvos, configuração ou operações da carteira

Cenário: CA-12 Cobertura do catálogo (RF-10)
  Dado um novo ativo cadastrado sem posição e com alvo ativo
  Quando o ativo possui identificação válida no provedor
  Então sua cotação é incluída no próximo ciclo de acompanhamento
  Quando outro ativo não tem cobertura ou tem identificação ambígua
  Então a interface informa indisponibilidade e não gera alerta para ele
  E os ativos com cotação válida continuam sendo avaliados
```

## 8. Prioridade MoSCoW

| Item | MoSCoW | Justificativa |
|---|---|---|
| RF-01 a RF-10 | Must | Entregam o monitoramento e a confiabilidade mínima |
| RF-11 | Should | Mantém os alertas consultáveis sem alterar sua entrega |
| Segurança, latência, observabilidade e precisão | Must | Protegem estratégia e evitam alerta falso ou tardio |
| Push, e-mail, SMS e monitoramento com aplicação fechada | Won't | Fora da primeira versão por decisão explícita |
| Execução ou recomendação de ordens | Won't | A decisão continua com Denis |

## 9. Esclarecimentos

### Sessão 2026-09-27

- **Q:** Quais ativos precisam de cotação no primeiro uso?
  **R:** “Todos”. Interpretação operacional explicitada em RN-13: todos os cadastrados, incluindo novos ativos. A seleção da API gratuita fica para investigação técnica, sem presumir cobertura universal.
- **Q:** Qual intervalo de atualização com a aplicação aberta?
  **R:** “2 a)” — 5 minutos.
- **Q:** Por quanto tempo guardar notificações e avaliações?
  **R:** “3 a)” — 30 dias, com limpeza automática.

As respostas resolvem as escolhas de produto de L-01, L-02 e L-03. A seleção e validação da API continuam como trabalho técnico obrigatório de planejamento, não como decisão já comprovada.

## 10. Lacunas

Nenhuma pergunta de produto pendente. O planejamento deverá verificar cobertura, identificadores, quota gratuita, atribuição e política de uso do provedor; dimensionar consultas em lote para 5 minutos e definir a rotina de limpeza. Se nenhum provedor gratuito atender à cobertura e à frequência solicitadas, apresentar a limitação antes de alterar esses requisitos.

## 11. Histórico de alterações

| Data | Alteração | Autor |
|---|---|---|
| 2026-09-27 | Versão inicial baseada na spec e nos adendos vigentes das Features 001 e 002 | reversa-requirements |
| 2026-09-27 | Três respostas incorporadas: catálogo completo, ciclos de 5 minutos e histórico de 30 dias; cobertura da API encaminhada à investigação técnica | reversa-clarify |
