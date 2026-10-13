# Risks, carteira-crypto

> Selo 🟡 PLANEJADO em todos os itens. Documento adversarial por design.

## Premortem
🟡 "O alerta chegou tarde ou não chegou, e a oportunidade foi perdida mesmo com o sistema em funcionamento." Causa raiz: limites da API gratuita, falha no agendamento ou canal de notificação pouco confiável.

🟡 "Os números pareciam corretos, mas preço médio, ganhos e alocação estavam errados." Causa raiz: movimentações incompletas ou regras inadequadas para taxas, vendas, transferências e moedas diferentes.

🟡 "A ferramenta foi abandonada porque manter operações, alvos e percentuais atualizados dava mais trabalho que o controle anterior." Causa raiz: excesso de entrada manual e fluxo semanal inconveniente.

**Manchete que mais assusta o usuário:** 🟡 "O alerta chegou tarde ou não chegou, e a oportunidade foi perdida mesmo com o sistema em funcionamento."

---

## Opção A, planilha automatizada com alertas
- **Premissa que mata:** 🟡 A plataforma de planilha e sua automação conseguem consultar preços e disparar alertas dentro de uma janela útil e previsível.
- **Teste barato da premissa:** 🟡 Montar uma prova com dois ativos, dois alvos próximos e um alvo já cruzado; executar por alguns dias, registrar horários de cotação e recebimento e simular uma falha da API.
- **Custo escondido:** 🟡 Operação contínua de gatilhos, permissões, limites de execução, fórmulas frágeis e diagnóstico quando a planilha falhar silenciosamente.
- **Ponto sem volta:** 🟡 Quando cálculos, histórico e automações ficarem espalhados por várias abas e scripts sem testes, tornando a migração e a auditoria caras.

## Opção B, aplicativo pessoal focado
- **Premissa que mata:** 🟡 É possível oferecer alertas suficientemente confiáveis usando uma fonte gratuita e uma infraestrutura de baixo custo, inclusive quando Denis não estiver com o aplicativo aberto.
- **Teste barato da premissa:** 🟡 Criar um monitor descartável para poucos ativos, medir durante alguns dias latência, indisponibilidade e limites da API e validar um único canal de notificação com eventos simulados.
- **Custo escondido:** 🟡 Hospedagem contínua, agendador, armazenamento seguro, observabilidade, prevenção de alertas duplicados, recuperação após falhas e manutenção quando a API mudar.
- **Ponto sem volta:** 🟡 Quando os dados históricos e a rotina pessoal dependerem do modelo interno e da infraestrutura sem exportação validada.

## Opção C, assistente de carteira integrado
- **Premissa que mata:** 🟡 As integrações de corretoras e carteiras entregam um histórico completo e reconciliável sem exigir manutenção desproporcional.
- **Teste barato da premissa:** 🟡 Exportar ou consultar dados reais de uma única origem, comparar uma amostra de compras, vendas, taxas e transferências com os comprovantes e medir as divergências antes de criar outras integrações.
- **Custo escondido:** 🟡 Segurança de credenciais, diferenças entre formatos, paginação, ativos renomeados, transações ausentes, reconciliação manual e suporte permanente a mudanças de terceiros.
- **Ponto sem volta:** 🟡 Quando decisões e cálculos passarem a depender de conectores específicos e do histórico normalizado por regras difíceis de reproduzir fora do sistema.

## Opção sempre presente, não construir
- **Premissa que mata:** 🟡 Denis conseguirá manter a disciplina manual e os alertas dispersos sem repetir a perda de oportunidades que motivou a ideia.
- **Teste barato da premissa:** 🟡 Executar por duas a quatro semanas uma rotina definida, com checklist de atualização semanal, alertas cadastrados e registro de oportunidades detectadas, perdidas e falsos alarmes.
- **Custo escondido:** 🟡 Tempo recorrente de conferência, duplicação de dados, risco de erro de digitação e dependência de memória para manter alvos e percentuais sincronizados.
- **Ponto sem volta:** 🟡 Não há um ponto técnico sem volta; o custo se acumula quando meses de registros ficam inconsistentes ou espalhados e precisam ser consolidados.

## Opção sempre presente, usar algo pronto
- **Premissa que mata:** 🟡 Um produto disponível cobre, no plano aceitável, os ativos, a moeda de referência, o histórico, os cálculos e os alertas necessários sem bloquear o controle dos percentuais-alvo.
- **Teste barato da premissa:** 🟡 Cadastrar uma amostra representativa de operações e alvos em cada candidato, comparar preço médio, resultado, alocação e alertas com um cálculo manual conhecido e testar exportação dos dados.
- **Custo escondido:** 🟡 Limites ou recursos pagos, regras de cálculo opacas, dependência do fornecedor, privacidade dos dados financeiros, mudanças no produto e trabalho paralelo para controlar a alocação recomendada.
- **Ponto sem volta:** 🟡 Quando todo o histórico estiver preso ao fornecedor sem exportação completa ou quando a rotina depender de funcionalidades que mudem de preço ou sejam removidas.

---

## Riscos transversais
🟡 Dependência de uma pessoa só: Denis será o único responsável por inserir movimentações, atualizar alvos e percentuais e perceber inconsistências; períodos sem manutenção degradam todos os cálculos e alertas.

🟡 Dados sensíveis: o histórico da carteira revela patrimônio, estratégia e comportamento financeiro; armazenamento, cópias, logs e notificações podem expor essas informações mesmo sem credenciais de negociação.

🟡 Integrações fora de controle: APIs de cotação, serviços de notificação, corretoras e aplicativos podem mudar limites, cobertura, símbolos, disponibilidade ou preço.

🟡 Migração de dados: o histórico existente precisa ser importado e validado; registros incompletos ou duplicados contaminam preço médio, ganhos, perdas e alocação.

🟡 Autenticação e permissão: uma solução hospedada ou integrada exigirá proteger acesso à carteira e, se houver conexões externas, limitar credenciais estritamente à leitura.

🟡 Disponibilidade não declarada: "ser avisado assim que estiver próximo" implica uma expectativa de latência e continuidade ainda não definida; sem uma janela mensurável não é possível avaliar se o alerta funciona bem.

## O que precisa ser respondido antes de decidir
🟡 Qual atraso máximo entre a cotação atingir a faixa e a chegada da notificação ainda permite agir?

🟡 O que significa "próximo do alvo": valor absoluto, percentual configurável, faixas distintas por ativo ou outra regra?

🟡 Qual canal de notificação será usado e ele precisa funcionar com o aplicativo fechado?

🟡 Quais operações, taxas, moedas e eventos precisam entrar no cálculo de preço médio e de ganhos e perdas?

🟡 Quanto trabalho manual semanal é aceitável para importar operações, atualizar alvos e manter percentuais?

---
Gerado por reversa-challenger em 2026-09-27T17:27:40.2156951-03:00
Sessão: 001-carteira-crypto
