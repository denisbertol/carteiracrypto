# Roadmap: Agente de consulta da carteira no Telegram

> Identificador: `004-agente-telegram`
> Data: `2026-11-01`
> Requirements: `_reversa_forward/004-agente-telegram/requirements.md`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA

## 1. Resumo da abordagem

O agente entra no processo que já serve a carteira. Ele lê texto e voz do Telegram pessoal de Denis, entende o pedido em linguagem natural e chama os mesmos cálculos de patrimônio, resultado, posição e lançamento. Não nasce um segundo livro.

A voz vira texto antes da interpretação. Data e hora omitidas num lançamento usam o instante da mensagem. Qualquer outro campo obrigatório ausente gera uma pergunta e fica pendente até a resposta; nada é gravado antes disso. A verificação de alarme só roda quando Denis pede: devolve notificação ainda não lida e alarme identificado naquele instante, ou informa que não existem alvos atingidos.

Consulta não marca aviso como lido e não envia mensagem sem pedido. Mensagem de outra conta não recebe dado financeiro.

## 2. Princípios aplicados

Não existe `.reversa/principles.md` neste projeto. Nenhum princípio local foi avaliado e nenhum conflito foi registrado.

| Princípio | Como a feature se relaciona | Status |
|-----------|------------------------------|--------|
| n/a | Arquivo de princípios ausente | n/a |

## 3. Decisões técnicas

| ID | Decisão | Justificativa | Alternativas descartadas | Confidência |
|----|---------|----------------|--------------------------|-------------|
| D-01 | O agente roda dentro da aplicação existente e usa o dono já configurado da carteira. | A carteira é de um único usuário e os serviços de posição, lançamento e notificação já estão nesse processo. | Um serviço separado que chamaria a API com sessão de navegador. | 🟢 |
| D-02 | Um único consumidor busca as atualizações do Telegram no processo já em execução, com trava para não haver dois consumidores. | O uso local e o container pessoal não exigem um endereço público novo. Dois processos não podem gravar o mesmo lançamento. | Webhook público obrigatório; um processo de fila separado. | 🟡 |
| D-03 | Texto e voz passam pelo mesmo leitor já usado na carteira para material livre, devolvendo uma intenção estruturada. A voz é transcrita antes. | O requisito é linguagem natural, e a carteira já tem leitura de texto e imagem sem um segundo livro. | Lista fixa de comandos; um fornecedor novo só para fala. | 🟢 |
| D-04 | Lançamento aceito chama o mesmo registro de operação, com a chave de idempotência derivada da atualização do Telegram. | Repetir a mesma mensagem não pode duplicar quantidade nem caixa. | Gravar direto no banco à parte do ledger. | 🟢 |
| D-05 | Rascunho incompleto fica persistido por conversa até os campos faltantes chegarem. Data e hora ausentes usam o instante da mensagem e não entram no rascunho. | Reinício do processo não pode esquecer a pergunta já feita. | Memória só do processo; gravar lançamento parcial. | 🟢 |
| D-06 | Alarme identificado usa a mesma regra do sinal do painel: Vender quando o preço atinge o dobro do preço médio; Comprar quando a participação está abaixo da ideal e o preço está no alvo de compra. Aguardar não é alarme. Notificação com leitura vazia entra junto. A consulta não preenche a leitura. | O pedido pede alarme não lido ou identificado, e o painel já define o sinal. Marcar como lido esconderia o aviso no painel sem Denis ter lido lá. | Um terceiro critério de alarme; marcar a notificação como lida ao responder no Telegram. | 🟡 |
| D-07 | O segredo do bot fica só no servidor. A conta autorizada é a do Telegram pessoal de Denis. Outra conta recebe recusa sem números. | RF-08. O telefone particular não impede que outra conta fale com o bot se o nome dele for conhecido. | Confiar só no sigilo do nome do bot; pedir senha da carteira a cada mensagem. | 🟢 |

## 4. Premissas

Nenhuma. O `requirements.md` não tem marcador `[DÚVIDA]` aberto.

| Premissa | Origem (`requirements.md` seção) | Risco se errada |
|----------|----------------------------------|-----------------|
| n/a | n/a | n/a |

