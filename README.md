# 🚕 Desafio Técnico: Engenharia de Dados NYC Taxi Trips

Este repositório contém uma solução completa de Engenharia de Dados para ingestão, processamento e análise dos dados de viagens de táxi de Nova York, conforme proposto no desafio técnico.

A solução é construída usando uma stack **Serverless e Cloud-Native (AWS)** e um motor de processamento moderno (**AWS Glue Serverless/PySpark**), demonstrando habilidades em IaC, ETL/ELT e Data Quality.

-----

## 🚀 Stack Tecnológica Escolhida

| Etapa do Pipeline | Tecnologia/Serviço | Finalidade no Projeto |
| :--- | :--- | :--- |
| **Orquestração** | **AWS Step Functions** | **Controlador Serverless.** Gerencia o *workflow* completo, garantindo que a Ingestão (Lambda) termine antes que o Processamento (Glue) comece. |
| **Infraestrutura como Código (IaC)** | **Terraform** | Provisionamento seguro e automatizado do S3, Glue Job, Lambda, Step Functions, IAM Roles e Athena. |
| **Data Lake e Armazenamento** | **Amazon S3** | Armazenamento persistente de dados brutos (`/landing`) e processados (`/consumer`) em Parquet. |
| **Ingestão (EL)** | **AWS Lambda (Python/`requests`/`boto3`)** | **Função Serverless.** Baixa os arquivos e faz o upload direto para a Landing Zone, com caminho particionado por *timestamp* de ingestão. |
| **Processamento e Transformação (T)** | **AWS Glue Job (PySpark)** | **Motor ETL Serverless da AWS.** Lê a última versão dos dados (pelo *timestamp*), aplica transformações e salva na Camada de Consumo. |
| **Catálogo de Dados** | **AWS Glue Data Catalog** | Registro do *schema* da tabela de consumo para ser acessada via SQL. |
| **Disponibilização (SQL)** | **Amazon Athena** | Permite consultas SQL diretas sobre os dados Parquet do S3. |
| **Análise e Relatórios** | **Jupyter Notebook** (+ Pandas/Matplotlib) | Realização das análises solicitadas e visualização dos resultados. |

-----

## 🎯 Objetivo do Desafio

Desenvolver um pipeline ELT completo (Ingestão $\rightarrow$ Processamento $\rightarrow$ Disponibilização $\rightarrow$ Análise) para os dados de viagens de táxi de **Janeiro a Maio de 2023** da cidade de Nova York, garantindo que as colunas obrigatórias (**VendorID**, **passenger\_count**, **total\_amount**, **tpep\_pickup\_datetime**, **tpep\_dropoff\_datetime**) estejam presentes e modeladas na camada de consumo.

-----

## 1\. ⚙️ Fase 1: Provisionamento e Ingestão de Dados (EL)

Esta fase inicial cria toda a infraestrutura de Data Lake e a função AWS Lambda para ingestão via Terraform.

### 1.1. Pré-requisitos e Setup Local

Certifique-se de que você possui as seguintes ferramentas instaladas e configuradas:

1.  **Python 3.x** e `pip`.
2.  **Terraform CLI**.
3.  **AWS CLI** configurado (via `aws configure`) com credenciais que tenham permissões de `Admin` ou as políticas específicas para S3, Glue, Lambda, Step Functions e IAM.

### Instalação de Dependências Python

O setup local é mínimo, pois o processamento principal ocorre na nuvem. Apenas as bibliotecas para *Análise* são necessárias.

```bash
pip3 install pandas matplotlib
````

### 1.2. Provisionamento da Infraestrutura com Terraform (IaC)

O código Terraform (localizado na pasta `infra/`) cria todos os recursos necessários, incluindo o **AWS Step Functions** para orquestração.

**NOTA SOBRE O ESTADO:** Para simplificar a execução do avaliador, o estado do Terraform (`terraform.tfstate`) será armazenado **localmente** na pasta `infra/`.

**ATENÇÃO:** Edite o arquivo `main.tf` e substitua as *placeholders* pelo nome único do seu bucket S3 antes de prosseguir.

```bash
# Navega para a pasta do Terraform
cd infra/

# 1. Inicializa o ambiente Terraform (o estado local será criado)
terraform init

# 2. Visualiza o plano de execução (recursos a serem criados)
terraform plan

# 3. Aplica o plano, criando toda a infraestrutura na AWS
terraform apply --auto-approve
```

### 1.3. Execução da Ingestão e Orquestração (ELT)

A execução do *pipeline* completo de ELT agora é feita via o orquestrador **AWS Step Functions**, garantindo o fluxo: **Ingestão (Lambda) $\rightarrow$ Processamento (Glue Job)**.

> **NOTA SOBRE IDEMPOTÊNCIA:** A Landing Zone agora salva os dados com um *timestamp* de ingestão (`ingest_ts`) no caminho S3. O Glue Job será configurado para **sempre processar a versão mais recente** para cada mês, garantindo que re-execuções não causem duplicação e que a camada de consumo seja baseada nos dados mais frescos.

#### 1.3.1. Execução Padrão (Valores Iniciais do Desafio)

O Step Function aceita um *payload* JSON que é repassado ao Lambda, permitindo o controle de quais meses/anos serão ingeridos. A invocação sem um *payload* específico usará os valores *default* (Janeiro a Maio de 2023).

```bash
# O ARN da State Machine pode ser obtido na saída do Terraform, ex:
STATE_MACHINE_ARN="arn:aws:states:us-east-1:123456789012:stateMachine:nyc-taxi-elt-pipeline" 

