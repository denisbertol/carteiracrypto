# Decision, carteira-crypto

> Selo 🟡 PLANEJADO. Decisão humana registrada, sujeita a revisão.

## Problema de referência
🟡 Quando acompanho minha carteira durante a semana, quero ser avisado da proximidade dos alvos de compra e venda e visualizar meu preço médio, ganhos, perdas e desvios da alocação recomendada, para agir a tempo com base nas orientações do consultor.

## Placar
| Opção | Job to be done | Esforço | Risco residual | Custo no legado | Total |
|---|---:|---:|---:|---:|---:|
| Planilha automatizada com alertas | 4 | 5 | 3 | 5 | 17 |
| Aplicativo pessoal focado | 5 | 3 | 4 | 5 | 17 |
| Assistente de carteira integrado | 5 | 1 | 2 | 5 | 13 |
| Não construir | 2 | 5 | 4 | 5 | 16 |
| Usar algo pronto | 3 | 5 | 4 | 5 | 17 |

🟡 Houve empate entre planilha automatizada, aplicativo pessoal focado e uso de algo pronto. Na prática, decide a necessidade de combinar regras próprias de alocação, cálculos transparentes e alertas observáveis. Como o contexto é greenfield, todas as opções receberam 5 em custo no legado.

## Recomendação do Arbiter
🟡 Aplicativo pessoal focado, 17 pontos. Entre as opções empatadas, cobre integralmente preço médio, ganhos e perdas, alocação recomendada e metas próprias, mantendo controle sobre a medição e o diagnóstico dos alertas.

## O que se perde ao escolher ela
🟡 Perde-se a implantação rápida e o menor custo inicial da planilha ou de um produto pronto; passam a existir responsabilidades de hospedagem, agendamento, observabilidade, segurança e manutenção da integração de cotações.

## Em que condição a recomendação muda
🟡 Se uma prova de conceito não entregar notificações dentro da latência aceitável usando uma API gratuita e infraestrutura de baixo custo, a opção usar algo pronto passa à frente. A latência aceitável ainda precisa ser definida.

## Decisão do usuário
🟡 Aplicativo pessoal focado, decidido por Denis em 2026-09-27T17:31:30.7930612-03:00.

## A validar antes de comprometer
🟡 Criar um monitor descartável para poucos ativos, medir durante alguns dias a latência, a indisponibilidade e os limites da API e validar um único canal de notificação com eventos simulados, inclusive com o aplicativo fechado.

## Riscos aceitos conscientemente
🟡 Dependência de APIs externas gratuitas e de um canal de notificação fora do controle do produto.

🟡 Custo contínuo de hospedagem, agendamento, armazenamento seguro, observabilidade, prevenção de alertas duplicados e recuperação após falhas.

🟡 Risco de cálculos incorretos se movimentações, taxas, vendas, transferências e moedas não forem modeladas e validadas com exemplos conhecidos.

🟡 Trabalho manual de manter movimentações, alvos semanais e percentuais do consultor atualizados, salvo automação futura.

🟡 Tratamento de dados financeiros sensíveis e necessidade de exportação para evitar dependência do formato interno.

---
Gerado por reversa-arbiter em 2026-09-27T17:31:30.7930612-03:00
Sessão: 001-carteira-crypto
