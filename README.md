# 🚕 Desafio Técnico: Engenharia de Dados NYC Taxi Trips

Este repositório contém uma solução completa de Engenharia de Dados para ingestão, processamento e análise dos dados de viagens de táxi de Nova York, conforme proposto no desafio técnico.

A solução é construída usando uma stack **Serverless e Cloud-Native (AWS)** e um motor de processamento moderno (**PySpark/Databricks CE**), demonstrando habilidades em IaC, ETL/ELT e Data Quality.

-----

## 🚀 Stack Tecnológica Escolhida

| Etapa do Pipeline | Tecnologia/Serviço | Finalidade no Projeto |
| :--- | :--- | :--- |
| **Infraestrutura como Código (IaC)** | **Terraform** | Provisionamento seguro e automatizado do S3 e AWS Glue/Athena. |
| **Data Lake e Armazenamento** | **Amazon S3** | Armazenamento persistente de dados brutos (`/landing`) e processados (`/consumer`) em Parquet. |
| **Ingestão (EL)** | **Python (`requests` e `boto3`)** | Solução de software para baixar os arquivos Parquet da TLC e carregá-los no S3. |
| **Processamento e Transformação (T)** | **PySpark** (Executado no Databricks CE ou local) | Leitura dos dados, filtragem de colunas, limpeza (Data Quality) e escrita no formato Parquet na Camada de Consumo. |
| **Catálogo de Dados** | **AWS Glue Data Catalog** | Registro do *schema* da tabela de consumo para ser acessada via SQL. |
| **Disponibilização (SQL)** | **Amazon Athena** | Permite consultas SQL diretas sobre os dados Parquet do S3. |
| **Análise e Relatórios** | **Jupyter Notebook** (+ Pandas/Matplotlib) | Realização das análises solicitadas e visualização dos resultados. |

-----

## 🎯 Objetivo do Desafio

Desenvolver um pipeline ELT completo (Ingestão $\rightarrow$ Processamento $\rightarrow$ Disponibilização $\rightarrow$ Análise) para os dados de viagens de táxi de **Janeiro a Maio de 2023** da cidade de Nova York, garantindo que as colunas obrigatórias (**VendorID**, **passenger\_count**, **total\_amount**, **tpep\_pickup\_datetime**, **tpep\_dropoff\_datetime**) estejam presentes e modeladas na camada de consumo.

-----

## 1\. ⚙️ Fase 1: Provisionamento e Ingestão de Dados (EL)

Esta fase inicial cria a infraestrutura de Data Lake via Terraform e carrega os dados brutos.

### 1.1. Pré-requisitos e Setup Local

Certifique-se de que você possui as seguintes ferramentas instaladas e configuradas:

1.  **Python 3.x** e `pip`.
2.  **Terraform CLI**.
3.  **AWS CLI** configurado (via `aws configure`) com credenciais que tenham permissões de `Admin` ou as políticas específicas para S3, Glue e IAM.

### Instalação de Dependências Python

```bash
pip3 install requests boto3 pyspark pandas
```

### 1.2. Provisionamento da Infraestrutura com Terraform (IaC)

O código Terraform (localizado na pasta `infra/`) cria o **Bucket S3** (nosso Data Lake) e o **AWS Glue Data Catalog**.

**NOTA SOBRE O ESTADO:** Para simplificar a execução do avaliador, o estado do Terraform (`terraform.tfstate`) será armazenado **localmente** na pasta `infra/`.

**ATENÇÃO:** Edite o arquivo `main.tf` e substitua as *placeholders* pelo nome único do seu bucket S3 antes de prosseguir.

```bash
# Navega para a pasta do Terraform
cd infra/

# 1. Inicializa o ambiente Terraform (o estado local será criado)
terraform init

# 2. Visualiza o plano de execução (recursos a serem criados)
terraform plan

# 3. Aplica o plano, criando o S3 Bucket, Glue Database e Tabela Athena
terraform apply --auto-approve

# Volta para a raiz do projeto e acessa a pasta src (para rodar o script Python)
cd ../src
```

### 1.3. Execução da Ingestão (Carga no S3)

O script Python `ingest_data.py` é a nossa **solução de ingestão**. Ele automatiza a extração (E) dos arquivos Parquet de Jan a Mai/2023 (Yellow e Green Taxis) do CloudFront da TLC e o upload (L) para a **Landing Zone** do S3.

