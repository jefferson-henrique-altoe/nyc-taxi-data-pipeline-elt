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
| **Processing (T - Camada Consumer)** | **AWS Glue Job (PySpark)** | **Motor ETL Serverless.** Lê a última versão dos dados, aplica Data Quality (DQ) e salva na **Camada Consumer** (Delta Lake). |
| **Reporting (T - Camada Reporting)** | **AWS Glue Job (PySpark)** | **Motor ETL Serverless.** Lê a Camada Consumer, executa as agregações **Q1 e Q2** e salva os relatórios na **Camada Reporting** (pronto para consumo). |
| **Catálogo de Dados** | **AWS Glue Data Catalog** | Registro do *schema* de todas as tabelas (`trips_consumer`, `q1_monthly_revenue`, `q2_hourly_passengers`) para acesso via SQL. |
| **Consumo e Análise Ad-Hoc** | **Amazon Athena / PyAthena** | Permite consultas SQL diretas sobre os relatórios pré-agregados, garantindo baixo custo e alta performance. |

---

## 💰 FinOps: Gestão de Custos Serverless

A arquitetura **Serverless** (Lambda, Glue, Step Functions) oferece um excelente balanço entre performance e custo, seguindo o princípio **pay-per-use** (pague apenas pelo que usar), o que é ideal para *pipelines* de dados intermitentes como este.

### Principais Drivers de Custo

* **AWS Glue (DPUs):** É o componente de maior custo potencial. O preço é baseado em **DPUs (Data Processing Units) por hora**. Para mitigar isso:
    * Usamos o Glue 3.0 (mais rápido e eficiente).
    * Os Jobs são otimizados para tempo de execução mínimo (leitura de Delta e escritas em Parquet eficientes).
* **Amazon S3 (Armazenamento):** O custo principal aqui é o armazenamento dos dados nas três camadas (Landing, Consumer, Reporting). O custo por GB é baixo, mas é contínuo.
* **AWS Step Functions:** O custo é baseado no número de **transições de estado** (State Transitions), que é muito baixo, mas escalável.

### O Papel do Free Tier

A **Camada Gratuita da AWS** cobre integralmente ou parcialmente o uso de vários serviços (Lambda, S3, Step Functions) por um ano, tornando este projeto financeiramente viável para testes iniciais e aprendizado.

### Boas Práticas FinOps

Para garantir a eficiência de custos fora do Free Tier, a melhor prática FinOps neste projeto é:

* **Destruição Imediata:** Após o teste e validação, utilize o comando `make destroy` para desprovisionar toda a infraestrutura e evitar cobranças recorrentes de recursos como Volumes EBS (anexados ao Glue) ou S3, mantendo apenas o código localmente.

---

## 🎯 Objetivo e Transformação

O objetivo é processar os dados de viagens de táxi de **Janeiro a Maio de 2023** e disponibilizar, na **Camada Reporting**, as seguintes análises prontas:

1.  **Q1:** Média de valor total (`total_amount`) por mês.
2.  **Q2:** Média de passageiros por cada hora do dia, agrupado por tipo de viagem.

---

## 1\. ⚙️ Fase 1: Provisionamento e Execução do ELT

### 1.1. Pré-requisitos e Setup Local

1.  **Python 3.x**, **`pip`**, **`make`** e **Terraform CLI**.
2.  **AWS CLI** configurado (via `aws configure`) com credenciais que possuam permissões de acesso.

### 1.2. Provisionamento da Infraestrutura (IaC)

Utilize o **`Makefile`** para automatizar o *build* do pacote Lambda e a execução do Terraform. O `make deploy` é o comando principal que encapsula ambos.

| Comando | Ação Executada | Observações |
| :--- | :--- | :--- |
| **`make deploy`** | **Execução Completa.** Prepara o pacote Python da Lambda, inicializa o Terraform e executa o `terraform apply --auto-approve`. | Comando principal de *setup* e deployment. |
| **`make destroy`** | **Destrói toda a infraestrutura da AWS (CUIDADO: Apaga dados).** | |
| **`make clean`** | Remove artefatos locais (`lambda_deployment_package`, `.terraform`, `.tfstate`). | Útil para limpeza e garantia de um *build* limpo. |

### 1.3. Execução da Orquestração (Pipeline ELT Completo)

O Step Function gerencia o fluxo de três estágios. Obtenha o ARN da State Machine na saída do Terraform: `nyc-taxi-elt-pipeline`.

