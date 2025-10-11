# infra/outputs.tf

output "data_lake_bucket_name" {
  description = "Nome do bucket S3 do Data Lake (Landing e Consumer)."
  value       = aws_s3_bucket.data_lake_bucket.id
}

output "glue_database_name" {
  description = "Nome do Banco de Dados no AWS Glue/Athena."
  value       = aws_glue_catalog_database.taxi_db.name
}

output "athena_table_location" {
  description = "Caminho S3 da tabela de consumo no Athena, onde o PySpark escreve."
  value       = aws_glue_catalog_table.trips_consumer_table.storage_descriptor[0].location
}