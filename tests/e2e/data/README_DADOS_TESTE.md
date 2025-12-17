# Dados de Teste Robustos - HealthCost AI Copilot

Este diretorio contem arquivos de dados para testes end-to-end do chatbot.

## Arquivos Disponiveis

### 1. Contrato de Plano de Saude (PDF)

**Arquivo:** `contrato_robusto.pdf`

Para gerar o PDF, execute:
```bash
pip install fpdf2
python gerar_contrato_robusto.py
```

**Conteudo do Contrato:**
- **12 clausulas detalhadas** cobrindo todos os aspectos do plano
- Identificacao completa das partes (CONTRATANTE e CONTRATADA)
- Caracteristicas do plano (segmentacao, abrangencia, acomodacao)
- Cobertura completa: ambulatorial, hospitalar, obstetrica
- Tabela de terapias com limites de sessoes
- Tabela completa de carencias
- Tabela detalhada de coparticipacao com limites
- Tabela de precos por faixa etaria (10 faixas)
- Lista de hospitais e prestadores credenciados
- Exclusoes de cobertura
- Regras de vigencia, renovacao e rescisao
- Canais de atendimento (SAC, Ouvidoria, ANS)
- Regras de reajuste (anual + sinistralidade)

**Perguntas para testar o chatbot:**
1. "Qual o valor da mensalidade para um titular de 45 anos?"
2. "Quantas sessoes de fisioterapia o plano cobre por ano?"
3. "Qual o prazo de carencia para parto?"
4. "O plano cobre cirurgia bariatrica?"
5. "Qual a coparticipacao para consultas?"
6. "Existe teto anual de coparticipacao?"
7. "Quais hospitais fazem parte da rede credenciada?"
8. "Quais sao as exclusoes de cobertura?"
9. "Como funciona o reajuste por sinistralidade?"
10. "Qual o limite de dependentes por titular?"

---

### 2. Planilha de Custos/Sinistros (CSV)

**Arquivo:** `custos_robusto.csv`

**Estatisticas do CSV:**
- **150+ registros** de atendimentos
- Periodo: Janeiro a Junho de 2024 (6 meses)
- 15 beneficiarios diferentes (titulares e dependentes)
- Todas as faixas etarias representadas
- Tipos de atendimento variados

**Colunas do CSV:**
| Coluna | Descricao |
|--------|-----------|
| data_atendimento | Data do procedimento (YYYY-MM-DD) |
| beneficiario | Nome completo do beneficiario |
| cpf | CPF formatado |
| tipo_beneficiario | Titular ou Dependente |
| faixa_etaria | Faixa etaria conforme contrato |
| tipo_atendimento | Consulta, Exame, Internacao, Cirurgia, etc. |
| procedimento | Descricao do procedimento |
| codigo_tuss | Codigo TUSS do procedimento |
| prestador | Nome do estabelecimento |
| categoria_prestador | Hospital, Laboratorio, Ambulatorio, etc. |
| valor_cobrado | Valor total cobrado |
| valor_pago | Valor pago pelo plano |
| coparticipacao | Valor pago pelo beneficiario |
| status | Status do pagamento |
| observacao | Notas adicionais |

**Cenarios incluidos nos dados:**

1. **Internacao cardiologica complexa** (Joao Pedro Oliveira)
   - 9 diarias de internacao
   - 2 diarias de UTI
   - Ecocardiograma durante internacao
   - Custo total: ~R$ 27.000

2. **Cirurgia ortopedica** (Ana Carolina Souza)
   - Artroscopia de joelho
   - 12 sessoes de fisioterapia
   - 2 diarias de internacao

3. **Acompanhamento pre-natal completo** (Fernanda Costa Dias)
   - 7 consultas de pre-natal
   - Ultrassonografias (morfologica, Doppler)
   - Parto cesariana
   - 3 diarias de internacao
   - Assistencia ao recem-nascido

4. **Apendicectomia de urgencia** (Eduardo Felipe Nascimento)
   - Atendimento de urgencia
   - Cirurgia videolaparoscopica
   - 3 diarias de internacao

