# --- 1. Variáveis ---
# Define o nome do bucket para facilitar a alteração (MUDAR ESTE VALOR)
variable "data_lake_bucket_name" {
  description = "Nome único do bucket S3 que será o Data Lake."
  # ESCOLHER NOME ÚNICO AQUI!
  default     = "nyc-taxi-data-lake-jha-case-ifood" 
}

# --- 2. S3 Data Lake ---

# Cria o bucket S3 principal
resource "aws_s3_bucket" "data_lake_bucket" {
  bucket = var.data_lake_bucket_name

  # ADICIONAR ISSO: Permite deletar o bucket mesmo com dados dentro.
  force_destroy = true

  tags = {
    Name    = "NYCTaxiDataLake"
    Project = "DataChallenge"
  }
}

# Garante que o bucket S3 não tenha acesso público (boa prática)
resource "aws_s3_bucket_public_access_block" "data_lake_public_access" {
  bucket = aws_s3_bucket.data_lake_bucket.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# --- 3. AWS Glue Data Catalog ---

# Cria o banco de dados lógico que o Athena usará
resource "aws_glue_catalog_database" "taxi_db" {
  name = "nyc_taxi_db"
  description = "Database para os dados de taxi de NY."
}

# Define a Tabela da Camada de Consumo (acessada pelo Athena)
# Define a Tabela da Camada de Consumo (acessada pelo Athena)
# O PySpark/Databricks deverá escrever os dados neste local e formato.
resource "aws_glue_catalog_table" "trips_consumer_table" {
  name          = "trips_consumer"
  database_name = aws_glue_catalog_database.taxi_db.name
  
  table_type    = "EXTERNAL_TABLE"
  
  # REMOVIDO: O LOCATION NÃO VAI MAIS AQUI!
  # location      = "s3://${aws_s3_bucket.data_lake_bucket.id}/consumer/trips/" # ESTAVA ERRADO

  # Parâmetros de formato
  parameters = {
    "classification" = "parquet"
    "parquet.compression" = "SNAPPY"
  }

  storage_descriptor {
    location      = "s3://${aws_s3_bucket.data_lake_bucket.id}/consumer/trips/"

    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"
    
    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
    }

    # Definição das colunas OBRIGATÓRIAS (e seus tipos de dados)
    columns {
      name = "vendorid"
      type = "bigint"
    }
    columns {
      name = "passenger_count"
      type = "bigint"
    }
    columns {
      name = "total_amount"
      type = "double"
    }
    columns {
      name = "tpep_pickup_datetime"
      type = "timestamp"
    }
    columns {
      name = "tpep_dropoff_datetime"
      type = "timestamp"
    }
    # Adicionar outras colunas se forem transformadas/mantidas
  }
}

# --- 4. IAM Role para o AWS Glue Job ---

# 4.1. Define o Trust Policy (quem pode assumir esta Role: o serviço Glue)
resource "aws_iam_role" "glue_service_role" {
  name = "Glue-Service-Role-for-NYCTaxi"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Action = "sts:AssumeRole",
        Effect = "Allow",
        Principal = {
          Service = "glue.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Project = "DataChallenge"
  }
}

# 4.2. Define a Policy de Permissões (o que a Role pode fazer)
resource "aws_iam_policy" "glue_execution_policy" {
  name        = "Glue-Execution-Policy-for-NYCTaxi"
  description = "Permissões para ler S3, escrever S3 e acessar o Glue Catalog."

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      # Permissão para o Glue usar o S3 (ler e escrever no bucket do projeto)
      {
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket",
          "s3:DeleteObject"
        ],
        Effect   = "Allow",
        Resource = [
          aws_s3_bucket.data_lake_bucket.arn,
          "${aws_s3_bucket.data_lake_bucket.arn}/*"
        ]
      },
      # Permissão para o Glue acessar o Data Catalog (essencial)
      {
        Action = [
          "glue:GetDatabase",
          "glue:GetTable",
          "glue:UpdateTable",
          "glue:CreateTable",
          "glue:DeleteTable",
          "glue:GetPartitions",
          "glue:CreatePartition",
          "glue:BatchCreatePartition",
          "glue:UpdatePartition",
          "glue:DeletePartition"
        ],
        Effect   = "Allow",
        Resource = "*" # Para o catálogo, geralmente usamos '*'
      },
      # Permissão para Logs (CloudWatch)
      {
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ],
        Effect   = "Allow",
        Resource = "arn:aws:logs:*:*:log-group:/aws-glue/jobs/*"
      },
      # Permissão para o Glue gerenciar a própria execução
      {
        Action   = "iam:PassRole",
        Effect   = "Allow",
        Resource = aws_iam_role.glue_service_role.arn
      }
    ]
  })
}

