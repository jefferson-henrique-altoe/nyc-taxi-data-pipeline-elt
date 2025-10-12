resource "aws_glue_catalog_table" "q1_monthly_revenue_table" {
  name             = "q1_monthly_revenue"
  database_name    = aws_glue_catalog_database.taxi_db.name
  table_type       = "EXTERNAL_TABLE"

  # Parâmetros de formato
  parameters = {
    "classification" = "parquet"
    "parquet.compression" = "SNAPPY"
  }

  storage_descriptor {
    # 🚨 APONTA PARA A PASTA FINAL DO RELATÓRIO Q1
    location      = "s3://${aws_s3_bucket.data_lake_bucket.id}/analytics/reporting/q1_avg_total_amount_monthly/"

    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"

    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
    }

    # Definição das colunas (Schema) do Relatório Q1
    columns {
      name = "report_month" # Exemplo: 2024-07
      type = "string"
    }
    columns {
      name = "avg_total_amount" # O resultado da sua agregação
      type = "double"
    }
  }
}

resource "aws_glue_catalog_table" "q2_hourly_passengers_table" {
  name             = "q2_hourly_passengers"
  database_name    = aws_glue_catalog_database.taxi_db.name
  table_type       = "EXTERNAL_TABLE"

  # Parâmetros de formato
  parameters = {
    "classification" = "parquet"
    "parquet.compression" = "SNAPPY"
  }

  storage_descriptor {
    # 🚨 APONTA PARA A PASTA FINAL DO RELATÓRIO Q2
    location      = "s3://${aws_s3_bucket.data_lake_bucket.id}/analytics/reporting/q2_avg_passengers_hourly_may/"

    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"

    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
    }

    # Definição das colunas (Schema) do Relatório Q2
    columns {
      name = "report_hour" # Exemplo: 0, 1, 2...
      type = "int"
    }
    columns {
      name = "avg_passenger_count" # O resultado da sua agregação
      type = "double"
    }
  }
}
