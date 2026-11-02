# Requirements: Agente de consulta da carteira no Telegram

> Identificador: `004-agente-telegram`
> Data: `2026-11-01`
> Pasta da extração reversa: `_reversa_sdd/`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA / DÚVIDA

## 1. Resumo executivo

Denis consulta e atualiza a carteira pelo celular fora do painel web. Esta feature entrega um agente que conversa com ele, em linguagem natural, por texto ou voz no Telegram pessoal do telefone dele. O agente só responde quando Denis manda uma mensagem e executa as funções já existentes da carteira: patrimônio total, resultado atual, lista de criptomoedas, saldo de um ativo, inclusão de lançamento realizado e verificação de alarme de alvo. O agente não executa ordem de mercado, não decide investimento e não envia aviso por conta própria.

## 2. Contexto a partir do legado

Não existem `architecture.md` nem `domain.md` na extração. A leitura vigente vem das specs em `_reversa_sdd/sdd/`, do inventário de 2026-11-01 e dos adendos vigentes das features 001, 002 e 003. O pedido cita o Sandeclaw só como referência de estilo; este repositório não documenta esse agente.

| Fonte | Trecho relevante | Confidência |
|-------|------------------|-------------|
| `_reversa_sdd/inventory.md#módulos-identificados` | A carteira já expõe auth, ledger, monitoramento, dashboard e leitura com IA. | 🟢 |
| `_reversa_sdd/inventory.md#integrações-externas` | Persistência em PostgreSQL/Supabase; cotações e Gemini já existem. Telegram ainda não é integração da aplicação. | 🟢 |
| `_reversa_sdd/prd.md#5-não-objetivos-out` | Sem execução de ordens, sem múltiplos usuários e sem decisão automática. | 🟡 |
| `_reversa_sdd/prd.md#6-restrições` | Um único usuário, uso frequente pelo celular, dados só para o autorizado. | 🟡 |
| `_reversa_sdd/prd.md#7-dependências-externas` | Canal de notificação/mensagem era indefinido no PRD; esta feature fixa o Telegram como canal do agente. | 🟡 |
| `_reversa_sdd/personas.md#persona-1-denis` | Denis acompanha a carteira pelo celular e registra só operação realizada. | 🟡 |
| `_reversa_sdd/sdd/operacoes-posicao-carteira.md#6-requisitos-funcionais` | Posição, caixa USDT, totais e recálculo só após lançamento persistido. | 🟡 |
| `_reversa_sdd/sdd/operacoes-posicao-carteira.md#12-segurança-e-privacidade` | Acesso exige identidade do único usuário. | 🟡 |
| `_reversa_sdd/sdd/painel-movel-carteira.md#6-requisitos-funcionais` | Painel mostra saldo total, caixa, posição por ativo e estado dos alvos. | 🟡 |
| `_reversa_sdd/sdd/monitoramento-precos-alertas.md#6-requisitos-funcionais` | Alvos de compra e venda geram aviso; o agente consulta esses avisos, não cria um motor paralelo. | 🟡 |
| `_reversa_sdd/addenda/001-operacoes-posicao-carteira.md#vigência` | Núcleo contábil e painel web já entregues. | 🟢 |
| `_reversa_sdd/addenda/003-monitoramento-precos-alertas.md#atualização-2026-11-01` | Monitoramento, painel autenticado e alertas estão em uso; provas formais restantes foram dispensadas. | 🟢 |

Leitura vigente no painel, para a mesma carteira:

- Patrimônio total é o saldo em USD quando as cotações necessárias estão completas; senão a visão é parcial.
- Resultado atual é ganho de capital (não realizado) somado ao realizado líquido.
- Cada ativo tem quantidade, valor em USD e demais campos da posição.
- Lançamento novo entra pelos mesmos tipos já aceitos: compra, venda, depósito, saque, transferência e taxa.
- No painel, notificação de monitoramento e coluna Sinal (Comprar, Vender, Aguardar) continuam existindo. No Telegram, a verificação pedida por Denis devolve notificação ainda não lida e alarme identificado naquele instante. Sem nenhum dos dois, a resposta é que não existem alvos atingidos no momento.

## 3. Personas e cenários de uso

