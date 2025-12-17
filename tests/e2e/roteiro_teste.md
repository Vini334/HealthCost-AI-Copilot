# Roteiro de Testes E2E - Passo a Passo

## Preparação

### 1. Iniciar a aplicação
```bash
cd /mnt/c/Bitbucket/copilot_auditoria
docker-compose up --build
```

### 2. Gerar o PDF de contrato
```bash
pip install reportlab
python tests/e2e/data/gerar_contrato_pdf.py
```

### 3. Acessar o Swagger
Abra no navegador: **http://localhost:8000/docs**

---

## ETAPA 1: Verificar Saúde da Aplicação

### 1.1 Health Check
- **Endpoint:** `GET /health`
- **Clique em:** "Try it out" → "Execute"
- **Esperado:**
```json
{
  "status": "healthy",
  "version": "0.1.0"
}
```

### 1.2 Readiness Check
- **Endpoint:** `GET /ready`
- **Clique em:** "Try it out" → "Execute"
- **Esperado:** Status de cada serviço (Azure OpenAI, Search, Storage, Cosmos DB)

---

## ETAPA 2: Criar Cliente

### 2.1 Criar cliente de teste
- **Endpoint:** `POST /api/v1/clients/`
- **Body:**
```json
{
  "name": "Empresa Tecnologia ABC Ltda",
  "document": "12.345.678/0001-90",
  "document_type": "cnpj",
  "email": "contato@tecnologiaabc.com.br",
  "phone": "(11) 99999-9999",
  "city": "Sao Paulo",
  "state": "SP"
}
```
- **Clique em:** "Try it out" → Cole o JSON → "Execute"
- **Guarde o `id` retornado!** (ex: `abc123-def456-...`) - Este é o `client_id`

---

## ETAPA 3: Upload do Contrato PDF

### 3.1 Upload do arquivo
- **Endpoint:** `POST /api/v1/upload/contract`
- **Parâmetros:**
  - `client_id`: (cole o ID do cliente criado)
  - `file`: Selecione o arquivo `tests/e2e/data/contrato_plano_saude.pdf`
- **Clique em:** "Try it out" → Preencha → "Execute"
- **Guarde o `document_id` retornado!**

### 3.2 Verificar documento listado
- **Endpoint:** `GET /api/v1/documents/`
- **Parâmetro:** `client_id`: (seu client_id)
- **Execute e verifique** que o documento aparece com status "uploaded"

---

## ETAPA 4: Processar o Contrato

### 4.1 Processar documento
- **Endpoint:** `POST /api/v1/documents/process`
- **Body:**
```json
{
  "document_id": "SEU_DOCUMENT_ID_AQUI",
  "client_id": "SEU_CLIENT_ID_AQUI"
}
```
- **Execute** e aguarde o processamento
- **Esperado:** Status mudará para "processed" e você verá os chunks criados

### 4.2 Verificar chunks
- **Endpoint:** `GET /api/v1/documents/{document_id}`
- **Parâmetro:** `document_id` do contrato
- **Execute e verifique** que há chunks extraídos do PDF

---

## ETAPA 5: Upload e Processamento de Custos

### 5.1 Upload do CSV
- **Endpoint:** `POST /api/v1/upload/costs`
- **Parâmetros:**
  - `client_id`: (seu client_id)
  - `file`: Selecione `tests/e2e/data/custos_sinistros.csv`
- **Execute e guarde** o `document_id` do CSV

### 5.2 Processar custos
- **Endpoint:** `POST /api/v1/costs/process`
- **Body:**
```json
{
  "document_id": "SEU_DOCUMENT_ID_DO_CSV",
  "client_id": "SEU_CLIENT_ID"
}
```
- **Execute** e aguarde processamento

### 5.3 Verificar registros
- **Endpoint:** `GET /api/v1/costs/records`
- **Parâmetro:** `client_id`
- **Execute e verifique** que os 20 registros foram importados

