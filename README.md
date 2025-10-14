# 🚕 Desafio Técnico: Engenharia de Dados NYC Taxi Trips

Este repositório contém uma solução completa de Engenharia de Dados **Serverless** para ingestão, processamento e **análise pré-agregada** dos dados de viagens de táxi de Nova York.

A arquitetura utiliza uma stack **Cloud-Native (AWS)** com orquestração centralizada no **AWS Step Functions**, garantindo um fluxo ELT robusto: **Landing** $\rightarrow$ **Consumer** $\rightarrow$ **Reporting**.

-----

## 🚀 Stack Tecnológica e Arquitetura Final

| Etapa do Pipeline | Tecnologia/Serviço | Finalidade no Projeto |
| :--- | :--- | :--- |
| **Orquestração** | **AWS Step Functions** | **Controlador Serverless.** Gerencia o *workflow* completo e é responsável por orquestrar a **execução paralela (fan-out)** dos Jobs de Processamento por mês e tipo de viagem. |
| **Infraestrutura como Código (IaC)** | **Terraform** | Provisionamento seguro e automatizado de **todos** os recursos (S3, Glue Jobs, Lambda, Step Functions, IAM Roles e Tabelas do Athena). |
| **Data Lake e Armazenamento** | **Amazon S3 / Delta Lake** | Armazenamento persistente nas camadas: `landing`, `consumer` (Delta/Parquet) e `analytics/reporting` (Parquet pré-agregado). |
| **Ingestão (EL)** | **AWS Lambda (Python)** | Baixa os arquivos e faz o upload para a **Landing Zone**, particionado por *timestamp* de ingestão. |
| **Processing (T - Camada Consumer)** | **AWS Glue Job (PySpark)** | **Motor ETL Serverless.** Lê a última versão dos dados, aplica Data Quality (DQ), unifica o *schema* e salva na **Camada Consumer** (Delta Lake). |
| **Reporting (T - Camada Reporting)** | **AWS Glue Job (PySpark)** | **Motor ETL Serverless.** Executa as agregações **Q1 e Q2** e salva os relatórios na **Camada Reporting** (pronto para consumo). |
| **Catálogo de Dados** | **AWS Glue Data Catalog** | Registro do *schema* de todas as tabelas para acesso via SQL (Athena). |
| **Consumo e Análise Ad-Hoc** | **Amazon Athena / PyAthena** | Permite consultas SQL diretas e de baixo custo sobre os relatórios pré-agregados. |

-----

## 💰 FinOps: Gestão de Custos Serverless

A arquitetura **Serverless** (Lambda, Glue, Step Functions) oferece um excelente balanço entre performance e custo, seguindo o princípio **pay-per-use**.

### Principais Drivers de Custo

  * **AWS Glue (DPUs):** Componente de maior custo potencial, baseado em **DPUs (Data Processing Units) por hora**. Mitigado por Glue 3.0 e otimização do tempo de execução.
  * **Amazon S3 (Armazenamento):** Custo contínuo para manter os dados nas três camadas.

### Boas Práticas FinOps

* **Destruição Imediata:** Após o teste e validação, utilize o comando `make destroy` para desprovisionar toda a infraestrutura e evitar cobranças recorrentes.

-----

## 🎯 Objetivo e Transformação

O objetivo é processar os dados de viagens de táxi de **Janeiro a Maio de 2023** e disponibilizar, na **Camada Reporting**, as seguintes análises prontas:

1.  **Q1:** Média de valor total (`total_amount`) por mês.
2.  **Q2:** Média de passageiros por cada hora do dia, agrupado por tipo de viagem.

-----

## 1\. ⚙️ Setup, Deploy e Execução do ELT

### 1.1. Pré-requisitos e Setup Local

1.  **Python 3.x**, **`pip`**, **`make`** e **Terraform CLI**.
2.  **AWS CLI** configurado com credenciais de acesso apropriadas.
3.  **Configuração do Bucket:** Antes de rodar o `make deploy`, edite o arquivo `infra/main.tf` e defina o nome desejado e único para o seu *bucket* S3 na variável `data_lake_bucket_name`.

### 1.2. Provisionamento da Infraestrutura (IaC)

Utilize o **`Makefile`** para automatizar o *build* e o deploy via Terraform.

| Comando | Ação Executada | Observações |
| :--- | :--- | :--- |
| **`make deploy`** | **Execução Completa.** Prepara o pacote Lambda e executa o `terraform apply --auto-approve`. | Comando principal de *setup* e deployment. |
| **`make destroy`** | **Destrói toda a infraestrutura da AWS.** | **CUIDADO: Apaga dados no S3.** |
| **`make clean`** | Limpeza Local | Remove artefatos temporários e de cache. |

### 1.3. Execução da Orquestração (Pipeline Dinâmico)

O Step Function aceita um *payload* JSON para definir a execução em lote por `months` e `trip_types`.

**Payload de Exemplo (Execução em Lote):**

```json
{
  "datalakeBucket": "nyc-taxi-data-lake-jha-case-ifood",
  "year": "2023",
  "months": ["02", "03", "04", "05"],
  "trip_types": ["yellow", "green"]
}
````

**Execução Customizada:**

```bash
# Obtenha o ARN da State Machine na saída do Terraform
STATE_MACHINE_ARN="ARN_DA_SUA_STATE_MACHINE" 

