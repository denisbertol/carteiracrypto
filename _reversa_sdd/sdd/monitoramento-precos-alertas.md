# Spec: Monitoramento de preços e alertas

**Versão:** 1.0
**Status:** Em revisão
**Autor:** reversa-spec-sdd
**Data:** 2026-09-27
**Reviewers:** Denis

---

## 1. Resumo

🟡 O componente consulta cotações em USD, mantém alvos informados pelo consultor e avisa dentro da aplicação aberta enquanto o preço permanecer na faixa configurável de proximidade. A primeira entrega usa 10% como valor inicial e deve produzir cada alerta devido em até 30 minutos.

## 2. Contexto e Motivação

**Problema:** 🟡 Denis consulta a carteira aproximadamente de hora em hora e pode perder oportunidades porque não percebe quando um preço se aproxima do alvo semanal.

**Evidências:** 🟡 O fracasso que mais preocupa o usuário é o alerta chegar tarde ou não chegar. O usuário aceitou alertas somente com a aplicação aberta na primeira versão.

**Por que agora:** 🟡 A confiabilidade deste componente determina se o aplicativo reduz a dependência do acompanhamento manual.

## 3. Goals (Objetivos)

- [ ] 🟡 G-01: Entregar cada alerta devido em até 30 minutos após uma cotação válida entrar na faixa de proximidade, enquanto a aplicação permanecer aberta.
- [ ] 🟡 G-02: Registrar o resultado de 100% das avaliações executadas como fora da faixa, alerta exibido ou falha identificada.
- [ ] 🟡 G-03: Permitir alterar o percentual global de proximidade, iniciado em 10,00%.

**Métricas de sucesso:**

| Métrica | Baseline atual | Target | Prazo |
|---|---:|---:|---|
| 🟡 Latência do alerta devido | 🟡 Monitoramento manual | 🟡 ≤ 30 minutos | 🟡 Cada evento durante o teste |
| 🟡 Avaliações com resultado observável | 🟡 Não existe | 🟡 100% das execuções | 🟡 Durante o teste |
| 🟡 Percentual inicial de proximidade | 🟡 Não existe | 🟡 10,00% | 🟡 Primeira configuração |

## 4. Non-Goals (Fora do Escopo)

- 🟡 NG-01: Enviar alertas com a aplicação fechada.
- 🟡 NG-02: Enviar e-mail, SMS, mensagem instantânea ou push nativo.
- 🟡 NG-03: Executar operações ou recomendar compra e venda.
- 🟡 NG-04: Garantir preço em tempo real além da frequência permitida pela API gratuita.

## 5. Usuários e Personas

**Usuário primário:** 🟡 Denis, que acompanha pelo celular e entende os alvos e riscos de mercado.

**Usuário secundário:** 🟡 Não existe. O consultor fornece os alvos fora da aplicação.

**Jornada atual:** 🟡 Denis consulta preços quando tem oportunidade e compara mentalmente ou em planilha com os alvos.

**Jornada futura:** 🟡 Denis registra os alvos, mantém o aplicativo aberto quando deseja monitorar e recebe avisos repetidos em cada atualização enquanto o preço estiver na faixa.

## 6. Requisitos Funcionais

### 6.1 Requisitos Principais

| ID | Requisito | Prioridade | Critério de Aceite |
|---|---|---|---|
| RF-01 | 🟡 O usuário deve poder registrar, alterar, ativar e desativar alvos em USD para cada ativo, identificando o tipo compra ou venda e a orientação de origem. | Must | 🟡 Um ativo aceita alvos ativos distintos e alvos desativados não geram avaliação. |
| RF-02 | 🟡 O sistema deve manter um percentual global configurável de proximidade com valor inicial de 10,00%. | Must | 🟡 Nova instalação usa 10,00%; alteração válida passa a ser usada nas avaliações seguintes. |
| RF-03 | 🟡 O sistema deve calcular a distância percentual como o valor absoluto da diferença entre cotação e alvo dividido pelo alvo. | Must | 🟡 Cotação 90 e alvo 100 resultam em 10,00%; cotação 110 e alvo 100 também resultam em 10,00%. |
| RF-04 | 🟡 O sistema deve considerar o preço dentro da faixa quando a distância percentual for menor ou igual ao percentual configurado. | Must | 🟡 Distância exatamente igual ao limite entra na faixa; distância superior fica fora. |
| RF-05 | 🟡 O sistema deve consultar cotações em USD em intervalos que garantam nova avaliação no máximo a cada 30 minutos enquanto a aplicação estiver aberta, respeitando os limites do provedor. | Must | 🟡 Durante sessão aberta e provedor disponível, não há intervalo superior a 30 minutos entre avaliações previstas. |
| RF-06 | 🟡 O sistema deve exibir uma notificação dentro da aplicação em cada avaliação válida enquanto o preço permanecer na faixa do alvo. | Must | 🟡 Três avaliações consecutivas dentro da faixa produzem três notificações; ao sair da faixa, a avaliação seguinte não notifica. |
| RF-07 | 🟡 O sistema deve cessar notificações para um alvo assim que uma cotação válida ficar fora da faixa ou o alvo for desativado. | Must | 🟡 O próximo ciclo após cada condição não exibe novo alerta para o alvo. |
| RF-08 | 🟡 O sistema deve registrar cotação, instante da cotação, instante da avaliação, distância calculada, alvo, limite e resultado de cada avaliação. | Must | 🟡 Cada avaliação pode ser auditada com os valores que determinaram o resultado. |
| RF-09 | 🟡 O sistema deve registrar tentativas de atualização ou avaliação que falharem e não contabilizá-las como alertas entregues. | Must | 🟡 Falha contém instante e causa observável e não aparece como sucesso. |
| RF-10 | 🟡 O sistema deve identificar na interface a última cotação válida e seu instante. | Must | 🟡 O usuário consegue distinguir cotação atualizada de cotação desatualizada. |
| RF-11 | 🟡 O sistema deve permitir vários alvos por ativo e avaliar cada alvo ativo de forma independente. | Should | 🟡 Dois alvos do mesmo ativo produzem estados e alertas separados. |

