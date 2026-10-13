# Options, carteira-crypto

> Selo 🟡 PLANEJADO em todos os itens. Nenhuma opção foi escolhida ainda.

## Problema de referência
🟡 Quando acompanho minha carteira durante a semana, quero ser avisado da proximidade dos alvos de compra e venda e visualizar meu preço médio, ganhos, perdas e desvios da alocação recomendada, para agir a tempo com base nas orientações do consultor.

## Restrições ativas
🟡 Uso pessoal por um único usuário; alvos e percentuais são fornecidos pelo consultor; cotações devem vir de APIs externas gratuitas, respeitando os intervalos e limites suportados. Critério de proximidade, canal de notificação, formato das movimentações e regras detalhadas de cálculo ainda estão abertos.

---

## Opção A, planilha automatizada com alertas
- **Em uma frase:** 🟡 Manter movimentações, alvos e percentuais em uma planilha, com atualização periódica de cotações, cálculos e uma automação separada para enviar alertas.
- **Como resolve o problema:** 🟡 Centraliza preço médio, resultado e alocação em uma interface familiar, enquanto regras programadas sinalizam ativos próximos dos alvos.
- **Esforço:** 🟡 baixo, exige modelar a planilha, integrar uma fonte gratuita e configurar uma rotina de alerta.
- **Impacto no legado:** 🟡 Nenhum, contexto greenfield.
- **Reversibilidade:** 🟡 fácil, os dados tabulares podem ser exportados e reutilizados em outra solução.
- **O que precisa ser verdade para funcionar:** 🟡 A quantidade de operações, ativos e regras deve permanecer administrável em planilha, e a plataforma escolhida deve conseguir executar atualizações e alertas na frequência necessária.

## Opção B, aplicativo pessoal focado
- **Em uma frase:** 🟡 Construir uma aplicação web responsiva para cadastrar movimentações, alvos e alocações, calcular a carteira e emitir alertas de proximidade.
- **Como resolve o problema:** 🟡 Reúne em um painel próprio a posição, o preço médio, os ganhos e perdas, os desvios de alocação e a distância de cada cotação até os alvos.
- **Esforço:** 🟡 médio, requer interface, persistência, motor de cálculo, integração de cotações, agendamento e notificações.
- **Impacto no legado:** 🟡 Nenhum, contexto greenfield.
- **Reversibilidade:** 🟡 fácil, desde que movimentações, alvos e percentuais possam ser exportados em formato aberto.
- **O que precisa ser verdade para funcionar:** 🟡 Uma API gratuita deve cobrir os ativos e a moeda de referência, e deve existir um canal de notificação compatível com a operação em segundo plano.

## Opção C, assistente de carteira integrado
- **Em uma frase:** 🟡 Construir um sistema mais amplo que importe movimentações de corretoras ou carteiras, acompanhe múltiplas fontes de cotação e gere alertas e sugestões de rebalanceamento.
- **Como resolve o problema:** 🟡 Reduz a digitação manual, mantém a posição atualizada e combina metas de preço, resultado e alocação para apoiar decisões durante a semana.
- **Esforço:** 🟡 alto, envolve integrações heterogêneas, reconciliação de operações, regras financeiras, segurança e maior observabilidade.
- **Impacto no legado:** 🟡 Nenhum, contexto greenfield.
- **Reversibilidade:** 🟡 cara, porque integrações, modelos de dados e rotinas de reconciliação criam dependências maiores, embora a exportação reduza o custo de saída.
- **O que precisa ser verdade para funcionar:** 🟡 As corretoras ou carteiras usadas devem oferecer acesso seguro e suficiente aos dados, e os benefícios da automação devem justificar a manutenção das integrações.

---

## Opção sempre presente, não construir
- **Em uma frase:** 🟡 Usar uma planilha manual para posição e alocação, combinada com alertas configurados diretamente nas corretoras ou aplicativos já utilizados.
- **Como resolve o problema:** 🟡 Estabelece uma rotina semanal de atualização dos alvos e uma rotina de conferência da carteira, aproveitando notificações já disponíveis para reduzir oportunidades perdidas.
- **Esforço:** 🟡 baixo, demanda organização inicial e disciplina recorrente, sem desenvolvimento de software.
- **Impacto no legado:** 🟡 Nenhum, contexto greenfield.
- **Reversibilidade:** 🟡 fácil, o processo pode ser substituído gradualmente e os registros migrados.
- **O que precisa ser verdade para funcionar:** 🟡 As ferramentas atuais devem permitir alertas suficientes, e Denis deve manter movimentações, alvos e percentuais atualizados manualmente.

## Opção sempre presente, usar algo pronto
- **Em uma frase:** 🟡 Adotar um rastreador existente, como Delta, CoinStats ou CoinMarketCap Portfolio, e complementar manualmente o que faltar para os percentuais-alvo do consultor.
- **Como resolve o problema:** 🟡 Esses candidatos oferecem acompanhamento de carteira, preços e alertas; alguns também exibem ganhos, perdas e distribuição, reduzindo a necessidade de construir o núcleo do produto.
- **Esforço:** 🟡 baixo, exige avaliar cobertura, limites do plano gratuito, método de entrada das operações e aderência às regras pessoais.
- **Impacto no legado:** 🟡 Nenhum, contexto greenfield.
- **Reversibilidade:** 🟡 fácil, desde que a solução permita exportar os dados ou que se mantenha uma cópia das movimentações.
- **O que precisa ser verdade para funcionar:** 🟡 Pelo menos um candidato deve cobrir os ativos, cálculos, alertas e moeda de referência necessários; o controle de alocação recomendada pode exigir complemento externo.

---
Gerado por reversa-explorer em 2026-09-27T17:20:16.8385990-03:00
Sessão: 001-carteira-crypto
Nenhuma recomendação emitida por design. Convergência é papel de /reversa-arbiter.
