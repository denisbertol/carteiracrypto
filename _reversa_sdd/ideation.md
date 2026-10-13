# Ideation, carteira-crypto

> Selo 🟡 PLANEJADO em todos os itens, sujeito a validação.

## Brief original
Quero criar o "carteira crypto" para registrar ativos, atualizar o preço médio ponderado e gerenciar metas de realização e compra. Quero incluir os alvos no meu gerenciador e ser notificado assim que estiver próximo. A atualização das cotações podem ser feitas em intervalos suportados por apis externas, gratuitas.

## Problema
🟡 Denis tem dificuldade para acompanhar, durante a semana, a aproximação das cotações aos alvos de compra e venda fornecidos semanalmente pelo consultor. Isso pode fazê-lo perder oportunidades previstas nesses alvos.

🟡 Também tem dificuldade para visualizar o preço médio ponderado, apurar ganhos e perdas e comparar a distribuição atual da carteira com os percentuais indicados pelo consultor. Pode fornecer o histórico das movimentações para os cálculos.

## Valor entregue
🟡 Perceber a proximidade dos alvos e compreender preço médio, ganhos, perdas e desvios de alocação para decidir a tempo com base nas orientações do consultor.

## Alternativas existentes
🟡 Planilha automatizada com alertas: 17 pontos, empatada com o aplicativo escolhido. Oferece menor esforço inicial, mas a decisão favoreceu o controle conjunto de cálculos, alocação e diagnóstico dos alertas no aplicativo.

🟡 Usar algo pronto: 17 pontos, também empatado. Os candidatos registrados no brainstorm são Delta, CoinStats e CoinMarketCap Portfolio; a aderência às regras pessoais, limites gratuitos e exportação ainda exige validação. Não houve prova de que sejam inadequados.

🟡 Assistente integrado a corretoras e carteiras: 13 pontos. A maior complexidade de integrações e reconciliação reduziu sua pontuação em esforço e risco residual.

🟡 Não construir, combinando controles manuais e alertas existentes: 16 pontos. Sua menor aderência ao objetivo mantém parte do trabalho e da dificuldade de acompanhamento com Denis.

🟡 Caminho escolhido por Denis: aplicativo pessoal focado, 17 pontos, aceitando o maior esforço inicial e a responsabilidade de manter seu funcionamento. O empate foi preservado; a escolha não demonstra confiabilidade já comprovada.

## Público-alvo (bruto)
🟡 Denis, único usuário, acompanha uma carteira de criptoativos e recebe de um consultor alvos de compra e venda e percentuais desejados de alocação. O consultor é fonte das orientações, sem acesso previsto ao produto.

## Métricas de sucesso
🟡 Tempo entre a cotação entrar na faixa de proximidade e o recebimento do alerta: no máximo 30 minutos. A regra da faixa, a forma de medir a entrada e o período de avaliação ainda precisam ser definidos.

🟡 Consumo computacional baixo é uma restrição confirmada; limites de CPU, memória, armazenamento e ambiente de medição permanecem [INDEFINIDO, validar com usuário].

🟡 A visualização de cálculos verificáveis e de desvios de alocação faz parte do resultado esperado. Exemplos de referência, tolerâncias e metas de cobertura dos alertas permanecem [INDEFINIDO, validar com usuário].

## Premissas a validar
🟡 Uma fonte gratuita de cotações e um canal de notificação conseguem cumprir o prazo de 30 minutos para os ativos acompanhados. Validar com poucos ativos durante alguns dias, medindo atrasos e falhas e simulando eventos; o teste ainda não foi executado.

🟡 O histórico fornecido e as regras de cálculo permitem obter preço médio, ganhos, perdas e alocação verificáveis. Validar operações representativas, incluindo os tipos de eventos, taxas e moedas que forem definidos para o escopo.

🟡 A atualização manual de movimentações, alvos e percentuais é sustentável para Denis, e a aplicação consegue operar com baixo consumo computacional. Os limites aceitáveis de trabalho manual e recursos ainda não foram quantificados.

## Notas
🟡 Modo guiado confirmado por Denis. Síntese reaproveitada confirmada explicitamente nesta conversa.

🟡 Fora da primeira entrega por declaração do usuário: integração automática com corretoras, execução de ordens e múltiplos usuários.

🟡 A primeira fatia proposta na pré-especificação usa cadastro manual, poucos ativos e um canal de notificação, reunindo cálculos da carteira e acompanhamento dos alvos. O formato definitivo de entrada das movimentações continua aberto.

🟡 As oito dúvidas da pré-especificação continuam abertas: regra de proximidade; canal e funcionamento com o aplicativo fechado; operações, taxas, transferências e moedas; resultados realizados e não realizados; cobertura da API gratuita; limites de recursos computacionais; exemplos para validar cálculos; duração e volume do teste de confiabilidade.

🟡 Preservar dados financeiros e permitir exportação são preocupações herdadas da decisão. Se a prova de alertas não atender ao prazo, a recomendação de construir deve ser reavaliada conforme o critério registrado em decision.md.

---
Gerado por reversa-ideator em 2026-09-27T17:39:58.1958809-03:00
Fonte: newproject-brief.md
Sessão de ideação reaproveitada: 001-carteira-crypto
Âncoras: brainstorms/001-carteira-crypto/framing.md, decision.md e pre-spec.md
