# 🚕 Desafio Técnico: Engenharia de Dados NYC Taxi Trips

Este repositório contém uma solução completa de Engenharia de Dados **Serverless** para ingestão, processamento e **análise pré-agregada** dos dados de viagens de táxi de Nova York.

A arquitetura utiliza uma stack **Cloud-Native (AWS)** com orquestração centralizada no **AWS Step Functions**, garantindo um fluxo ELT robusto: **Landing** $\rightarrow$ **Consumer** $\rightarrow$ **Reporting**.

---

## 🚀 Stack Tecnológica e Arquitetura Final

| Etapa do Pipeline | Tecnologia/Serviço | Finalidade no Projeto |
| :--- | :--- | :--- |
| **Orquestração** | **AWS Step Functions** | **Controlador Serverless.** Garante o *workflow* sequencial de três passos: Ingestão $\rightarrow$ Processamento $\rightarrow$ Reporting. |
| **Infraestrutura como Código (IaC)** | **Terraform** | Provisionamento seguro e automatizado de **todos** os recursos (S3, Glue Jobs, Lambda, Step Functions, IAM Roles e Tabelas do Athena). |
| **Data Lake e Armazenamento** | **Amazon S3** | Armazenamento persistente nas camadas: `landing`, `consumer` (Delta/Parquet) e `analytics/reporting` (Parquet pré-agregado). |
| **Ingestão (EL)** | **AWS Lambda (Python)** | Baixa os arquivos e faz o upload para a **Landing Zone**, particionado por *timestamp* de ingestão. |
| **Processamento (T - Camada Consumer)** | **AWS Glue Job (PySpark)** | **Motor ETL Serverless.** Lê a última versão dos dados, aplica Data Quality (DQ) e salva na **Camada Consumer** (Delta Lake). |
| **Reporting (T - Camada Reporting)** | **AWS Glue Job (PySpark)** | **Motor ETL Serverless.** Lê a Camada Consumer, executa as agregações **Q1 e Q2** e salva os relatórios na **Camada Reporting** (pronto para consumo). |
| **Catálogo de Dados** | **AWS Glue Data Catalog** | Registro do *schema* de todas as tabelas (`trips_consumer`, `q1_monthly_revenue`, `q2_hourly_passengers`) para acesso via SQL. |
| **Consumo e Análise Ad-Hoc** | **Amazon Athena / PyAthena** | Permite consultas SQL diretas sobre os relatórios pré-agregados, garantindo baixo custo e alta performance. |

---

## 🎯 Objetivo e Transformação

O objetivo é processar os dados de viagens de táxi de **Janeiro a Maio de 2023** e disponibilizar, na **Camada Reporting**, as seguintes análises prontas:

1.  **Q1:** Média de valor total (`total_amount`) por mês.
2.  **Q2:** Média de passageiros por cada hora do dia, agrupado por tipo de viagem.

---

## 1\. ⚙️ Fase 1: Provisionamento e Execução do ELT

### 1.1. Pré-requisitos e Setup Local

1.  **Python 3.x**, **`pip`** e **`make`**.
2.  **Terraform CLI**.
3.  **AWS CLI** configurado (via `aws configure`) com credenciais que possuam permissões para todos os serviços necessários (S3, Glue, Lambda, Step Functions, IAM e Athena).

### 1.2. Provisionamento da Infraestrutura com Terraform (IaC)

Todos os recursos de S3, IAM, Glue Jobs (Processamento e Reporting) e o Step Function são provisionados via `terraform apply`, orquestrado pelo `Makefile`.

| Comando | Ação Executada |
| :--- | :--- |
| **`make deploy`** | Prepara o pacote Lambda, faz upload dos scripts Glue e executa `terraform apply --auto-approve`. |
| **`make destroy`** | **Destrói toda a infraestrutura da AWS (CUIDADO: Apaga dados).** |

### 1.3. Execução da Orquestração (Pipeline ELT Completo)

O Step Function gerencia o fluxo de três estágios. O ARN da State Machine pode ser obtido na saída do Terraform: `nyc-taxi-elt-pipeline`.

#### 1.3.1. Execução Padrão (Valores Iniciais do Desafio)

A invocação sem um *payload* específico usará os valores *default* (Janeiro a Maio de 2023).

