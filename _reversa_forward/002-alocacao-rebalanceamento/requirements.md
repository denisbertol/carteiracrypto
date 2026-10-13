# Requirements: Alocação e rebalanceamento

> Identificador: `002-alocacao-rebalanceamento`  
> Data: `2026-09-27`  
> Pasta da extração reversa: `_reversa_sdd/`  
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA / DÚVIDA

---

## 1. Resumo executivo

Permite a Denis registrar versões das orientações de alocação recomendadas pelo consultor e comparar a posição atual com a posição ideal em USD calculada sobre o patrimônio total da carteira. O caixa (USDT) integra obrigatoriamente a distribuição e participa dos 100,00% da carteira. O sistema calcula e exibe o ajuste necessário em USD e o desvio percentual por ativo, sem sugerir ou executar ordens automáticas de compra ou venda. A entrada em vigor é imediata, ativos recomendados sem saldo aparecem com posição atual zero (para indicar compra necessária) e ativos mantidos sem meta recomendada aparecem com meta 0% (indicando realização/desinvestimento total).

---

## 2. Contexto a partir do legado e especificações

| Fonte | Trecho relevante | Confidência |
|---|---|---|
| `_reversa_sdd/sdd/alocacao-rebalanceamento.md` | Registro de orientações vigentes, validação de soma de 100,00% com USDT, cálculo da posição ideal sobre saldo total e apuração de desvios em USD. | 🟢 |
| `_reversa_sdd/prd.md#3. Requisitos Funcionais` | RF-05 e RF-06: definição de metas de alocação por percentuais do consultor e exibição comparativa entre carteira atual e ideal. | 🟢 |
| `_reversa_sdd/addenda/001-operacoes-posicao-carteira.md` | Feature 001 entrega as projeções de saldo total, caixa USDT e valor atual a mercado das posições cripto. | 🟢 |
| `_reversa_sdd/personas.md` | Persona Denis: autonomia na tomada de decisões fora do sistema, consultando desvios para direcionar compras, vendas e rebalanceamentos manuais. | 🟢 |

---

## 3. Personas e cenários de uso

| Persona | Objetivo | Cenário-chave |
|---|---|---|
| Denis | Visualizar desvios em USD da carteira em relação aos percentuais recomendados pelo consultor. | Recebe atualização semanal do consultor, cadastra a nova orientação com soma 100,00% e confere quais ativos demandam aporte ou realização. |

---

## 4. Regras de negócio novas ou alteradas

1. **RN-01 🟢:** A alocação recomendada é composta por um conjunto de percentuais atribuídos a cada ativo, incluindo obrigatoriamente o caixa (USDT). A soma de todos os percentuais de uma orientação deve totalizar exatamente 100,00%. Somatórios divergentes devem ser rejeitados com indicação da diferença. Origem: `_reversa_sdd/sdd/alocacao-rebalanceamento.md#RF-01,RF-02`.
2. **RN-02 🟢:** As orientações são versionadas no tempo. O cadastro de uma nova orientação válida torna-a a orientação vigente, preservando o histórico das versões anteriores para auditoria e conferência. Origem: `_reversa_sdd/sdd/alocacao-rebalanceamento.md#RF-03`.
3. **RN-03 🟢:** A base de cálculo da posição ideal é o patrimônio total da carteira em USD (saldo em caixa USDT somado ao valor de mercado atual de todos os criptoativos). A posição ideal em USD de um ativo é dada por `saldo_total_usd * (percentual_vigente / 100)`. Origem: `_reversa_sdd/sdd/alocacao-rebalanceamento.md#RF-04,RF-05`.
4. **RN-04 🟢:** O ajuste necessário em USD é calculado como `posicao_ideal_usd - posicao_atual_usd`. Valores positivos representam saldo faltante (necessidade de aporte/compra); valores negativos representam excesso de alocação (necessidade de realização/venda). O sistema exibe o valor numérico assinado, sem prescrever ordens de compra/venda. Origem: `_reversa_sdd/sdd/alocacao-rebalanceamento.md#RF-06`.
5. **RN-05 🟢:** O desvio percentual é calculado como `(posicao_atual_usd / posicao_ideal_usd) - 1` quando a posição ideal for maior que zero. Se a posição ideal for zero, o desvio percentual é considerado não aplicável (N/A). Origem: `_reversa_sdd/sdd/alocacao-rebalanceamento.md#RF-07`.
6. **RN-06 🟡:** Se o saldo total for zero ou se as cotações de mercado estiverem indisponíveis para ativos com saldo positivo, a comparação de alocação deve ser sinalizada como incompleta/indisponível, sem exibir valores fictícios derivados de zero. Origem: `_reversa_sdd/sdd/alocacao-rebalanceamento.md#EC-02,EC-04`.
7. **RN-07 🟢:** A orientação cadastrada passa a vigorar imediatamente a partir do momento do salvamento, tornando-se a base ativa para recálculo de todas as posições ideais e arquivando a orientação anterior. Origem: sessão de esclarecimentos (resposta 1).
8. **RN-08 🟢:** A tabela comparativa de alocação exibe a união dos ativos recomendados na orientação vigente com os ativos atualmente mantidos em carteira com saldo positivo:
   - Se um ativo mantido em carteira receber meta 0,00% (ou não for citado na recomendação), ele aparece com meta 0,00%, posição ideal USD 0,00 e ajuste negativo igual ao valor atual total (desinvestimento).
   - Se um ativo novo recomendado ainda não tiver saldo mantido (posição atual zero), ele aparece com posição atual USD 0,00 e ajuste positivo igual à sua posição ideal (aquisição). Origem: sessão de esclarecimentos (respostas 2 e 3).