5. **Tratamento de saude mental** (Juliana Aparecida Costa)
   - 1 consulta psiquiatrica
   - 20+ sessoes de psicoterapia
   - Acompanhamento continuo

6. **Acompanhamento geriatrico** (Lucia Helena Ferreira)
   - Consultas trimestrais
   - Densitometria ossea
   - 12 sessoes de fisioterapia

7. **Atendimentos pediatricos** (Amanda e Lucas)
   - Consultas de puericultura
   - Urgencias pediatricas
   - Investigacao alergica

8. **Check-ups preventivos** (Roberto, Sandra, Thiago)
   - Colonoscopia de rastreamento
   - Mamografia e ultrassom de mamas
   - PSA e exames urologicos

**Perguntas para testar o chatbot:**

*Analise de custos:*
1. "Qual o custo total de internacoes no periodo?"
2. "Qual beneficiario teve o maior gasto?"
3. "Quanto foi gasto com fisioterapia?"
4. "Qual o valor total de coparticipacao cobrado?"
5. "Quais foram os procedimentos mais caros?"

*Analise por categoria:*
6. "Qual prestador recebeu mais pagamentos?"
7. "Como se distribuem os custos por tipo de atendimento?"
8. "Quantas internacoes tivemos e qual o custo medio?"

*Analises combinadas (contrato + custos):*
9. "A coparticipacao cobrada esta de acordo com o contrato?"
10. "Quantas sessoes de fisioterapia foram usadas vs. o limite do contrato?"
11. "Quais pontos voce sugeriria renegociar com a operadora?"
12. "A sinistralidade esta dentro do esperado?"
13. "Temos beneficiarios que atingiram o teto de coparticipacao?"

---

## Resumo dos Custos para Referencia

### Por Tipo de Atendimento (aproximado):
| Tipo | Quantidade | Valor Total |
|------|------------|-------------|
| Consultas | ~35 | ~R$ 9.000 |
| Exames | ~30 | ~R$ 8.500 |
| Terapias | ~45 | ~R$ 7.000 |
| Internacoes | ~25 | ~R$ 55.000 |
| Cirurgias | 3 | ~R$ 24.000 |
| Parto | 1 | ~R$ 8.500 |

### Por Beneficiario (maiores custos):
1. Joao Pedro Oliveira - ~R$ 30.000 (internacao cardiologica)
2. Fernanda Costa Dias - ~R$ 18.000 (pre-natal + parto)
3. Ana Carolina Souza - ~R$ 16.000 (cirurgia joelho)
4. Eduardo Felipe Nascimento - ~R$ 12.000 (apendicectomia)
5. Lucia Helena Ferreira - ~R$ 3.500 (geriatria)

### Totais Gerais (aproximado):
- **Valor Total Cobrado:** ~R$ 115.000
- **Valor Pago pelo Plano:** ~R$ 108.000
- **Coparticipacao Total:** ~R$ 7.000

---

## Como Usar nos Testes

### Via Interface Web:
1. Acesse http://localhost:8000
2. Crie um cliente de teste
3. Faca upload do `contrato_robusto.pdf`
4. Faca upload do `custos_robusto.csv`
5. Aguarde processamento
6. Inicie conversa com perguntas da lista acima

### Via API (Swagger):
1. Acesse http://localhost:8000/docs
2. Crie cliente via POST /api/v1/clients/
3. Upload contrato via POST /api/v1/upload/contract
4. Upload custos via POST /api/v1/upload/costs
5. Processe os documentos
6. Teste chat via POST /api/v1/chat/

---

## Notas Importantes

- Os dados sao **ficticios** e criados apenas para testes
- CPFs e CNPJs sao invalidos (formato correto, digitos verificadores nao)
- Valores baseados em tabelas reais mas ajustados para testes
- Cenarios desenhados para exercitar todos os agentes do sistema:
  - **Retrieval Agent:** busca semantica no contrato
  - **Contract Analyst:** interpretacao de clausulas
  - **Cost Insights:** analise de custos e tendencias
  - **Negotiation Advisor:** sugestoes de renegociacao