```bash
# Substitua pelo seu ARN da State Machine
STATE_MACHINE_ARN="ARN_DA_SUA_STATE_MACHINE" 

# Invoca o Step Function. Payload vazio ({}) usa os valores default
aws stepfunctions start-execution \
    --state-machine-arn $STATE_MACHINE_ARN \
    --name "Run-$(date +%Y%m%d%H%M%S)" \
    --input '{}'
````

#### 1.3.2. Execução Customizada (Exemplo: Julho de 2024, Apenas Yellow)

Para ingerir dados de um período ou tipo de viagem diferente, passe um objeto JSON no campo `--input`:

```bash
# Payload para customizar a execução: ano 2024, mês 07, apenas yellow
INPUT='{"year": "2024", "months": ["07"], "trip_types": ["yellow"]}'

aws stepfunctions start-execution \
    --state-machine-arn $STATE_MACHINE_ARN \
    --name "Run-July2024-$(date +%Y%m%d%H%M%S)" \
    --input "$INPUT"
```

**Verificação:** Acompanhe o gráfico de execução no Console do AWS Step Functions para garantir que o fluxo de **três tarefas** (`Lambda` $\rightarrow$ `Glue Processing` $\rightarrow$ `Glue Reporting`) seja concluído com sucesso.

-----

## 2\. 🧩 Fase 2: Reporting e Disponibilização (Q1 e Q2)

Após a conclusão do Job de Reporting, os relatórios agregados estão disponíveis na **Camada Reporting** do S3 e catalogados pelo Glue Data Catalog.

### Tabelas do Glue Catalog para Consulta Final

| Tabela | Análise | Caminho no S3 |
| :--- | :--- | :--- |
| `q1_monthly_revenue` | Média Mensal de Receita | `s3://<SEU_BUCKET>/analytics/reporting/q1_monthly_revenue/` |
| `q2_hourly_passengers` | Média Horária de Passageiros | `s3://<SEU_BUCKET>/analytics/reporting/q2_hourly_passengers/` |

-----

## 3\. 🔍 Fase 3: Análise e Consumo Final de Dados

O consumo dos relatórios pré-agregados pode ser feito de duas maneiras, ambas acessando as tabelas catalogadas via Amazon Athena.

### 3.1. Acesso Direto via Amazon Athena (SQL)

Este é o método mais rápido para validação manual no console AWS:

1.  Acesse o Console do **Amazon Athena** e selecione o banco de dados `nyc_taxi_db`.
2.  Execute a consulta na tabela de relatório, por exemplo:

<!-- end list -->

```sql
SELECT 
    report_month, 
    ROUND(avg_total_amount, 2) AS avg_revenue
FROM 
    "nyc_taxi_db"."q1_monthly_revenue"
ORDER BY 
    report_month;
```

### 3.2. Acesso Programático Local (Script PyAthena)

Para integrar a análise em um ambiente Python local (como o script `analytics_job.py`):

#### A. Instalação de Dependências Locais

É necessário instalar as bibliotecas que farão a comunicação com o Athena e processarão o resultado em um DataFrame.

```bash
# Instala o driver do Athena e o Pandas
pip install pyathena[pandas]
```

#### B. Execução do Script

Certifique-se de que o **`analytics_job.py`** esteja configurado com o nome do seu bucket S3 e que suas credenciais AWS estejam ativas na máquina.

```bash
# O script irá consultar o Athena e imprimir os resultados
python analysis/analytics_job.py
```

O sucesso dessas consultas confirma que todo o pipeline ELT está operacional e que os relatórios de negócio estão prontos para o consumo.

-----

## 🧠 Metodologia e Produtividade

Este projeto foi desenvolvido utilizando uma abordagem de **Engenharia Aumentada por IA (AI-Augmented Engineering)**. O modelo de linguagem **Gemini (Google)** foi utilizado como um *pair programmer* arquitetural para:

1.  **Orquestração Serverless:** Implementar o **AWS Step Functions** como orquestrador central, elevando o pipeline a um nível profissional com monitoramento e controle de fluxo.
2.  **Idempotência e Versionamento:** Adotar a estratégia de *timestamp* na Landing Zone para garantir a imutabilidade do dado *raw* e a leitura da última versão pelo processamento ETL.
3.  **Otimização de Custos e Segurança:** Orientação na configuração eficiente dos recursos (Lambda, Glue Workers) e uso de IAM Roles, mantendo o custo AWS baixo e a segurança em alta.

Esta metodologia visa demonstrar proficiência em ferramentas de IA para **ganho de produtividade**, mantendo total controle e entendimento das decisões arquiteturais tomadas.