# Invoca o Step Function, passando um payload vazio ({}) para usar defaults
aws stepfunctions start-execution \
    --state-machine-arn $STATE_MACHINE_ARN \
    --name "Run-$(date +%Y%m%d%H%M%S)" \
    --input '{}'
```

#### 1.3.2. Execução Customizada (Exemplo: Julho de 2024, Apenas Yellow)

Para ingerir dados de um período diferente, passe um objeto JSON no campo `--input`:

```bash
# Payload para customizar a execução: ano 2024, mês 07, apenas yellow
INPUT='{"year": "2024", "months": ["07"], "trip_types": ["yellow"]}'

aws stepfunctions start-execution \
    --state-machine-arn $STATE_MACHINE_ARN \
    --name "Run-July2024-$(date +%Y%m%d%H%M%S)" \
    --input "$INPUT"
```

#### Saída Esperada (Verificação)

Verifique o Console do **AWS Step Functions** para visualizar o gráfico de execução em tempo real. O sucesso da execução indica que todo o pipeline (Lambda e Glue Job) foi concluído.

### ⚠️ Solução de Problemas Comuns (Troubleshooting)

Se, ao rodar o `terraform apply`, você encontrar o erro `AccessDenied` (Código 403) na criação de qualquer recurso AWS, isso indica que as credenciais AWS configuradas não possuem as permissões necessárias.

**Ação:** O usuário IAM configurado via `aws configure` **deve ter permissões de administrador** ou, no mínimo, as políticas específicas para **S3, Glue, Lambda, Step Functions e IAM** anexadas. Tente rodar o `terraform apply --auto-approve` novamente após corrigir as permissões no Console AWS/IAM.

-----

## 2\. 🧩 Fase 2: Processamento e Data Quality (T)

Nesta fase, o código PySpark processa os dados da Landing Zone, aplica transformações, garante a Qualidade de Dados (DQ) e salva o resultado na **Camada de Consumo**.

### 2.1. Lógica do PySpark (Seleção da Última Versão)

O script `process_data_glue.py` deve conter a lógica para identificar e processar a versão mais recente dos dados:

1.  Ler todos os dados da Landing Zone.
2.  Usar funções do Spark SQL ou `Window Functions` para identificar o valor **máximo** do campo `ingest_ts` para cada `partition_date`.
3.  Filtrar o *DataFrame* para reter apenas as linhas correspondentes ao último `ingest_ts`.
4.  Aplicar transformações ETL e regras de Data Quality.

### 2.2. Execução do Job AWS Glue

O Job ETL será iniciado automaticamente pelo Step Functions.

**Atenção ao Custo:** O Job Glue está configurado com `Worker Type: G.025X` e `Number of Workers: 2`. O custo por execução é **baixo** (pagamento por segundo), mas é um recurso pago pela AWS.

**Próximos Passos:**

1.  Finalize o script `process_data_glue.py` com a lógica de seleção da última versão.
2.  **Rode o `terraform apply`** (se ainda não o fez) para garantir que a versão mais recente do script foi enviada para o S3.

-----

## 3\. 🔍 Fase 3: Análise e Consumo de Dados

Nesta fase, os dados são acessados via SQL (Athena) e analisados em um Notebook.

1.  **Verificação no Athena:** No Console da AWS, use o **Amazon Athena** para consultar a tabela `trips_consumer` criada pelo Terraform.
    ```sql
    SELECT count(*) FROM "nyc_taxi_db"."trips_consumer";
    ```
2.  **Análise no Notebook:** Abra o Jupyter e execute o Notebook (`analysis.ipynb`) que se conecta ao Athena (via PyAthena ou similar) ou lê o Parquet final do S3 para gerar as visualizações e *insights* solicitados.

-----

## 🗑️ Limpeza de Recursos (Obrigatório)

Para evitar custos indesejados na sua conta AWS, **SEMPRE** destrua a infraestrutura após o término da avaliação.

```bash
cd infra/
terraform destroy --auto-approve
```

-----

## 🧠 Metodologia e Produtividade

Este projeto foi desenvolvido utilizando uma abordagem de **Engenharia Aumentada por IA (AI-Augmented Engineering)**. O modelo de linguagem **Gemini (Google)** foi utilizado como um *pair programmer* arquitetural para:

1.  **Orquestração Serverless:** Implementar o **AWS Step Functions** como orquestrador central, elevando o pipeline a um nível profissional com monitoramento e controle de fluxo.
2.  **Idempotência e Versionamento:** Adotar a estratégia de *timestamp* na Landing Zone para garantir a imutabilidade do dado *raw* e a leitura da última versão pelo processamento ETL.
3.  **Otimização de Custos e Segurança:** Orientação na configuração eficiente dos recursos (Lambda, Glue Workers) e uso de IAM Roles, mantendo o custo AWS baixo e a segurança em alta.

Esta metodologia visa demonstrar proficiência em ferramentas de IA para **ganho de produtividade**, mantendo total controle e entendimento das decisões arquiteturais tomadas.
