# Pre-Spec, carteira-crypto

> Selo 🟡 PLANEJADO. Insumo de entrada para o próximo pipeline, não é uma spec.

## Problema
🟡 Durante a semana, Denis precisa perceber a aproximação das cotações aos alvos do consultor e enxergar preço médio, ganhos, perdas e desvios da alocação recomendada a tempo de decidir sobre compras e vendas.

## Caminho escolhido
🟡 Construir um aplicativo pessoal focado, com entrada manual de movimentações, alvos e percentuais, atualização periódica de cotações, visão consolidada da carteira e alertas observáveis.

## Escopo mínimo da primeira entrega
🟡 Permitir que Denis cadastre manualmente uma amostra pequena de ativos, movimentações, alvos de compra e venda e percentuais recomendados; consultar cotações em uma API gratuita; exibir posição, preço médio ponderado, ganhos e perdas e desvio de alocação; detectar a proximidade dos alvos; e enviar alertas por um único canal, registrando a hora da cotação, da detecção e da entrega para medir a confiabilidade.

## Não-objetivos
🟡 Integração automática com corretoras, execução de ordens e suporte a múltiplos usuários não entram na primeira entrega.

## Restrições ativas
🟡 A aplicação deve ter consumo mínimo de recursos computacionais.

🟡 As cotações devem vir de API externa gratuita, respeitando sua cobertura, frequência e limites.

🟡 Uso pessoal por um único usuário, com movimentações, alvos e percentuais inseridos manualmente na primeira entrega.

## Critério de pronto
🟡 Com uma amostra conhecida de ativos e movimentações cadastrada, a aplicação exibe posição, preço médio ponderado, ganhos e perdas e desvio entre alocação atual e recomendada; quando uma cotação entra na faixa de proximidade de um alvo, registra o evento e entrega a notificação pelo canal escolhido em até 30 minutos, inclusive durante o período de teste acordado.

## Premissa a validar primeiro
🟡 Uma API gratuita, uma rotina leve de monitoramento e um canal de notificação conseguem entregar alertas úteis em até 30 minutos. O teste barato consiste em monitorar poucos ativos durante alguns dias, registrar latência e indisponibilidade e simular alvos atingidos e falhas da API com o aplicativo fechado.

## Riscos herdados
🟡 Dependência da disponibilidade, cobertura e limites de uma API externa gratuita e de um serviço de notificação.

🟡 Alertas atrasados, ausentes ou duplicados sem observabilidade e recuperação de falhas.

🟡 Cálculos incorretos caso movimentações, taxas, vendas, transferências e moedas sejam modeladas de forma incompleta.

🟡 Dados financeiros sensíveis expostos em armazenamento, registros técnicos, cópias ou notificações.

🟡 Abandono por excesso de manutenção manual de movimentações, alvos e percentuais.

🟡 Crescimento do consumo computacional causado por consultas excessivas, histórico ou rotinas de monitoramento ineficientes.

## Dúvidas abertas
- [DÚVIDA] 🟡 Como definir "próximo do alvo": percentual fixo, valor absoluto, faixa configurável por ativo ou outra regra?
- [DÚVIDA] 🟡 Qual será o único canal de notificação da primeira entrega, e ele precisa funcionar com o aplicativo fechado?
- [DÚVIDA] 🟡 Quais tipos de movimentação, taxas, transferências e moedas entram nos cálculos de preço médio, ganhos e perdas?
- [DÚVIDA] 🟡 Ganhos e perdas devem distinguir resultados realizados e não realizados já na primeira entrega?
- [DÚVIDA] 🟡 Qual API gratuita cobre todos os ativos e a moeda de referência da carteira dentro do limite de 30 minutos?
- [DÚVIDA] 🟡 Qual limite mensurável de CPU, memória, armazenamento ou custo define o consumo mínimo de recursos computacionais?
- [DÚVIDA] 🟡 Qual conjunto de exemplos conhecidos será usado para confirmar que preço médio, resultados e alocação estão corretos?
- [DÚVIDA] 🟡 Por quantos dias e com quantos eventos o teste de alertas precisa operar para ser considerado confiável?

---
Gerado por reversa-pre-spec em 2026-09-27T17:35:08.0869728-03:00
Sessão: 001-carteira-crypto
Destino sugerido: /reversa-new
