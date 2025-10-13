# 🚕 Desafio Técnico: Engenharia de Dados NYC Taxi Trips

Este repositório contém uma solução completa de Engenharia de Dados **Serverless** para ingestão, processamento e **análise pré-agregada** dos dados de viagens de táxi de Nova York.

A arquitetura utiliza uma stack **Cloud-Native (AWS)** com orquestração centralizada no **AWS Step Functions**, garantindo um fluxo ELT robusto: **Landing** $\rightarrow$ **Consumer** $\rightarrow$ \*\*Reporting$.

-----

## 🚀 Stack Tecnológica e Arquitetura Final

| Etapa do Pipeline | Tecnologia/Serviço | Finalidade no Projeto |
| :--- | :--- | :--- |
| **Orquestração** | **AWS Step Functions** | **Controlador Serverless.** Gerencia o *workflow* e utiliza o estado `Map` para paralelizar o processamento por mês e tipo de viagem. |
| **Infraestrutura como Código (IaC)** | **Terraform** | Provisionamento seguro e automatizado de **todos** os recursos (S3, Glue Jobs, Lambda, Step Functions, IAM Roles e Tabelas do Athena). |
| **Data Lake e Armazenamento** | **Amazon S3** | Armazenamento persistente nas camadas: `landing`, `consumer` (Delta/Parquet) e `analytics/reporting` (Parquet pré-agregado). |
| **Ingestão (EL)** | **AWS Lambda (Python)** | Baixa os arquivos e faz o upload para a **Landing Zone**, particionado por *timestamp* de ingestão. |
| **Processing (T - Camada Consumer)** | **AWS Glue Job (PySpark)** | **Motor ETL Serverless.** Lê a última versão dos dados, aplica Data Quality (DQ) e salva na **Camada Consumer** (Delta Lake). |
| **Reporting (T - Camada Reporting)** | **AWS Glue Job (PySpark)** | **Motor ETL Serverless.** Lê a Camada Consumer, executa as agregações **Q1 e Q2** e salva os relatórios na **Camada Reporting** (pronto para consumo). |
| **Catálogo de Dados** | **AWS Glue Data Catalog** | Registro do *schema* de todas as tabelas (`trips_consumer`, `q1_monthly_revenue`, `q2_hourly_passengers`) para acesso via SQL. |
| **Consumo e Análise Ad-Hoc** | **Amazon Athena / PyAthena** | Permite consultas SQL diretas sobre os relatórios pré-agregados, garantindo baixo custo e alta performance. |

-----

## 💰 FinOps: Gestão de Custos Serverless

A arquitetura **Serverless** (Lambda, Glue, Step Functions) oferece um excelente balanço entre performance e custo, seguindo o princípio **pay-per-use** (pague apenas pelo que usar), o que é ideal para *pipelines* de dados intermitentes como este.

### Principais Drivers de Custo

  * **AWS Glue (DPUs):** É o componente de maior custo potencial. O preço é baseado em **DPUs (Data Processing Units) por hora**. Para mitigar isso:
      * Usamos o Glue 3.0 (mais rápido e eficiente).
      * Os Jobs são otimizados para tempo de execução mínimo (leitura de Delta e escritas em Parquet eficientes).
  * **Amazon S3 (Armazenamento):** O custo principal aqui é o armazenamento dos dados nas três camadas (Landing, Consumer, Reporting). O custo por GB é baixo, mas é contínuo.
  * **AWS Step Functions:** O custo é baseado no número de **transições de estado** (State Transitions), que é muito baixo, mas escalável.

### Boas Práticas FinOps

Para garantir a eficiência de custos fora do Free Tier, a melhor prática FinOps neste projeto é:

  * **Destruição Imediata:** Após o teste e validação, utilize o comando `make destroy` para desprovisionar toda a infraestrutura e evitar cobranças recorrentes de recursos como Volumes EBS (anexados ao Glue) ou S3, mantendo apenas o código localmente.

-----

## 🎯 Objetivo e Transformação

O objetivo é processar os dados de viagens de táxi de **Janeiro a Maio de 2023** e disponibilizar, na **Camada Reporting**, as seguintes análises prontas:

1.  **Q1:** Média de valor total (`total_amount`) por mês.
2.  **Q2:** Média de passageiros por cada hora do dia, agrupado por tipo de viagem.

-----

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

-----

## 2\. 🏃‍♂️ Fase 2: Execução Dinâmica e Paralela do Pipeline

O Step Function agora suporta um *payload* dinâmico para rodar o Processamento e Reporting em paralelo para múltiplos meses e tipos de táxi, utilizando o estado `Map`.

### 2.1. Estrutura de Entrada (Payload)

O *payload* define quais dados devem ser processados e alimenta o estado `Map` para otimizar as execuções do AWS Glue.

**Payload de Exemplo (Processamento em Lote):**

```json
{
  "datalakeBucket": "nyc-taxi-data-lake-jha-case-ifood",
  "year": "2023",
  "months": [
    "02",
    "03",
    "04",
    "05"
  ],
  "trip_types": [
    "yellow",
    "green"
  ]
}
```

| Chave | Descrição | Uso |
| :--- | :--- | :--- |
| **`months`** | Lista de meses ("MM") a serem processados. | Utilizado no estado `Map` para criar execuções paralelas de ELT. |
| **`trip_types`** | Tipos de táxis a serem processados. | Utilizado no estado `Map` para criar execuções paralelas por tipo. |

