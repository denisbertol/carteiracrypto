# Carteira Crypto 🚀

Aplicação pessoal leve para gestão de carteira de criptoativos, cálculo de preço médio ponderado, acompanhamento de ganhos/perdas realizados e projeção da carteira ideal com base nas orientações de consultoria.

Projetada com motor contábil puro em alta precisão decimal (`Decimal` de 80 dígitos) e isolamento atômico em banco de dados PostgreSQL com Row Level Security (RLS) e Supabase Auth.

---

## 🛠 Arquitetura e Tecnologias

- **Linguagem & Framework:** Python 3.12+ com FastAPI e Uvicorn.
- **Banco de Dados:** PostgreSQL (Supabase) com schema privado `portfolio_private` e RLS forçada.
- **Autenticação:** Supabase Auth (JWT assimétrico com validação de JWKS e verificação de proprietário `OWNER_USER_ID`).
- **Interface:** HTML responsivo renderizado no servidor via Jinja2 e CSS puro (foco móvel a partir de 360px).
- **Hospedagem:** Otimizada para execução em container leve no **Koyeb** (consumo < 128 MB de RAM).

---

## 🚀 Como Executar Localmente

### 1. Pré-requisitos
- Python 3.11+
- Banco de dados PostgreSQL (local ou instância gratuita no Supabase)
- Docker (opcional)

### 2. Configuração de Variáveis de Ambiente
Copie o arquivo de exemplo e preencha suas variáveis:
```bash
cp .env.example .env
```
Preencha no `.env`:
- `DATABASE_URL`: String de conexão do PostgreSQL (papel de aplicação).
- `MIGRATION_DATABASE_URL`: String de conexão com permissões administrativas para criar tabelas/schemas.
- `SUPABASE_URL` e `SUPABASE_PUBLISHABLE_KEY`: Dados do seu projeto Supabase.
- `OWNER_USER_ID`: Seu UUID de usuário no Supabase Auth.

### 3. Instalar Dependências
```bash
pip install -e ".[dev]"
```

### 4. Executar Migrações do Banco
```bash
python -m app.migrate
```

### 5. Executar Suíte de Testes
```bash
python -m unittest discover tests
```

### 6. Executar Seeds Demonstrativos
```bash
# Seed contábil básico
python scripts/seed_demo.py

# Seed de recomendação de alocação inicial (BTC 50%, ETH 30%, USDT 20%)
python scripts/seed_allocation.py
```

### 7. Iniciar Servidor Local
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
Acesse no navegador: `http://127.0.0.1:8000`

---

## 📊 Módulos e Funcionalidades

### 1. Operações e Posição da Carteira (`001-operacoes-posicao-carteira`)
- Registro de compras, vendas, depósitos, saques e transferências de custódia.
- Contabilidade contínua com preço médio ponderado e segregação do caixa em USDT.
- Projeção de patrimônio total e lucro/prejuízo realizado em USD.
- Exportação CSV em `/api/v1/exports/operations.csv` e `/api/v1/exports/positions.csv`.

### 2. Alocação e Rebalanceamento (`002-alocacao-rebalanceamento`)
- Cadastro e controle de versões de recomendações de alocação ideal.
- Regra estrita de validação: somatório das porcentagens deve ser exatamente `100,00%` (incluindo USDT como caixa).
- Motor de cálculo com algoritmo do Maior Resto (Largest Remainder) para reconciliação exata de centavos de dólar.
- Exibição comparativa: Alocação Alvo (%), Valor Atual (USD), Valor Ideal (USD), Ajuste Necessário (USD) e Desvio (%).
- Endpoints REST:
  - `GET /api/v1/allocations`: Obtém a comparação atual de rebalanceamento contra os preços de mercado vigentes.
  - `POST /api/v1/allocations`: Cadastra uma nova versão vigente da recomendação e arquiva versões anteriores.
  - `GET /api/v1/allocations/history`: Consulta o histórico de versões anteriores de orientações.
  - `GET /api/v1/exports/allocations.csv`: Exporta os dados calculados de rebalanceamento em formato CSV.

