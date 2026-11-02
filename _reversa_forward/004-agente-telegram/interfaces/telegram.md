# Contrato: Telegram

> Identificador: `004-agente-telegram`
> Data: `2026-11-01`
> Direção: a aplicação chama a Bot API. Não há rota nova no navegador.

## Entrada

O consumidor único busca atualizações com offset maior que a última aplicada. Cada atualização traz identificador, conversa, texto ou arquivo de voz e o instante da mensagem.

Mensagem de conta diferente da vinculada:

- não chama snapshot, ledger nem leitura de saldo
- a resposta não contém número da carteira, símbolo com quantidade nem confirmação de lançamento

Áudio é baixado pelo identificador de arquivo informado na atualização. O arquivo só segue para a leitura de intenção. Não é gravado no histórico de operações.

## Saída

Uma mensagem de resposta por atualização tratada, na mesma conversa:

- consulta: patrimônio, resultado, lista, saldo ou alarme, em texto
- lançamento incompleto: uma pergunta nomeando o que falta
- lançamento aceito: confirmação com tipo, ativo, quantidade e data usada
- recusa do ledger: motivo, sem alterar saldo
- pedido fora do escopo: informa que só consulta a carteira ou registra lançamento já realizado

Timeout de cada chamada externa: 10 segundos, o mesmo teto já usado nas leituras de provedor da carteira. Falha de rede não grava lançamento e a resposta, se a conversa ainda estiver acessível, diz que a consulta não foi concluída.

Idempotência: o identificador da atualização é único. A segunda entrega da mesma atualização não cria outra operação e não faz outra pergunta.

O agente não chama `sendMessage` sem uma atualização nova de Denis.