### 6.2 Fluxo Principal (Happy Path)

1. 🟡 O usuário registra um alvo e mantém o limite de 10% ou informa outro percentual.
2. 🟡 O usuário abre a aplicação e inicia uma sessão de acompanhamento.
3. 🟡 O sistema consulta a cotação em USD e registra seu instante.
4. 🟡 O sistema calcula a distância para cada alvo ativo.
5. 🟡 O sistema registra o resultado de cada avaliação.
6. 🟡 Para cada alvo dentro da faixa, o sistema exibe uma notificação na aplicação.
7. 🟡 O ciclo se repete em cada atualização até a aplicação fechar, o alvo ser desativado ou o preço sair da faixa.

### 6.3 Fluxos Alternativos

**Fluxo Alternativo A — Aplicação fechada:**
1. 🟡 O usuário fecha a aplicação.
2. 🟡 O sistema não promete avaliação nem entrega de notificação durante esse período.

**Fluxo Alternativo B — Falha na cotação:**
1. 🟡 A consulta ao provedor falha ou retorna dado inválido.
2. 🟡 O sistema registra a falha, mantém identificável a última cotação válida e não gera alerta a partir de dado inválido.

## 7. Requisitos Não-Funcionais

| ID | Requisito | Valor alvo | Observação |
|---|---|---|---|
| RNF-01 | 🟡 Latência | 🟡 ≤ 30 minutos com aplicação aberta | 🟡 Medida da entrada na faixa até a exibição do alerta. |
| RNF-02 | 🟡 Observabilidade | 🟡 100% das avaliações e falhas registradas | 🟡 Sem valores sensíveis além do necessário para auditar o alvo. |
| RNF-03 | 🟡 Consumo | 🟡 Uma consulta não deve ser repetida por alvo do mesmo ativo no mesmo ciclo | 🟡 Reutilizar a cotação do ciclo para todos os alvos daquele ativo. |
| RNF-04 | 🟡 Privacidade | 🟡 Notificação visível apenas na sessão autenticada | 🟡 Não expor saldo total no texto padrão do alerta. |

## 8. Design e Interface

**Componentes afetados:** 🟡 Editor de alvos, configuração de proximidade, indicador de última atualização, central de notificações e histórico de avaliações.

**Comportamento esperado:** 🟡 A notificação informa ativo, cotação, alvo, tipo do alvo, distância percentual e horário. Notificações permanecem acessíveis na sessão sem impedir o uso da carteira.

**Estados da UI:**
- 🟡 Estado vazio: orientar o cadastro do primeiro alvo.
- 🟡 Estado de carregamento: mostrar consulta em andamento e última cotação válida.
- 🟡 Estado de erro: informar indisponibilidade sem usar preço zero.
- 🟡 Estado de sucesso: mostrar instante da atualização e alertas produzidos no ciclo.

## 9. Modelo de Dados

🟡 Entidades comportamentais necessárias:

```text
Alvo: identificador, ativo, tipo, preço em USD, estado, orientação, datas
Configuração de proximidade: percentual vigente, datas
Cotação: ativo, valor em USD, instante de mercado ou coleta, provedor
Avaliação: alvo, cotação, distância, limite, resultado, instante, causa de falha
Notificação em aplicação: avaliação, conteúdo, instante de exibição, estado de leitura
```

**Migrações necessárias:** 🟡 Não há legado de aplicação. Alvos iniciais serão inseridos manualmente.

## 10. Integrações e Dependências

| Dependência | Tipo | Impacto se indisponível |
|---|---|---|
| 🟡 API gratuita de cotações em USD | 🟡 Obrigatória | 🟡 Registrar falha, mostrar última cotação válida como desatualizada e suspender alertas baseados em preço novo. |
| 🟡 Sessão ativa da aplicação | 🟡 Obrigatória na primeira entrega | 🟡 Não há compromisso de monitoramento ou alerta com a aplicação fechada. |
| 🟡 Catálogo de ativos | 🟡 Obrigatória | 🟡 Alvo não pode ser associado nem cotado sem identificador válido. |

