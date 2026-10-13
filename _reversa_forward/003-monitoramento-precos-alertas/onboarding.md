# Roteiro de validação — Feature 003

🟡 Procedimento para depois da implementação. Arquivos, comandos novos e endpoints aqui previstos não foram executados neste planejamento. Usar banco de teste e conta autorizada isolada.

1. Configurar .env com conexão de teste, Supabase Auth e proprietário existentes. Acrescentar QUOTE_MODE=coingecko e COINGECKO_DEMO_API_KEY pelo secret local/deploy; não compartilhar chave no chat. Confirmar quota e reset da chave no painel do provedor.
2. Executar `python -m app.migrate` em banco de teste; conferir migração 003 aplicada uma vez. Executar `python -m unittest discover tests` e testes PostgreSQL de integração que a implementação adicionará. Mocks sozinhos não comprovam RLS/transações.
3. Iniciar `uvicorn app.main:app --host 127.0.0.1 --port 8000`. Abrir http://127.0.0.1:8000 sem login: somente shell, nenhum saldo ou alvo. Autenticar com Denis; confirmar rejeição de tokens de teste no runtime e usuário diferente.
4. Cadastrar/mapear BTC, ETH e SOL por IDs explícitos verificados no catálogo, além de USDT contábil. Criar um ativo com identificação inexistente para verificar erro isolado. Não pressupor que símbolos garantem identidade.
5. Criar múltiplos alvos e observar limite inicial de 10%. Na suíte determinística: alvo 100, preços 90/110 dentro e 89,99 fora; repetir três ciclos na faixa e conferir três eventos por alvo. Alterar limite, desativar alvo durante consulta e simular 429/timeout/preço antigo.
6. Na prova real, criar alvos próximos aos preços verificados e manter página ativa por pelo menos seis ciclos de 5 minutos. Registrar timestamps de coleta, avaliação e exibição; resultados devem separar alerta criado de exibido. Verificar atribuição do provedor na tela.
7. Abrir segunda aba e recarregar: não aumentar chamadas por janela de 300 s. Fechar abas: não ocorrer fetch de preços novo. Suspender navegador, retornar e confirmar aviso de lacuna sem alertas retroativos.
8. Conferir carteira, alocação e CSV com mesmo snapshot de preços; preços antigos devem ser identificados e não gerar alertas. USDT permanece em USD 1,00.
9. Usar relógio controlado nos testes para avançar 30 dias: registros expiram na fronteira; limpeza remove apenas histórico expirado, preservando operações, alvos e última cotação. Reiniciar serviço e verificar retomada da limpeza.
10. Em 360 px, testar cadastro, lista de notificações, leitura, falha de rede e sessão expirada. Registrar evidências em regression-watch e relatório da prova, sem alegar aprovação antes de executar.

Rollback operacional: desabilitar monitoramento e manter leitura autenticada/cache com rótulo de desatualização. Não retornar a código com bypass de autenticação nem remover tabelas automaticamente. Deploy e criação de conta/chave permanecem ações posteriores; este plano não as executou.