| Persona | Objetivo | Cenário-chave |
|---------|----------|---------------|
| Denis | Conferir patrimônio, resultado e saldo sem abrir o painel | Fala ou escreve em linguagem natural no Telegram do próprio telefone e recebe os mesmos totais que o painel autenticado mostraria naquele instante. |
| Denis | Registrar uma operação já feita | Envia o lançamento por texto ou voz. Data e hora omitidas usam o instante da mensagem. Campo faltante vira pergunta e a posição só muda depois que o ledger aceita o lançamento completo. |
| Denis | Saber se há alarme de alvo | Pede a verificação. O agente responde na hora com alarme não lido ou identificado, ou informa que não existem alvos atingidos no momento. |

O consultor continua fora do produto. Terceiros que falarem com o agente não recebem dado financeiro.

## 4. Regras de negócio novas ou alteradas

1. **RN-01 🟢:** O agente executa somente as funções pedidas sobre a carteira já persistida. Ele não cria um segundo livro, não recalcula posição por conta própria e não substitui o painel web.
   - Origem no legado: `_reversa_sdd/sdd/operacoes-posicao-carteira.md#6-requisitos-funcionais`
   - Tipo: nova
2. **RN-02 🟢:** Somente um lançamento efetivamente realizado e aceito pelo ledger altera a posição. Intenção, cotação ou conversa no Telegram não viram operação.
   - Origem no legado: `_reversa_sdd/sdd/operacoes-posicao-carteira.md#1-resumo`
   - Tipo: nova (canal novo, mesma regra)
3. **RN-03 🟢:** Consultas de patrimônio, resultado, lista e saldo devolvem os valores do snapshot autenticado da carteira. Cotação ausente não vira zero; totais dependentes ficam parciais, como no painel.
   - Origem no legado: `_reversa_sdd/sdd/operacoes-posicao-carteira.md#6-requisitos-funcionais` RF-09 e RF-10
   - Tipo: nova
4. **RN-04 🟢:** O canal é o Telegram pessoal de Denis, no telefone dele. Texto e voz enviados por essa conta são executados. Mensagem de outra conta não devolve patrimônio, resultado, posição, alerta nem confirmação de lançamento.
   - Origem no legado: `_reversa_sdd/prd.md#5-não-objetivos-out` e `_reversa_sdd/sdd/operacoes-posicao-carteira.md#12-segurança-e-privacidade`
   - Tipo: nova
5. **RN-05 🟡:** O agente não envia ordem de compra ou venda a corretora, não recomenda investimento e não substitui o julgamento de Denis.
   - Origem no legado: `_reversa_sdd/prd.md#5-não-objetivos-out`
   - Tipo: nova
6. **RN-06 🟢:** A verificação de alarme só ocorre quando Denis pede. O agente devolve notificação de monitoramento ainda não lida e alarme identificado naquele instante, com o ativo. Se não houver nenhum, responde que não existem alvos atingidos no momento. O agente não envia essa verificação sozinho.
   - Origem no legado: `_reversa_sdd/sdd/monitoramento-precos-alertas.md#6-requisitos-funcionais` e adendo 003
   - Tipo: nova

## 5. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de aceite | Confidência |
|----|-----------|------------|--------------------|-------------|
| RF-01 | O agente entende linguagem natural em texto ou voz no Telegram pessoal de Denis e responde no mesmo diálogo, somente depois de uma mensagem dele. | Must | Uma frase ou um áudio autorizado produz uma resposta no Telegram. Sem mensagem de Denis, o agente não envia aviso. O painel web permanece utilizável se o agente estiver parado. | 🟢 |
| RF-02 | O agente consulta o patrimônio total da carteira. | Must | A resposta traz o saldo total em USD do snapshot da carteira, ou indica visão parcial quando o total não está completo. | 🟢 |
| RF-03 | O agente consulta o resultado atual. | Must | A resposta traz o resultado como ganho de capital somado ao realizado líquido, ou indica visão parcial se um dos dois faltar. | 🟢 |
| RF-04 | O agente traz a lista de criptomoedas da carteira. | Must | A lista cobre os ativos com posição ou percentual vigente, com símbolo identificável, sem inventar ativo. | 🟢 |
| RF-05 | O agente consulta o saldo de uma criptomoeda específica. | Must | Pedido com símbolo cadastrado devolve quantidade e valor em USD daquele ativo; símbolo inexistente informa que o ativo não está na carteira. | 🟢 |
| RF-06 | O agente inclui um lançamento realizado a partir de texto ou voz. | Must | Lançamento completo e aceito pelo ledger entra no histórico, recalcula a posição e aparece no painel. Data e hora omitidas usam o instante da mensagem. | 🟢 |
| RF-07 | O agente verifica, quando Denis pede, se há alarme de alvo de compra ou venda. | Must | A verificação roda no momento do pedido. Havendo notificação não lida ou alarme identificado, a resposta traz o ativo e o alarme. Sem nenhum dos dois, a resposta informa que não existem alvos atingidos no momento. | 🟢 |
| RF-08 | O agente executa texto e voz somente da conta Telegram pessoal de Denis. | Must | Comando de voz ou texto dessa conta é executado. Mensagem de outra conta não contém valor financeiro, lista de ativos, alerta nem confirmação de lançamento. | 🟢 |
| RF-09 | O agente completa a data omitida e pergunta o que mais faltar antes de gravar. | Must | Sem data e hora, o lançamento usa o instante da mensagem. Falta de tipo, ativo, quantidade, preço exigido ou outro campo obrigatório gera uma pergunta e não grava a operação. Lançamento completo e inválido para o ledger também não altera saldo. | 🟢 |
| RF-10 | O agente não executa operação de mercado. | Must | Nenhum pedido de consulta ou lançamento dispara compra, venda, depósito ou saque em corretora. | 🟢 |