## 5. Delta arquitetural

Não existe `_reversa_sdd/architecture.md`. O delta aponta para o inventário e para as specs já citadas no requisito.

| Componente | Arquivo de origem no legado | Tipo de mudança | Resumo |
|------------|------------------------------|-----------------|--------|
| painel | `_reversa_sdd/inventory.md#módulos-identificados` | contrato-novo | O mesmo snapshot de patrimônio, resultado e posição passa a ser respondido no Telegram. O painel web não muda de regra. |
| ledger | `_reversa_sdd/sdd/operacoes-posicao-carteira.md#6-requisitos-funcionais` | contrato-alterado | Ganha um acesso por mensagem. A gravação continua no registro de operação já existente. |
| monitoring | `_reversa_sdd/sdd/monitoramento-precos-alertas.md#6-requisitos-funcionais` | contrato-novo | A verificação de alarme passa a ser sob demanda, sem ciclo novo e sem aviso espontâneo. |
| ai | `_reversa_sdd/inventory.md#módulos-identificados` | contrato-alterado | A leitura existente passa a aceitar fala e a devolver uma intenção da carteira, além de lançamentos e alvos do painel. |
| agente Telegram | n/a | componente-novo | Consumidor de mensagens, rascunho e respostas. Não calcula posição própria. |

## 6. Delta no modelo de dados

- Resumo das mudanças: a carteira ganha o vínculo da conta Telegram autorizada, o rascunho de lançamento incompleto e o registro da atualização já aplicada, para não gravar duas vezes. Posição, alvo e notificação permanecem como estão.
- Detalhe completo em: `_reversa_forward/004-agente-telegram/data-delta.md`

## 7. Delta de contratos externos

| Contrato | Tipo | Arquivo de detalhe |
|----------|------|--------------------|
| Telegram | HTTP | `_reversa_forward/004-agente-telegram/interfaces/telegram.md` |
| Leitura da intenção | HTTP | `_reversa_forward/004-agente-telegram/interfaces/intencao.md` |

O contrato HTTP já existente da carteira não muda para o navegador.

## 8. Plano de migração

1. Acrescentar o armazenamento do vínculo, do rascunho e da atualização aplicada, sem alterar lançamentos antigos.
2. Subir o consumidor somente quando o segredo do bot estiver configurado. Sem segredo, a carteira web segue igual.
3. Na primeira mensagem da conta pessoal, gravar o vínculo. Mensagem anterior a esse vínculo, se chegar de outra conta, é recusada.
4. Não há transformação de saldo, alvo ou notificação já gravados.

## 9. Riscos e mitigações

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|---------------|-----------|
| A mesma mensagem ser entregue duas vezes | alto | médio | Idempotência pela atualização do Telegram antes de gravar o lançamento. |
| Dois processos consumindo a mesma fila | alto | baixo | Trava única; o segundo consumidor não lê. |
| Voz transcrita com ativo ou quantidade errados | alto | médio | Campo ambíguo ou faltante vira pergunta; não grava até completar. |
| Outra conta descobrir o bot | alto | baixo | Recusa sem valor financeiro. |
| Interpretação tratar “comprar” como ordem de mercado | alto | médio | Fora de consulta e de lançamento realizado, a resposta explica o limite e não chama corretora. |
| Leitura indisponível | médio | médio | A mensagem informa a falha e não inventa saldo nem lançamento. |

## 10. Critério de pronto

- [ ] Todas as ações do `actions.md` marcadas `[X]`
- [ ] Texto e voz autorizados consultam patrimônio, resultado, lista, saldo e alarme com os mesmos números do painel
- [ ] Lançamento sem data usa o instante da mensagem; outro campo faltante pergunta e não grava
- [ ] Lançamento inválido para o ledger não muda a posição
- [ ] Sem mensagem de Denis, o agente não envia aviso
- [ ] Conta que não é a pessoal não recebe dado financeiro
- [ ] `cross-check.md` (se executado) sem CRITICAL nem HIGH
- [ ] `regression-watch.md` gerado
- [ ] Re-extração reversa executada e sem regressão vermelha (recomendado, não obrigatório)

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-11-01 | Versão inicial gerada por `/reversa-plan` | reversa |