# Exemplo de invocação com payload customizado
INPUT='{"datalakeBucket": "nyc-taxi-data-lake-jha-case-ifood", "year": "2024", "months": ["07"], "trip_types": ["yellow"]}'

aws stepfunctions start-execution \
    --state-machine-arn $STATE_MACHINE_ARN \
    --name "Run-Custom-Batch-$(date +%Y%m%d%H%M%S)" \
    --input "$INPUT"
```

-----

## 2\. 🧩 Reporting e Consumo Final de Dados

Após a conclusão do Job de Reporting, os relatórios agregados estão disponíveis na **Camada Reporting** do S3 (`/analytics/reporting/`) e catalogados pelo Glue Data Catalog.


### Tabelas do Glue Catalog para Consulta

| Tabela | Análise |
| :--- | :--- |
| `q1_monthly_revenue` | Média Mensal de Receita |
| `q2_hourly_passengers` | Média Horária de Passageiros |

### Acesso via Amazon Athena (SQL)

No Console do **Amazon Athena**, execute:

```sql
SELECT 
    report_month, 
    ROUND(avg_total_amount, 2) AS avg_revenue
FROM 
    "nyc_taxi_db"."q1_monthly_revenue"
ORDER BY 
    report_month;
```

### Acesso Programático Local (Script PyAthena)

Instale as dependências locais e execute o script `analysis/analytics_job.py`:

```bash
# Instala o driver do Athena e o Pandas
pip3 install pyathena[pandas]

# O script irá consultar o Athena e imprimir os resultados
python analysis/analytics_job.py
```

-----

## 3\. 💡 Melhorias e Próximos Passos (To-Do)

A solução atual é funcional, mas esta lista de melhorias visa aumentar a **resiliência**, a **performance** e a **governança** do pipeline, abordando lições aprendidas nos testes.

### 3.1. Resolução de Inconsistência de Schema (Mês 1)

Oportunidade | Descrição | Justificativa Arquitetural |
| :--- | :--- | :--- |
**Tratamento Robusto de Schema Drift (Mês 1)** | Os testes indicaram falha no processamento dos dados do Mês 1 (Janeiro), sugerindo uma **inconsistência de tipo de dado (schema drift)** não tratada. Ação (To-Do): Implementar a definição de *schema* estrito para colunas críticas e configurar o Spark para mover registros inválidos para uma Dead Letter Queue (DLQ), isolando o problema e permitindo o processamento contínuo dos dados válidos. | Corrige a falha de processamento observada no Mês 1, garantindo que o pipeline seja tolerante a dados malformados e inconsistências de tipo. |

### 3.2. Melhorias de Resiliência e Data Quality (DQ)

| Oportunidade | Descrição | Justificativa Arquitetural |
| :--- | :--- | :--- |
| **Monitoramento Ativo de DQ** | Implementar uma biblioteca de DQ (como **GDQ** ou **Great Expectations**) no Job de Processing. Definir regras (ex: `total_amount` nunca deve ser negativo) e criar um **Alerta SNS/CloudWatch** se uma regra falhar. | Migra de uma checagem de DQ passiva (filtros) para um monitoramento ativo, alertando *antes* que dados ruins cheguem ao Reporting. |
| **Integração com AWS Lake Formation** | Aplicar políticas de segurança e acesso granular baseadas em tags nas tabelas do Glue Catalog (ex: restringir o acesso a colunas sensíveis, se houvesse, como dados de motorista). | Garante um Data Lake seguro, controlando quem pode consultar as camadas Consumer e Reporting (Governança e Segurança). |
| **Data Lineage (Linhagem de Dados)** | Configurar o AWS Glue para registrar a linhagem de dados, ou usar o *logging* do Delta Lake (Audit History). | Essencial para *troubleshooting* e auditoria. Permite rastrear um valor do Reporting de volta à Landing Zone. |

### 3.3. Melhorias na Experiência do Desenvolvedor (DX)

| Oportunidade | Descrição | Justificativa Arquitetural |
| :--- | :--- | :--- |
| **Testes Unitários/Integração** | Adicionar um *framework* de testes (ex: **Pytest**) para testar as funções PySpark de transformação (`apply_data_quality_and_transform`) localmente, antes do deploy no Glue. | Aumenta a confiança no código e reduz o ciclo de desenvolvimento/depuração no ambiente de nuvem, que é mais lento e caro. |
| **CI/CD Simplificado** | Integrar o pipeline Terraform/make deploy com um serviço de CI/CD (ex: GitHub Actions ou AWS CodePipeline) para automatizar o deploy a cada *merge* na *branch* `main`. | Migra para um fluxo de trabalho DevOps completo, garantindo que a infraestrutura seja deployada consistentemente a partir do código fonte. |

-----

## 🧠 Metodologia e Produtividade

Este projeto foi desenvolvido utilizando uma abordagem de **Engenharia Aumentada por IA (AI-Augmented Engineering)**, onde o modelo **Gemini (Google)** atuou como um *pair programmer* arquitetural. Esta metodologia visa demonstrar proficiência em ferramentas de IA para **ganho de produtividade**, mantendo total controle e entendimento das decisões arquiteturais tomadas.