## 11. Edge Cases e Tratamento de Erros

| Cenário | Trigger | Comportamento esperado |
|---|---|---|
| EC-01: Alvo zero ou negativo | 🟡 Preço-alvo menor ou igual a zero | 🟡 Rejeitar o alvo e manter a versão anterior. |
| EC-02: Limite inválido | 🟡 Percentual menor que 0% ou maior que 100% | 🟡 Rejeitar a configuração e explicar o intervalo permitido. |
| EC-03: Limite exato | 🟡 Distância igual ao percentual configurado | 🟡 Considerar dentro da faixa e notificar. |
| EC-04: API indisponível | 🟡 Timeout, erro ou limite de quota | 🟡 Registrar falha, sinalizar cotação desatualizada e não gerar alerta com preço antigo como se fosse novo. |
| EC-05: Vários alvos na faixa | 🟡 Uma cotação atende mais de um alvo do ativo | 🟡 Gerar notificação identificável para cada alvo ativo. |
| EC-06: Saída e retorno à faixa | 🟡 Preço sai da faixa e depois volta | 🟡 Cessar enquanto estiver fora e retomar em cada ciclo após o retorno. |
| EC-07: Aplicação perde conexão | 🟡 Sessão aberta sem acesso ao serviço | 🟡 Informar interrupção, registrar a falha possível e retomar avaliações futuras sem afirmar cobertura do intervalo perdido. |

## 12. Segurança e Privacidade

- **Autenticação:** 🟡 O monitoramento e as notificações exigem sessão autenticada.
- **Autorização:** 🟡 Apenas Denis gerencia e visualiza seus alvos.
- **Dados sensíveis:** 🟡 Alvos revelam estratégia; notificações devem evitar saldos e demais valores da carteira.
- **Auditoria:** 🟡 Registrar mudanças de alvo, limite de proximidade, avaliações, falhas e entregas.

## 13. Plano de Rollout

- **Estratégia:** 🟡 Prova com poucos ativos, alvos simulados próximos e eventos dentro e fora da faixa durante vários ciclos.
- **Como reverter (rollback):** 🟡 Desativar os alvos e retornar ao acompanhamento manual sem alterar operações ou posições.
- **Monitoramento pós-deploy:** 🟡 Medir intervalos, falhas, alertas devidos, alertas exibidos e notificações repetidas nas primeiras 24 a 48 horas de sessão de teste.

## 14. Open Questions

| # | Pergunta | Impacto | Dono | Prazo |
|---|---|---|---|---|
| OQ-01 | ⚠️ ABERTO: Qual API gratuita cobre todos os ativos usados por Denis em USD? | 🟡 Alto | 🟡 Implementação | 🟡 Antes da prova de conceito |
| OQ-02 | ⚠️ ABERTO: Qual duração e quantidade mínima de eventos comprovam confiabilidade suficiente? | 🟡 Alto | 🟡 Denis | 🟡 Antes da aceitação |
| OQ-03 | ⚠️ ABERTO: O histórico de notificações será preservado após encerrar a sessão ou somente durante a sessão aberta? | 🟡 Médio | 🟡 Denis | 🟡 Antes da implementação da central |

## 15. Decisões Tomadas (Decision Log)

| Decisão | Alternativas consideradas | Racional |
|---|---|---|
| 🟡 Percentual configurável com início em 10% | 🟡 Valor fixo em USD | 🟡 Denis escolheu percentual e autorizou 10% como começo. |
| 🟡 Notificação dentro da aplicação aberta | 🟡 Alertas em segundo plano | 🟡 Denis dispensou funcionamento com o aplicativo fechado na primeira versão. |
| 🟡 Notificar a cada ciclo dentro da faixa | 🟡 Notificar uma vez por entrada | 🟡 Denis pediu notificação contínua até o valor sair da faixa. |

## Apêndice

### Referências
- 🟡 `../prd.md`
- 🟡 `../personas.md`
- 🟡 `../brainstorms/001-carteira-crypto/risks.md`

### Histórico de Revisões
| Versão | Data | Autor | Mudanças |
|---|---|---|---|
| 🟡 1.0 | 🟡 2026-09-27 | 🟡 reversa-spec-sdd | 🟡 Criação inicial. |

## Relatório de avaliação

🟡 **Score total:** 100/100 — ⭐ Excelente, pronta para implementação.

| Dimensão | Score |
|---|---:|
| 🟡 Completude | 🟡 100% |
| 🟡 Testabilidade | 🟡 100% |
| 🟡 Clareza | 🟡 100% |
| 🟡 Escopo | 🟡 100% |
| 🟡 Casos de borda | 🟡 100% |

🟡 **Gaps críticos:** nenhum.

🟡 **Sugestões:** nenhuma.

🟡 **Iterações:** 1.