**Pré-requisito:** Certifique-se de que a variável `S3_BUCKET_NAME` no `ingest_data.py` foi atualizada com o nome do bucket que o Terraform criou.

```bash
# Executa o script de Ingestão Python
python3 ingest_data.py
```

#### Saída Esperada

O script irá confirmar o upload para os 10 arquivos (5 meses x 2 tipos):

```
--- Iniciando Ingestão de Dados (2023) ---
Bucket de Destino: [SEU_BUCKET_NAME]
...
--- Processando 1/10 - Tipo: yellow, Mês: 01 ---
-> Iniciando download: [URL_DO_CLOUDFRONT]
   [SUCESSO] Upload concluído para s3://[SEU_BUCKET_NAME]/landing/yellow_tripdata_2023-01.parquet
...
--- Ingestão Concluída! ---
```

### ⚠️ Solução de Problemas Comuns (Troubleshooting)

Se, ao rodar o `terraform apply`, você encontrar o erro `AccessDenied` (Código 403) na ação `s3:CreateBucket` (ou qualquer ação IAM, como `glue:*`), isso indica que as credenciais AWS configuradas não possuem as permissões necessárias para criar os recursos.

**Como Resolver:**

O usuário IAM configurado via `aws configure` **deve ter permissões de administrador** ou, no mínimo, uma política anexada que permita as seguintes ações:

* **S3:** `s3:*` (Para criar e gerenciar o bucket de dados)
* **Glue:** `glue:*` (Para criar o Glue Database e a tabela)
* **IAM:** (Se houver *Roles* criadas), `iam:PassRole`

**Ação:**

1.  Acesse o **Console da AWS** com um usuário Administrador.
2.  Vá para o serviço **IAM** e encontre o usuário que está sendo usado no CLI.
3.  Anexe a política gerenciada pela AWS chamada **`AdministratorAccess`** ou uma política personalizada que contenha as ações listadas acima.
4.  Após a anexação, tente rodar o `terraform apply --auto-approve` novamente.

-----

## 2\. 🧩 Fase 2: Processamento e Data Quality (T)

Nesta fase, o código PySpark processa os dados da Landing Zone, aplica transformações, garante a Qualidade de Dados (DQ) e salva o resultado na **Camada de Consumo**.

*(Neste ponto, você deve criar o script PySpark e o código de Data Quality.)*

**Próximos Passos:**

1.  Crie o script `process_data.py` (código PySpark).
2.  O script deve ler de `s3://[SEU_BUCKET_NAME]/landing/`.
3.  Filtre as 5 colunas obrigatórias e aplique as regras de DQ (ex: `passenger_count > 0`).
4.  Escreva o resultado em Parquet na Camada de Consumo: `s3://[SEU_BUCKET_NAME]/consumer/trips/`.

<!-- end list -->

```bash
# Exemplo de execução (utilizando spark-submit para rodar o PySpark localmente)
spark-submit process_data.py
```

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

Para evitar custos indesejados na sua conta AWS, **SEM-PRE** destrua a infraestrutura após o término da avaliação.

```bash
cd infra/
terraform destroy --auto-approve
```

-----
## 🧠 Metodologia e Produtividade

Este projeto foi desenvolvido utilizando uma abordagem de **Engenharia Aumentada por IA (AI-Augmented Engineering)**. O modelo de linguagem **Gemini (Google)** foi utilizado como um *pair programmer* arquitetural para:

1.  **Validação de Escolhas Tecnológicas:** Confirmar a escolha do Terraform sobre o CloudFormation para portabilidade de dados (Databricks CE).
2.  **Otimização de Custos e Segurança:** Orientação na escolha da arquitetura *Serverless* (S3, Glue, Lambda) para manter o custo AWS próximo de zero (`terraform destroy`).
3.  **Geração de Código Boilerplate:** Acelerar a criação de templates IaC (Terraform) e scripts de ingestão (Python/Boto3), permitindo que o foco principal fosse direcionado para a **Lógica PySpark e Qualidade de Dados**.

Esta metodologia visa demonstrar proficiência em ferramentas de IA para **ganho de produtividade**, mantendo total controle e entendimento das decisões arquiteturais tomadas.

-----
## 💡 Ferramentas de Produtividade

A arquitetura e as decisões de implementação neste projeto foram validadas e aceleradas com o auxílio do **Gemini (Modelo de Linguagem do Google)**, utilizado como um acelerador de produtividade na fase de design de software e IaC. O foco em *best practices* foi mantido como prioridade.