### 3. Monitoramento de preços e alertas (`003-monitoramento-precos-alertas`)

- A página inicial entrega somente o shell público. Entre com uma sessão Supabase Auth para consultar carteira, alocação, alvos, notificações ou exportações; access/refresh tokens permanecem na memória da aba e não são persistidos no navegador.
- Posição e alocação carregam juntas por `GET /api/v1/dashboard`, em um snapshot `REPEATABLE READ`. Exportações CSV exigem `Bearer` e são baixadas pelo cliente autenticado.
- Cadastre alvos de compra/venda em USD, uma faixa global de 0% a 100% (padrão 10%) e o ID CoinGecko para cada ativo não pareado com USDT. A cobertura é explícita: ativos pendentes ou sem cobertura ficam indisponíveis e não geram alertas.
- O acompanhamento solicita ciclos de 300 segundos enquanto a aplicação está aberta, autenticada e conectada. Suspensão da aba, rede indisponível ou sessão expirada interrompem a cobertura; ao retornar, o sistema informa a lacuna e não cria alertas retroativos. Não há alertas push, e-mail ou SMS.
- Cotações antigas permanecem identificadas como desatualizadas e nunca geram alerta. A tela atribui dados de mercado à CoinGecko. Avaliações e notificações ficam disponíveis por 30 dias; o processo reconcilia ciclos interrompidos a cada 60 segundos e limpa o histórico expirado após uma reconciliação bem-sucedida.

#### Configuração do provedor

O padrão é `QUOTE_MODE=unavailable`. Para habilitar CoinGecko Demo, configure no ambiente do servidor `QUOTE_MODE=coingecko`, `COINGECKO_DEMO_API_KEY`, `COINGECKO_CALL_LIMIT` e os dois limites da janela real da chave (`COINGECKO_WINDOW_START` e `COINGECKO_WINDOW_END`, com timezone). A chave fica somente no servidor; o navegador recebe apenas a configuração pública do Supabase. Sem chave ou janela válida, o primeiro pedido fica bloqueado antes de criar um ciclo ou fazer chamada externa.

Confirme no painel do provedor a quota realmente disponível antes de habilitar. Cada lote de cotação e atualização do catálogo consome orçamento; falhas também podem consumir quota. Com um lote por ciclo a cada cinco minutos durante 31 dias, a projeção é de 8.928 chamadas, antes de consultas ao catálogo. Lotes adicionais elevam esse total. O contador local deve refletir o limite real da chave. Nenhuma cobertura universal do catálogo é presumida.

#### Verificações locais

Com Playwright e Chrome/Chromium disponíveis no ambiente Node, execute `node --test tests/browser_monitoring.cjs`. Os cenários de navegador usam respostas de API simuladas para testar formulários, horários, notificações e layout de 360 px. A validação com PostgreSQL, sessão real e provedor configurado está registrada separadamente em `_reversa_forward/003-monitoramento-precos-alertas/validation.md`.

#### Rollback

Para interromper consultas, defina `QUOTE_MODE=unavailable` no servidor e reinicie o serviço. Mantenha o schema e o histórico; o rollback não remove operações, alvos ou notificações e nunca deve reintroduzir bypass de autenticação ou tokens de teste. Migrações não são revertidas automaticamente.

---

## 🚢 Deploy no Koyeb (Container)

1. Crie uma aplicação no [Koyeb](https://www.koyeb.com).
2. Configure o deploy a partir do repositório Git ou via Docker image.
3. Defina as variáveis de ambiente no painel do Koyeb (`DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `OWNER_USER_ID`, `APP_ENV=production`).
4. Configure o Health Check HTTP:
   - Caminho: `/health/live`
   - Porta: `8000`