### 5.4 Ver resumo de custos
- **Endpoint:** `GET /api/v1/costs/summary`
- **Parâmetro:** `client_id`
- **Execute e verifique** o resumo agregado

---

## ETAPA 6: Testar Busca Semântica

### 6.1 Buscar sobre coparticipação
- **Endpoint:** `POST /api/v1/search/`
- **Body:**
```json
{
  "query": "qual o valor da coparticipação para consultas",
  "client_id": "SEU_CLIENT_ID",
  "top_k": 3,
  "search_mode": "hybrid"
}
```
- **Execute e verifique** que retorna chunks relevantes sobre coparticipação

### 6.2 Buscar sobre carências
- **Body:**
```json
{
  "query": "quais são os prazos de carência do plano",
  "client_id": "SEU_CLIENT_ID",
  "top_k": 3,
  "search_mode": "hybrid"
}
```

---

## ETAPA 7: Testar o Chat (Copilot)

### 7.1 Primeira pergunta - sobre contrato
- **Endpoint:** `POST /api/v1/chat/`
- **Body:**
```json
{
  "message": "Qual o valor da mensalidade do plano para um titular?",
  "client_id": "SEU_CLIENT_ID"
}
```
- **Execute e verifique:**
  - Resposta menciona R$ 850,00
  - Há citações do contrato
  - Foi criada uma `conversation_id`
- **Guarde o `conversation_id`!**

### 7.2 Segunda pergunta - continuação
- **Body:** (use o mesmo conversation_id)
```json
{
  "message": "E quais são as exclusões de cobertura?",
  "client_id": "SEU_CLIENT_ID",
  "conversation_id": "SEU_CONVERSATION_ID"
}
```
- **Verifique** que o contexto da conversa foi mantido

### 7.3 Pergunta sobre custos
- **Body:**
```json
{
  "message": "Qual beneficiário teve o maior custo total? E quanto foi gasto com internações?",
  "client_id": "SEU_CLIENT_ID"
}
```
- **Verifique** que o sistema analisa os dados de custos

### 7.4 Pergunta de análise combinada
- **Body:**
```json
{
  "message": "Considerando o contrato e os custos, quais pontos você sugeriria renegociar com a operadora?",
  "client_id": "SEU_CLIENT_ID"
}
```
- **Verifique** que o sistema usa múltiplos agentes para dar recomendações

---

## ETAPA 8: Verificar Conversas

### 8.1 Listar conversas
- **Endpoint:** `GET /api/v1/conversations/`
- **Parâmetro:** `client_id`
- **Verifique** as conversas criadas

### 8.2 Ver detalhes da conversa
- **Endpoint:** `GET /api/v1/conversations/{conversation_id}`
- **Verifique** todas as mensagens trocadas

---

## Perguntas Sugeridas para Teste

### Sobre o Contrato
1. "Qual o valor da coparticipação para exames de imagem?"
2. "Quantas sessões de fisioterapia são cobertas por ano?"
3. "Qual o prazo de carência para parto?"
4. "O plano cobre cirurgia plástica?"
5. "Quais hospitais fazem parte da rede credenciada?"

### Sobre os Custos
1. "Resuma os custos por tipo de atendimento"
2. "Qual foi o procedimento mais caro?"
3. "Quanto pagamos de coparticipação no período?"
4. "Quantas internações tivemos e qual o custo total?"

### Análises Combinadas
1. "A coparticipação cobrada está de acordo com o contrato?"
2. "Quais procedimentos poderiam ser otimizados?"
3. "Sugira pontos para renegociação do contrato"

---

## Troubleshooting

### Erro 500 - Internal Server Error
- Verifique os logs: `docker-compose logs api`
- Confirme que as variáveis de ambiente Azure estão configuradas

### Documento não processado
- Verifique se o Azure AI Search está configurado
- Confirme que o índice foi criado

### Chat não responde
- Verifique conexão com Azure OpenAI
- Confirme deployment do modelo GPT-4o

### Busca retorna vazio
- Confirme que o documento foi processado
- Verifique se há chunks no índice do Azure AI Search