---

## 5. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de aceite | Confidência |
|---|---|---|---|---|
| RF-01 | Cadastro de Orientação de Alocação | Must | Permite registrar uma versão de orientação contendo percentuais para ativos e USDT, com entrada em vigor imediata. | 🟢 |
| RF-02 | Validação Estrita de Soma 100% | Must | Rejeita cadastros cuja soma dos percentuais seja diferente de 100,00%, informando a diferença exata. | 🟢 |
| RF-03 | Versionamento e Histórico | Must | Mantém o histórico imutável das orientações anteriores permitindo consulta da evolução da estratégia. | 🟢 |
| RF-04 | Cálculo da Posição Ideal em USD | Must | Calcula a posição ideal de cada ativo multiplicando o saldo total da carteira pelo percentual vigente com precisão decimal. | 🟢 |
| RF-05 | Cálculo do Ajuste Necessário em USD | Must | Calcula e exibe `posição ideal - posição atual` como número assinado em USD para todos os ativos vigentes ou mantidos. | 🟢 |
| RF-06 | Cálculo do Desvio Percentual | Must | Calcula `(atual / ideal) - 1` formatado em percentual com duas casas decimais, ou N/A se ideal for zero. | 🟢 |
| RF-07 | Tabela Comparativa no Painel | Must | Exibe tabela consolidada no painel web contendo: Ativo, % Sugerido, Valor Atual, Valor Ideal, Desvio USD e Desvio %. | 🟢 |
| RF-08 | Reconciliação Visual de Arredondamento | Should | Garante que a soma das posições ideais reconcilie com o saldo total com discrepância máxima de USD 0,01. | 🟡 |
| RF-09 | Exportação de Alocação em CSV | Should | Disponibiliza endpoint para download em CSV da comparação de alocação vigente e histórico de metas. | 🟢 |

---

## 6. Requisitos Não Funcionais

| Tipo | Requisito | Evidência ou justificativa | Confidência |
|---|---|---|---|
| Precisão | Cálculos realizados em alta precisão `Decimal` nativa, eliminando erros de ponto flutuante binário. | RNF-01 e RNF-02 da spec. | 🟢 |
| Desempenho | Tempo de resposta do cálculo de alocação inferior a 50ms para até 100 ativos cadastrados. | Roadmap técnico e restrição de processo leve. | 🟡 |
| Segurança | Orientação e metas protegidas por Row Level Security (RLS) e acessíveis exclusivamente por Denis via Supabase Auth. | RF-12 e diretrizes de privacidade. | 🟢 |

---

## 7. Critérios de Aceitação

