# Adendo: Agente de consulta da carteira no Telegram

> Identificador: 004-agente-telegram  
> Data: 2026-11-01  
> Cenário: greenfield  

---

## Vigência

Vigente desde 2026-11-01.

---

## Resumo da entrega

Esta feature integra um assistente autônomo móvel no Telegram pessoal de Denis (baseado no padrão Sandeclaw e desenvolvimento orientado a especificação - SDD). Denis pode consultar e registrar movimentações na carteira por texto ou voz em linguagem natural diretamente do celular.

O agente só responde após mensagem de Denis e executa sob demanda as funções da carteira: patrimônio total, resultado atual, lista de criptomoedas, saldo de ativo específico, inclusão de lançamento realizado e verificação de alarme de alvos. Ele não executa ordens a mercado em corretoras, não recomenda investimentos e bloqueia com segurança qualquer remetente não autorizado sem vazar dados patrimoniais.

Todas as 18 ações de `actions.md` foram implementadas e concluídas com sucesso, acompanhadas de uma suíte com 19 testes automatizados aprovados com 100% de êxito.

---

## Impacto por artefato da extração

| Artefato | Seção | Tipo de impacto | Delta |
|---|---|---|---|
| _reversa_sdd/prd.md | 4. Escopo (in); 5. Não-objetivos (out); 7. Dependências externas | componente-novo | O Telegram passa a ser o canal de mensageria móvel oficial da aplicação para consultas e lançamentos rápidos de Denis, mantendo as restrições estritas de mono-usuário e ausência de ordens automáticas. |
| _reversa_sdd/sdd/operacoes-posicao-carteira.md | 6. Requisitos Funcionais; 9. Modelo de Dados; 10. Integrações e Dependências | componente-novo | Operações realizadas podem ser submetidas via mensagem ou áudio transcrito; a data da mensagem preenche data ausente, campos faltantes geram perguntas e o ledger contábil executa replay atômico com idempotência garantida. |
| _reversa_sdd/sdd/monitoramento-precos-alertas.md | 6. Requisitos Funcionais; 8. Design e Interface | componente-novo | A verificação de alarmes passa a ser consultável sob demanda pelo Telegram, agregando notificações ainda não lidas e sinais de Compra e Venda a mercado, sem preencher `read_at` na interface web. |
| _reversa_sdd/sdd/painel-movel-carteira.md | 6. Requisitos Funcionais; 12. Segurança e Privacidade | componente-novo | O snapshot patrimonial e de resultado pode ser consultado fora do navegador com os mesmos valores calculados para a carteira. Remetentes desconhecidos são recusados sem dados expostos. |

---

## Regras sob vigilância

Nenhum item W ativo no watch principal. A feature é greenfield e os requisitos implementados (RF-01 a RF-10) foram catalogados na seção de observações de [regression-watch.md](../../_reversa_forward/004-agente-telegram/regression-watch.md).

---

## Fontes

- _reversa_forward/004-agente-telegram/requirements.md
- _reversa_forward/004-agente-telegram/roadmap.md
- _reversa_forward/004-agente-telegram/actions.md
- _reversa_forward/004-agente-telegram/progress.jsonl
- _reversa_forward/004-agente-telegram/legacy-impact.md
- _reversa_forward/004-agente-telegram/regression-watch.md

---

## Atualização 2026-11-01 — Cognição e Diálogo via Gemini API

A interpretação de intenções do agente Telegram foi aprimorada com a integração nativa da **API Gemini** (`gemini-2.5-flash`), utilizando a chave persistida na configuração da carteira (`portfolio_private.portfolios.gemini_api_key`) ou via variável de ambiente.

### Resumo do Delta Novo

1. **Compreensão de Linguagem Natural com LLM:**
   - Interpretação semântica profunda de mensagens incompletas, gírias e tolerância a erros tipográficos.
   - Reconhecimento explícito de solicitações abstratas como *"registrar nova operação"* ou *"comprei cripto"*, classificando a intenção como `lancamento` e identificando com precisão os campos faltantes (`missing_fields`).

