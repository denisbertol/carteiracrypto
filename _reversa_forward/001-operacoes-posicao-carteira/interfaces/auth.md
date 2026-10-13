# Contrato Supabase Auth — proposto

Integração HTTPS usando SUPABASE_URL e chave pública publishable. Usuário único previamente criado; sem rota de registro no produto. Senha enviada diretamente ao Auth e não registrada pela aplicação.

- Login: POST `{SUPABASE_URL}/auth/v1/token?grant_type=password`, headers apikey e Content-Type application/json; body {email,password}. Sucesso entrega access_token, refresh_token, expires_in e user.
- Renovação: POST no mesmo caminho com grant_type=refresh_token e body {refresh_token}; substituir tokens conforme resposta.
- Validação preferida: assinatura JWT com JWKS do projeto, issuer `{SUPABASE_URL}/auth/v1`, audience authenticated, exp e sub; sub deve ser exatamente OWNER_USER_ID. Permitir somente algoritmos da configuração verificada, nunca escolher algoritmo a partir do token sem restrição.
- Projetos sem assinatura assimétrica suportada: GET `{SUPABASE_URL}/auth/v1/user` com apikey e bearer; sucesso precisa devolver ID igual ao proprietário. Não aceitar token somente decodificado.

Tokens mantidos apenas em memória no cliente nesta primeira entrega; recarregar página pode exigir login. Não usar localStorage para secrets nem colocar token em URL. Logout limpa memória e solicita invalidação ao Auth; dados da tela são limpos. Resposta financeira 401 solicita novo login, preservando formulário apenas em memória enquanto a página estiver aberta; confirmar identidade antes do reenvio.

Timeout Auth 5 s. Falha de rede/5xx não concede acesso; exibir erro recuperável. Login/refresh não recebem retries cegos, pois refresh pode rotacionar token; em falha ambígua pedir novo login. JWKS em cache limitado a 10 minutos; chave desconhecida tenta atualização uma vez. Chaves válidas cacheadas permitem validação local até expiração do cache/token; caso contrário falhar fechado.

Fonte: [JWT Supabase](https://supabase.com/docs/guides/auth/jwts). No coding, verificar endpoints e esquema com a versão oficial usada e testes em projeto isolado. Papel de banco não deriva de entrada do cliente; identidade validada é passada localmente à transação pelo backend.
