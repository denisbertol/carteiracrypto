# Primeiro teste: Agente de consulta da carteira no Telegram

> Identificador: `004-agente-telegram`
> Data: `2026-11-01`

## Antes

1. A carteira web sobe e o login de Denis abre o painel, com patrimônio e pelo menos um ativo.
2. A leitura com IA do painel já tem chave válida. Sem essa chave, texto e voz não são interpretados.
3. No BotFather, crie um bot pessoal e copie o token. Não commite o token.
4. Coloque o token só na configuração do servidor. Sem token, o agente fica desligado e o painel continua igual.

## Conversa

1. No Telegram do seu telefone, abra o bot e envie: “qual o patrimônio total?”
2. Compare o número com o card Patrimônio total do painel. Se o painel disser parcial, a resposta também indica visão parcial.
3. Envie: “qual o resultado atual?” e compare com o card Resultado.
4. Envie: “lista as criptomoedas” e confira os símbolos com a tabela.
5. Envie: “saldo do BTC”. Quantidade e valor batem com a linha do BTC. Um símbolo que não existe responde que o ativo não está na carteira.
6. Envie um áudio pedindo o saldo de outro ativo que você tenha. A resposta usa a transcrição e os mesmos números da tabela.
7. Envie: “comprei 0,01 de BTC a 78000”. Sem data, a operação fica com o instante dessa mensagem. Confira no histórico do painel.
8. Envie: “comprei BTC”. O agente pergunta quantidade e preço e não cria lançamento até você responder.
9. Envie: “tem alarme de alvo?”. Com aviso não lido ou sinal Comprar ou Vender, a resposta cita o ativo. Sem isso, diz que não existem alvos atingidos no momento. O aviso no painel continua não lido.
10. Deixe passar um alvo sem mandar mensagem. O Telegram não recebe aviso sozinho.
11. De outro telefone ou outra conta, mande “patrimônio”. A resposta não traz valor.

## Recuo

Apague o token da configuração e reinicie. O painel e os lançamentos já gravados permanecem. O consumidor do Telegram não inicia.