2. **Fluxo Conversacional Guiado e Interativo:**
   - Geração de resposta conversacional humanizada (`conversational_reply`) para guiar Denis no preenchimento de compras/vendas (perguntando tipo, moeda, quantidade e preço de forma acolhedora e contextual).
   - Introdução da intenção `conversa` para responder educadamente a saudações, dúvidas sobre recursos da carteira e explicações de comandos, garantindo que o bot nunca fique mudo nem apresente respostas vazias.

3. **Arquitetura de Resiliência (Fallback Local):**
   - Caso a API Gemini fique indisponível, sofra timeout ou esgote cotas, o motor heurístico local atua como contingência automática, assegurando alta disponibilidade ininterrupta.

| Artefato | Seção | Tipo de impacto | Delta novo |
|---|---|---|---|
| _reversa_sdd/sdd/operacoes-posicao-carteira.md | 6. Requisitos Funcionais; 10. Integrações e Dependências | componente-novo | A entrada de operações via Telegram ganha entrevista guiada interativa conduzida por LLM para preenchimento de campos obrigatórios antes da submissão ao ledger. |
| _reversa_sdd/sdd/painel-movel-carteira.md | 6. Requisitos Funcionais; 8. Design e Interface | componente-novo | O canal conversacional incorpora capacidade de diálogo com saudações, dúvidas gerais e orientações contextuais, com fallback heurístico local. |

A suíte de testes unitários foi expandida para 21 testes cobrindo intenções conversacionais e o fluxo de perguntas guiadas de lançamento.

---

## Atualização 2026-11-01 — Robustez de Resposta e Correção de Alvos de Compra/Venda

Aprimoramento crítico da confiabilidade operacional do agente Telegram para assegurar que nenhuma mensagem enviada por Denis fique sem resposta ("vácuo zero"), acompanhado da resolução do schema do Gemini e da query de metas de alocação.

### Resumo do Delta Novo

1. **Garantia de Retorno Ininterrupto (Anti-Vácuo):**
   - Implementação de salvaguarda global de tratamento de exceções no processador de atualizações (`process_single_telegram_update`).
   - Se ocorrer qualquer falha transacional ou de rede durante o processamento de uma consulta, a transação realiza rollback seguro e o bot envia imediatamente mensagem de aviso amigável a Denis, garantindo previsibilidade da experiência de uso.

2. **Correção Relacional da Consulta de Alvos e Alocações:**
   - Ajuste em `_get_allocations_map` para associar corretamente `portfolio_private.allocation_targets` com `portfolio_private.allocation_target_items` e `portfolio_private.assets` onde `active = true`.
   - Eliminação de abortos de transação PostgreSQL (`InFailedSqlTransaction`) que interrompiam a resposta de alarmes.

3. **Respostas Segmentadas por Tipo de Alvo:**
   - Respostas personalizadas quando Denis pergunta especificamente por compras ou vendas (ex.: *"Não existem alvos de compra atingidos no momento na sua carteira"* em vez de aviso genérico).

4. **Conformidade de Schema com a API Gemini:**
   - Remoção de valores nulos/vazios na restrição de enums do JSON schema enviado à API do Gemini, eliminando erros HTTP 400 (`INVALID_ARGUMENT`).

| Artefato | Seção | Tipo de impacto | Delta novo |
|---|---|---|---|
| _reversa_sdd/sdd/monitoramento-precos-alertas.md | 6. Requisitos Funcionais; 8. Design e Interface | componente-novo | Resposta de alarme no Telegram passa a distinguir o escopo da pergunta (compra vs venda) e assegura retorno mesmo na ausência de alvos atingidos. |
| _reversa_sdd/sdd/painel-movel-carteira.md | 12. Segurança e Privacidade; 7. Requisitos Não Funcionais | componente-novo | Robustez de mensageria com garantia de feedback ao usuário sob qualquer exceção de infraestrutura, com rollback transacional preventivo. |