#### 1.3.1. Execução Padrão (Jan-Mai 2023)

```bash
# Substitua pelo seu ARN da State Machine
STATE_MACHINE_ARN="ARN_DA_SUA_STATE_MACHINE" 

# Invoca o Step Function com payload vazio ({}) para usar os valores default
aws stepfunctions start-execution \
    --state-machine-arn $STATE_MACHINE_ARN \
    --name "Run-$(date +%Y%m%d%H%M%S)" \
    --input '{}'
````

# #### 1.3.2. Execução Customizada (Exemplo: Julho de 2024, Apenas Yellow)

# Passe um objeto JSON para customizar o período de ingestão:

# ```bash
# # Payload para customizar a execução: ano 2024, mês 07, apenas yellow
# INPUT='{"year": "2024", "months": ["07"], "trip_types": ["yellow"]}'

# aws stepfunctions start-execution \
#     --state-machine-arn $STATE_MACHINE_ARN \
#     --name "Run-July2024-$(date +%Y%m%d%H%M%S)" \
#     --input "$INPUT"
# ```

# **Verificação de Falhas:** O Step Function está configurado para **falhar imediatamente** se qualquer um dos Glue Jobs (`Processing` ou `Reporting`) ou a Lambda retornar um erro, garantindo que a execução não fique travada.

#### 1.3.2. Execução Customizada (Customizando o Período e Tipos de Viagem)

O Step Function aceita um objeto JSON como input para **customizar a janela de tempo** e os **tipos de táxi** a serem processados. Se o input for `{}`, o pipeline usa os valores padrão definidos abaixo:

| Parâmetro | Tipo | Descrição | Valores Padrão (se input for `{}`) |
| :--- | :--- | :--- | :--- |
| **`year`** | `String` | O ano de referência dos dados (e.g., `"2023"`, `"2024"`). | `"2023"` |
| **`months`** | `Array<String>` | Lista de meses a serem processados, no formato de dois dígitos (e.g., `["01", "02", "03"]`). | `["01", "02", "03", "04", "05"]` |
| **`trip_types`** | `Array<String>` | Lista de tipos de táxi a serem incluídos. Tipos válidos: `yellow`, `green`, `fhv`. | `["yellow", "green", "fhv"]` |

**Exemplo de Execução Customizada (Julho de 2024, Apenas Yellow e Green):**

Passe o objeto JSON abaixo no argumento `--input`:

```bash
# Payload para customizar a execução: ano 2024, mês 07, apenas yellow e green
INPUT='{
    "year": "2024", 
    "months": ["07"], 
    "trip_types": ["yellow", "green"]
}'

aws stepfunctions start-execution \
    --state-machine-arn $STATE_MACHINE_ARN \
    --name "Run-July2024-YellowGreen-$(date +%Y%m%d%H%M%S)" \
    --input "$INPUT"

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

O consumo dos relatórios pré-agregados pode ser feito via Amazon Athena.

### 3.1. Acesso Direto via Amazon Athena (SQL)

No Console do **Amazon Athena**, selecione o banco de dados `nyc_taxi_db` e execute:

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

Instale as dependências locais e execute o script `analysis/analytics_job.py`:

```bash
# Instala o driver do Athena e o Pandas
pip3 install pyathena[pandas]

# O script irá consultar o Athena e imprimir os resultados
python analysis/analytics_job.py
```

-----

## 🧠 Metodologia e Produtividade

Este projeto foi desenvolvido utilizando uma abordagem de **Engenharia Aumentada por IA (AI-Augmented Engineering)**. O modelo de linguagem **Gemini (Google)** foi utilizado como um *pair programmer* arquitetural para:

1.  **Orquestração Serverless:** Implementar o **AWS Step Functions** como orquestrador central, elevando o pipeline a um nível profissional com monitoramento e controle de fluxo.
2.  **Idempotência e Versionamento:** Adotar a estratégia de *timestamp* na Landing Zone para garantir a imutabilidade do dado *raw* e a leitura da última versão pelo processamento ETL.
3.  **Otimização de Custos e Segurança:** Orientação na configuração eficiente dos recursos (Lambda, Glue Workers) e uso de IAM Roles, mantendo o custo AWS baixo e a segurança em alta.

Esta metodologia visa demonstrar proficiência em ferramentas de IA para **ganho de produtividade**, mantendo total controle e entendimento das decisões arquiteturais tomadas.