# 4.3. Anexa a Policy à Role
resource "aws_iam_role_policy_attachment" "glue_policy_attach" {
  role       = aws_iam_role.glue_service_role.name
  policy_arn = aws_iam_policy.glue_execution_policy.arn
}

# 4.4. Anexa uma Managed Policy da AWS (Permissões básicas de Glue)
# É uma boa prática complementar com a política gerenciada.
resource "aws_iam_role_policy_attachment" "glue_managed_attach" {
  role       = aws_iam_role.glue_service_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

# --- 5. Upload do Script Glue para o S3 (Automatizado pelo Terraform) ---

resource "aws_s3_object" "glue_script_upload" {
  bucket = aws_s3_bucket.data_lake_bucket.id
  # Define o caminho do script dentro do bucket
  key    = "src/process_data_glue.py"
  
  # Define o caminho do script local (Assumindo que o script está na pasta 'src/')
  source = "../src/process_data_glue.py"
  
  # Garante que o objeto S3 seja atualizado se o arquivo local mudar
  # Usa o hash do arquivo para detectar alterações
  etag = filemd5("../src/process_data_glue.py")
  
  # Define o tipo de conteúdo (bom para metadados)
  content_type = "text/x-python"
}

# --- 6. AWS Glue ETL Job ---

resource "aws_glue_job" "data_processing_job" {
  name                 = "nyc_taxi_processing_job"
  role_arn             = aws_iam_role.glue_service_role.arn
  default_arguments = {
    "--datalake-formats" = "delta"
    "--conf"             = "spark.sql.extensions=io.delta.sql.DeltaSparkSessionExtension --conf spark.sql.catalog.spark_catalog=org.apache.spark.sql.delta.catalog.DeltaCatalog"
    # Garanta que o Glue use uma versão compatível (ex: Glue 4.0/Spark 3.3+)
  }
  glue_version         = "4.0" # Versão moderna do Glue que suporta Spark 3.3
  worker_type          = "G.025X" # Tipo de máquina (G.1X é um bom ponto de partida)
  number_of_workers    = 2      # Número de workers para processamento distribuído

  # Certifica-se de que o upload do script termine antes de configurar o Job
  depends_on = [aws_s3_object.glue_script_upload]

  # Configurações do Job
  command {
    # IMPORTANTE: Você deve fazer o upload do seu script PySpark para este caminho!
    script_location = "s3://${aws_s3_bucket.data_lake_bucket.id}/src/process_data_glue.py"
    python_version  = "3"
  }

  default_arguments = {
    "--job-language" = "python"
    "--TempDir"      = "s3://${aws_s3_bucket.data_lake_bucket.id}/temp/" # Necessário para o Glue
    "--enable-job-insights" = "true" # Boa prática
  }

  # Configuração de Logs
  execution_class = "STANDARD" # Ou FLEX para economia em jobs agendados
  max_retries     = 0

  tags = {
    Project = "DataChallenge"
  }
}

# --- 7. IAM Role para o AWS Lambda (Ingestão) ---

resource "aws_iam_role" "ingestion_lambda_role" {
  name = "Lambda-Role-NYCTaxi-Ingestion"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Action = "sts:AssumeRole",
        Effect = "Allow",
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

# Policy de Permissão S3 (Ler CloudFront não requer permissão, mas o upload sim)
resource "aws_iam_policy" "ingestion_s3_policy" {
  name        = "Lambda-S3-Write-Policy"
  description = "Permissão para escrever na Landing Zone do S3."

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      # Permissão para Logs no CloudWatch (padrão)
      {
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ],
        Effect   = "Allow",
        Resource = "arn:aws:logs:*:*:*"
      },
      # Permissão para o Boto3 escrever na Landing Zone
      {
        Action = [
          "s3:PutObject",
          "s3:AbortMultipartUpload"
        ],
        Effect   = "Allow",
        Resource = "${aws_s3_bucket.data_lake_bucket.arn}/landing/*"
      }
    ]
  })
}

# Anexar Policies à Role
resource "aws_iam_role_policy_attachment" "lambda_s3_attach" {
  role       = aws_iam_role.ingestion_lambda_role.name
  policy_arn = aws_iam_policy.ingestion_s3_policy.arn
}

# --- 8. AWS Lambda: Upload e Função ---

# 8.1. Cria um arquivo ZIP do código Python para o Lambda
data "archive_file" "ingestion_zip" {
  type        = "zip"
  source_file = "../src/ingest_data.py" # Assumindo que o script Python está em src/
  output_path = "tmp/ingestion_code.zip"
}

# 8.2. Faz o upload do ZIP para o S3
resource "aws_s3_object" "lambda_code_upload" {
  bucket = aws_s3_bucket.data_lake_bucket.id
  key    = "lambda/ingest_data_code.zip"
  source = data.archive_file.ingestion_zip.output_path
  etag   = data.archive_file.ingestion_zip.output_md5
}