```gherkin
Cenário: CA-01 Cadastro de orientação válida com 100% incluindo USDT
  Dado que Denis possui saldo total de 10.000 USD na carteira (incluindo caixa e criptos)
  Quando cadastra uma nova orientação com: BTC 50%, ETH 30% e USDT 20%
  Então a orientação entra em vigor imediatamente
  E a posição ideal calculada é: BTC USD 5.000,00, ETH USD 3.000,00 e USDT USD 2.000,00

Cenário: CA-02 Rejeição de orientação com soma divergente de 100%
  Quando Denis submete uma orientação com BTC 50%, ETH 30% e USDT 15% (soma 95%)
  Então a solicitação é rejeitada com erro de validação
  E o sistema informa que a soma atual é 95,00% e faltam 5,00% para completar 100%
  E a orientação vigente anterior permanece inalterada

Cenário: CA-03 Cálculo de desvio em USD e percentual
  Dado que a carteira possui saldo total de 10.000 USD
  E a orientação vigente define BTC com 50% (ideal de USD 5.000,00)
  E a posição atual em BTC é de USD 4.500,00
  Então o ajuste necessário em USD é +500,00 USD
  E o desvio percentual é de -10,00%
  E nenhum texto de compra ou venda automática é exibido

Cenário: CA-04 Ativo em carteira com meta recomendada de zero
  Dado que Denis possui 1.000 USD em SOL na carteira
  Quando a nova orientação do consultor atribui 0% a SOL
  Então SOL é exibido na tabela com meta de 0,00%
  E a posição ideal de SOL é 0,00 USD
  E o ajuste necessário é de -1.000,00 USD
  E o desvio percentual é exibido como "N/A"

Cenário: CA-05 Novo ativo recomendado sem posição mantida
  Dado que Denis não possui nenhum saldo em SOL (atual 0,00 USD)
  Quando o consultor recomenda 10% em SOL para um patrimônio total de 10.000 USD
  Então SOL aparece na tabela de alocação com atual USD 0,00
  E posição ideal de 1.000,00 USD
  E ajuste necessário de +1.000,00 USD

Cenário: CA-06 Carteira com cotações indisponíveis
  Dado que um ativo com quantidade positiva está sem cotação a mercado válida
  Quando a tabela de alocação é consultada
  Então o sistema exibe aviso de que a posição comparativa está incompleta
  E não inventa valores ideais baseados em saldo parcial
```

---

## 8. Prioridade MoSCoW

| Item | MoSCoW | Justificativa |
|---|---|---|
| RF-01 a RF-07 | Must | Funcionalidades essenciais para eliminar a dependência da planilha do consultor. |
| RF-08 (Reconciliação) | Should | Refinamento de apresentação para garantir que a soma dos centavos feche perfeitamente. |
| RF-09 (Exportação CSV) | Should | Facilidade de auditoria e exportação para registros externos. |

---

## 9. Esclarecimentos

### Sessão 2026-09-27

- **Q:** Quando você cadastrar uma nova recomendação de percentuais, qual deve ser o início da vigência?  
  **R:** 1 a — Entra em vigor imediatamente após o salvamento, tornando-se a base ativa de cálculo.
- **Q:** Se você mantiver saldo de um ativo, mas a nova recomendação do consultor atribuir 0% a ele, como exibir?  
  **R:** 2 a — Deve permanecer visível na tabela com meta de 0,00%, exibindo todo o saldo atual como desvio/ajuste a realizar (desinvestimento).
- **Q:** Se o consultor sugerir percentual para um ativo que você ainda não possui (posição atual USD 0,00), como tratar?  
  **R:** 3 a — Deve aparecer na tabela com posição atual USD 0,00 e ajuste necessário positivo igual ao valor ideal a comprar (aquisição).

As respostas fecham integralmente as lacunas L-01 e L-02 e estão refletidas nas regras RN-07 e RN-08 e nos cenários CA-04 e CA-05.

---

## 10. Lacunas

Nenhuma dúvida pendente nesta sessão. Todas as regras comportamentais estão fechadas e confirmadas.

---

## 11. Histórico de alterações

| Data | Alteração | Autor |
|---|---|---|
| 2026-09-27 | Versão inicial gerada por `/reversa-requirements` a partir da spec SDD alocacao-rebalanceamento.md | reversa-requirements |
| 2026-09-27 | Resolução das dúvidas L-01 e L-02; inclusão das regras RN-07 e RN-08 e cenários CA-04 e CA-05 | reversa-clarify |
