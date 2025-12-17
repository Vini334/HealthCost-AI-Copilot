# Testes E2E - HealthCost AI Copilot

Este diretório contém arquivos e instruções para testes end-to-end do sistema.

## Estrutura

```
tests/e2e/
├── README.md                      # Este arquivo
├── data/
│   ├── contrato_plano_saude.pdf   # PDF de contrato para teste
│   ├── custos_sinistros.csv       # CSV de custos/sinistros
│   └── gerar_contrato_pdf.py      # Script para gerar o PDF
└── roteiro_teste.md               # Roteiro completo de testes
```

## Pré-requisitos

1. **Aplicação rodando** via Docker:
   ```bash
   docker-compose up --build
   ```

2. **Gerar o PDF de contrato** (requer reportlab):
   ```bash
   pip install reportlab
   python tests/e2e/data/gerar_contrato_pdf.py
   ```

3. **Swagger UI** disponível em: http://localhost:8000/docs

## Dados de Teste

### Contrato (PDF)
- Empresa: Tecnologia ABC Ltda.
- Operadora: Saúde Total S/A
- Plano: Empresarial Premium
- Valor base: R$ 850,00/mês
- Coparticipação: 20% em consultas e exames de imagem
- Cobertura: Nacional, apartamento, com obstetrícia

### Custos (CSV)
- 20 registros de sinistros
- Período: Janeiro a Março/2024
- 5 beneficiários diferentes
- Tipos: Consultas, exames, internações, procedimentos
- Total aproximado: R$ 19.000,00

## Cenários de Teste

### Teste 1: Fluxo Básico
1. Criar cliente
2. Upload do contrato PDF
3. Processar documento
4. Enviar pergunta ao chat

### Teste 2: Análise de Custos
1. Upload do CSV de custos
2. Processar dados
3. Consultar resumo de custos
4. Perguntar ao chat sobre os custos

### Teste 3: Perguntas sobre Contrato
- "Qual o valor da coparticipação para consultas?"
- "Quais são as carências do plano?"
- "O que não está coberto pelo plano?"

### Teste 4: Análise de Sinistros
- "Qual o beneficiário com maior custo?"
- "Quanto gastamos com internações?"
- "Resuma os custos por tipo de atendimento"

## Executando os Testes

Siga o roteiro detalhado em `roteiro_teste.md`.