# 8.3. Cria a função AWS Lambda
resource "aws_lambda_function" "ingestion_function" {
  function_name    = "nyc-taxi-ingest-function"
  s3_bucket        = aws_s3_object.lambda_code_upload.bucket
  s3_key           = aws_s3_object.lambda_code_upload.key
  handler          = "ingest_data.handler" # O handler deve ser definido no seu script Python
  runtime          = "python3.11"
  role             = aws_iam_role.ingestion_lambda_role.arn
  timeout          = 300 # 5 minutos (o download pode demorar)
  memory_size      = 256 # Suficiente para downloads

  # Passa o nome do bucket como uma variável de ambiente, mais seguro.
  environment {
    variables = {
      S3_BUCKET_NAME = var.data_lake_bucket_name
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_s3_attach
  ]

  tags = {
    Project = "DataChallenge"
  }
}

# 9. IAM Role para a State Machine do Step Functions
resource "aws_iam_role" "sfn_execution_role" {
  name_prefix = "nyc-taxi-sfn-exec-role-"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "states.${data.aws_region.current.name}.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

# 10. Política para permitir a Invocação do Lambda
resource "aws_iam_policy" "sfn_lambda_invoke_policy" {
  name_prefix = "nyc-taxi-sfn-lambda-policy-"
  description = "Permite que o Step Functions invoque o Lambda de ingestão."

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = "lambda:InvokeFunction"
        # 🚨 SUBSTITUA PELO ARN DA SUA FUNÇÃO LAMBDA
        Resource = [aws_lambda_function.nyc-taxi-ingest-function.arn] 
      }
    ]
  })
}

# 11. Política para permitir o Início do Glue Job
resource "aws_iam_policy" "sfn_glue_start_job_policy" {
  name_prefix = "nyc-taxi-sfn-glue-policy-"
  description = "Permite que o Step Functions inicie o Glue Job."

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = "glue:StartJobRun"
        # 🚨 SUBSTITUA PELO ARN DO SEU GLUE JOB (Nome)
        Resource = ["arn:aws:glue:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:job/${aws_glue_job.nyc_taxi_processing_job.name}"] 
      }
    ]
  })
}

# 12. Anexa as políticas à Role de execução
resource "aws_iam_role_policy_attachment" "sfn_lambda_attach" {
  role       = aws_iam_role.sfn_execution_role.name
  policy_arn = aws_iam_policy.sfn_lambda_invoke_policy.arn
}

resource "aws_iam_role_policy_attachment" "sfn_glue_attach" {
  role       = aws_iam_role.sfn_execution_role.name
  policy_arn = aws_iam_policy.sfn_glue_start_job_policy.arn
}

# 13. Definição da State Machine (Workflow ASL)
locals {
  # Definindo o workflow (ASL) como um template JSON
  sfn_definition = jsonencode({
    Comment = "Pipeline ETL Serverless NYC Taxi (Lambda -> Glue Job)"
    StartAt = "InvokeIngestionLambda"
    States = {
      InvokeIngestionLambda = {
        Type = "Task"
        # Padrão AWS SFN: Invoca Lambda de forma síncrona
        Resource = "arn:aws:states:::lambda:invoke" 
        Parameters = {
          # Nome da função Lambda
          "FunctionName" = aws_lambda_function.nyc-taxi-ingest-function.arn
          # 🚨 CHAVE CRUCIAL: Passa todo o INPUT do Step Function como payload do Lambda
          "Payload.$"    = "$" 
        }
        Retry = [ # Exemplo de tratamento de erro: Tenta 2 vezes em caso de falha
          {
            ErrorEquals = ["Lambda.ServiceException", "Lambda.AWSLambdaException", "Lambda.SdkClientException"]
            IntervalSeconds = 2
            MaxAttempts     = 2
            BackoffRate     = 2
          }
        ]
        Next = "StartDataProcessingJob"
      }
      StartDataProcessingJob = {
        Type = "Task"
        # Padrão AWS SFN: Inicia o Glue Job e espera ele terminar
        Resource = "arn:aws:states:::glue:startJobRun.sync" 
        Parameters = {
          "JobName" = aws_glue_job.nyc_taxi_processing_job.name
          # Aqui poderiam ser passados argumentos adicionais para o Glue Job, se necessário
        }
        End = true
      }
    }
  })
}

# 14. Criação do recurso State Machine
resource "aws_sfn_state_machine" "nyc_taxi_elt_pipeline" {
  name       = "nyc-taxi-elt-pipeline"
  role_arn   = aws_iam_role.sfn_execution_role.arn
  definition = local.sfn_definition
  
  # Certifica-se de que a State Machine só seja criada após as permissões estarem prontas
  depends_on = [
    aws_iam_role_policy_attachment.sfn_lambda_attach,
    aws_iam_role_policy_attachment.sfn_glue_attach,
  ]
}