### 2.2. Execução Customizada

Obtenha o ARN da State Machine na saída do Terraform: `nyc-taxi-elt-pipeline`.

```bash
# Exemplo de Payload: Processar Março e Abril de 2024 (Apenas Green)
INPUT='{
    "datalakeBucket": "nyc-taxi-data-lake-jha-case-ifood",
    "year": "2024", 
    "months": ["03", "04"], 
    "trip_types": ["green"]
}'

aws stepfunctions start-execution \
    --state-machine-arn "ARN_DA_SUA_STATE_MACHINE" \
    --name "Run-Custom-Batch-$(date +%Y%m%d%H%M%S)" \
    --input "$INPUT"
```

**Verificação de Falhas:** O Step Function está configurado para **falhar imediatamente** se qualquer Job Glue ou a Lambda retornar um erro, garantindo a integridade do *workflow*.

-----

## 3\. 🧩 Fase 3: Reporting e Disponibilização (Q1 e Q2)

Após a conclusão do Job de Reporting, os relatórios agregados estão disponíveis na **Camada Reporting** do S3 e catalogados pelo Glue Data Catalog.

### Tabelas do Glue Catalog para Consulta Final

| Tabela | Análise | Caminho no S3 |
| :--- | :--- | :--- |
| `q1_monthly_revenue` | Média Mensal de Receita | `s3://<SEU_BUCKET>/analytics/reporting/q1_monthly_revenue/` |
| `q2_hourly_passengers` | Média Horária de Passageiros | `s3://<SEU_BUCKET>/analytics/reporting/q2_hourly_passengers/` |

-----

## 4\. 🔍 Fase 4: Análise e Consumo Final de Dados

O consumo dos relatórios pré-agregados pode ser feito via Amazon Athena.

### 4.1. Acesso Direto via Amazon Athena (SQL)

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

### 4.2. Acesso Programático Local (Script PyAthena)

Instale as dependências locais e execute o script `analysis/analytics_job.py`:

```bash
# Instala o driver do Athena e o Pandas
pip3 install pyathena[pandas]

# O script irá consultar o Athena e imprimir os resultados
python analysis/analytics_job.py
```

-----

## 5\. 💡 Melhorias e Próximos Passos (To-Do)

A solução atual é funcional, mas esta lista de melhorias visa aumentar a **resiliência**, a **performance** e a **governança** do pipeline, abordando lições aprendidas nos testes.

### 5.1. Resolução de Inconsistência de Schema (Mês 1)

Durante a execução de testes, os dados do Mês 1 (Janeiro) falharam no Job de Processing, enquanto os meses subsequentes (2 a 5) foram processados com sucesso.

  * **Problema:** Isto sugere uma **inconsistência de tipo de dado (schema drift)** ou valor atípico no arquivo de Janeiro, que não foi tratado pelo esquema flexível do Spark.
  * **Ação (To-Do):** Refinar o Job de Processing para garantir a **resiliência de schema** através de:
      * Implementar um *schema* estrito para colunas críticas.
      * Adotar o tratamento de erros do Spark (`badRecordsPath`) ou mover explicitamente os registros inválidos para uma **Dead Letter Queue (DLQ)**, isolando o problema e permitindo o processamento contínuo dos dados válidos.

### 5.2. Otimização de Governança de Dados

  * **Crawler Automático:** Criar e integrar um AWS Glue Crawler ao final do Step Functions. Este Crawler deve ser acionado após a conclusão do Job de Reporting para garantir que o *schema* das tabelas `q1_monthly_revenue` e `q2_hourly_passengers` esteja sempre atualizado no Glue Catalog.

### 5.3. Otimização de Custos e Performance

  * **Filtro na Leitura do Delta:** Otimizar o Job de Reporting para usar **filtros de *pushdown*** ao ler a Camada Consumer, mesmo que a arquitetura Delta ajude. Isso minimiza a quantidade de dados lidos antes do processamento.
  * **Glue Worker Type:** Avaliar a migração do Glue Job para *Worker Type* como `G.1X` ou `G.2X` para tarefas de *reporting* mais pesadas, buscando um *sweet spot* entre o aumento de custo e o tempo de execução (tempo é dinheiro).

-----

## 🧠 Metodologia e Produtividade

Este projeto foi desenvolvido utilizando uma abordagem de **Engenharia Aumentada por IA (AI-Augmented Engineering)**. O modelo de linguagem **Gemini (Google)** foi utilizado como um *pair programmer* arquitetural para:

1.  **Orquestração Serverless:** Implementar o **AWS Step Functions** como orquestrador central, elevando o pipeline a um nível profissional com monitoramento e controle de fluxo.
2.  **Idempotência e Versionamento:** Adotar a estratégia de *timestamp* na Landing Zone para garantir a imutabilidade do dado *raw* e a leitura da última versão pelo processamento ETL.
3.  **Otimização de Custos e Segurança:** Orientação na configuração eficiente dos recursos (Lambda, Glue Workers) e uso de IAM Roles, mantendo o custo AWS baixo e a segurança em alta.

Esta metodologia visa demonstrar proficiência em ferramentas de IA para **ganho de produtividade**, mantendo total controle e entendimento das decisões arquiteturais tomadas.