## 6. Requisitos Não Funcionais

| Tipo | Requisito | Evidência ou justificativa | Confidência |
|------|-----------|----------------------------|-------------|
| Segurança | Só o remetente autorizado lê e altera a carteira por este canal. Credencial do Telegram e dados financeiros não aparecem em registro técnico desnecessário. | `_reversa_sdd/sdd/operacoes-posicao-carteira.md#12-segurança-e-privacidade` e `_reversa_sdd/prd.md#6-restrições` | 🟡 |
| Integridade | Lançamento pelo Telegram obedece às mesmas regras de saldo não negativo, USDT como caixa e recálculo cronológico do ledger. | `_reversa_sdd/sdd/operacoes-posicao-carteira.md#7-requisitos-não-funcionais` | 🟢 |
| Precisão | Valores monetários apresentados em USD seguem a precisão de apresentação já usada no painel, sem arredondar o cálculo interno para duas casas. | `_reversa_sdd/sdd/operacoes-posicao-carteira.md#7-requisitos-não-funcionais` RNF-01 | 🟡 |
| Disponibilidade | Falha do Telegram não impede o uso do painel web nem corrompe lançamentos já gravados. | `_reversa_sdd/prd.md#6-restrições` (canal extra, não substituto) | 🟡 |
| Observabilidade | Recusa de remetente, lançamento rejeitado e consulta parcial deixam um resultado observável para Denis na conversa, sem vazar saldo a terceiro. | `_reversa_sdd/sdd/monitoramento-precos-alertas.md#6-requisitos-funcionais` RF-09 | 🟡 |
| Escopo de canal | Esta entrega usa somente o Telegram. Outro aplicativo de mensagem fica fora. | Pedido desta feature e `_reversa_sdd/prd.md#7-dependências-externas` | 🟡 |

## 7. Critérios de Aceitação

