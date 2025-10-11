# infra/main.tf

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