```gherkin
Cenário: consultar patrimônio total
  Dado que Denis está autorizado no Telegram
  E a carteira possui snapshot autenticado
  Quando ele pede o patrimônio total
  Então o agente responde com o saldo total em USD desse snapshot
  E se o total estiver incompleto a resposta indica visão parcial

Cenário: consultar resultado atual
  Dado que Denis está autorizado no Telegram
  Quando ele pede o resultado atual
  Então o agente responde com a soma do ganho de capital e do realizado líquido
  E se um desses valores faltar a resposta indica visão parcial

Cenário: listar criptomoedas
  Dado que a carteira tem ao menos um ativo com posição ou percentual vigente
  Quando Denis pede a lista de criptomoedas
  Então o agente lista os símbolos existentes
  E não inclui ativo que a carteira não possui

Cenário: consultar saldo de um ativo
  Dado que BTC está cadastrado na carteira
  Quando Denis pede o saldo de BTC
  Então o agente responde com a quantidade e o valor em USD de BTC

Cenário: ativo inexistente na consulta de saldo
  Dado que XYZ não está cadastrado na carteira
  Quando Denis pede o saldo de XYZ
  Então o agente informa que o ativo não está na carteira
  E não cria o ativo

Cenário: incluir lançamento válido sem data
  Dado que Denis envia por texto ou voz um lançamento com tipo, ativo cadastrado, quantidade e demais campos exigidos, sem data e hora
  Quando o ledger aceita a operação
  Então a data e a hora do lançamento são as da mensagem
  E a operação aparece no histórico
  E o patrimônio e o saldo daquele ativo passam a refletir o recálculo

Cenário: lançamento com campo faltando além da data
  Dado que Denis pede um lançamento sem quantidade, ativo, tipo ou preço exigido
  Quando o agente lê a mensagem
  Então ele pergunta o dado que falta
  E não grava a operação até a resposta completar os campos

Cenário: incluir lançamento inválido
  Dado que o lançamento completo venderia mais quantidade do que a posição possui
  Quando Denis pede para incluir esse lançamento
  Então o agente recusa
  E a posição permanece igual

Cenário: verificar alarme quando existe
  Dado que Denis pede a verificação de alarme de alvo
  E existe notificação de monitoramento ainda não lida ou alarme identificado
  Quando o agente executa a verificação naquele momento
  Então a resposta traz o ativo e o alarme

Cenário: verificar alarme quando não existe
  Dado que Denis pede a verificação de alarme de alvo
  E não há notificação não lida nem alarme identificado
  Quando o agente executa a verificação
  Então a resposta informa que não existem alvos atingidos no momento

Cenário: agente não fala sozinho
  Dado que surge um alarme de alvo
  E Denis não enviou mensagem
  Quando o tempo passa
  Então o agente não envia mensagem no Telegram

Cenário: remetente que não é a conta pessoal
  Dado que uma conversa no Telegram não é a conta pessoal de Denis
  Quando essa conversa pede o patrimônio total
  Então o agente não devolve valor financeiro
  E não registra lançamento

Cenário: pedido de execução em corretora
  Dado que Denis pede ao agente para comprar um ativo na corretora
  Quando o agente interpreta o pedido
  Então ele não envia ordem a corretora
  E informa que só registra lançamento já realizado ou consulta a carteira
```

## 8. Prioridade MoSCoW

| Item | MoSCoW | Justificativa |
|------|--------|---------------|
| RF-01 | Must | Sem diálogo no Telegram a feature não existe. |
| RF-02 | Must | Pedido explícito: consultar o patrimônio total. |
| RF-03 | Must | Pedido explícito: consultar o resultado atual. |
| RF-04 | Must | Pedido explícito: trazer a lista de criptomoedas. |
| RF-05 | Must | Pedido explícito: saldo de um ativo específico. |
| RF-06 | Must | Pedido explícito: incluir um novo lançamento. |
| RF-07 | Must | Pedido explícito: consultar alarme de alvo de compra ou venda. |
| RF-08 | Must | A carteira é de um único usuário e contém dados financeiros. |
| RF-09 | Must | Lançamento inválido não pode corromper quantidade nem caixa. |
| RF-10 | Must | Continua fora do produto executar ordem de mercado. |
| RNF de segurança | Must | Terceiro no Telegram não pode ler a carteira. |
| RNF de disponibilidade | Should | O painel web já cobre o uso diário se o Telegram falhar. |

Fora desta entrega: cadastrar ativo novo, alterar alvo, alterar alocação, exportar CSV, abrir o painel web pelo Telegram e enviar aviso sem Denis ter perguntado.

## 9. Esclarecimentos

### Sessão 2026-11-01

- **Q:** Como Denis conversa com o agente no Telegram?
  **R:** Linguagem natural, por exemplo “quanto está o patrimônio?” ou “saldo do BTC”.
- **Q:** O agente pode falar sem Denis perguntar?
  **R:** Só responde quando Denis manda mensagem.
- **Q:** Como o Telegram reconhece Denis como único autorizado?
  **R:** O Telegram é particular do telefone de Denis. Somente ele tem acesso, e qualquer comando enviado por voz ou mensagem deve ser executado.
- **Q:** O que o agente deve devolver em “tem alarme de alvo de compra ou venda?”
  **R:** A verificação é executada no momento do pedido. Se houver alarme não lido ou algum alarme identificado, o agente devolve esse resultado. Caso contrário, informa que não existem alvos atingidos no momento.
- **Q:** Ao incluir um lançamento pelo Telegram, o agente grava na hora?
  **R:** Se a data e a hora não forem informadas, usa a data e a hora da mensagem. Se faltar qualquer outra informação, o agente devolve uma pergunta para completar o lançamento.

## 10. Lacunas

Nenhuma lacuna aberta.

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-11-01 | Versão inicial gerada por `/reversa-requirements` | reversa |
| 2026-11-01 | Esclarecimentos da sessão integrados; dúvidas de conversa, autorização, alarme e lançamento fechadas | reversa-clarify |
