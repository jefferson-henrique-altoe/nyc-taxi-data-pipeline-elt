from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
import pyspark.sql.functions as F
from awsglue.utils import getResolvedOptions
import sys

# 1. Definição do Contexto Glue e Argumentos
sc = SparkContext.getOrCreate()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)

# Pega os argumentos passados pelo Step Functions/Glue Job
try:
    args = getResolvedOptions(sys.argv, ['JOB_NAME', 'datalake_bucket'])
    S3_BUCKET_NAME = args['datalake_bucket']
except Exception as e:
    # Fallback para o caso de teste local ou erro (usar valor padrão do TF)
    print(f"ATENÇÃO: Não foi possível obter o argumento 'datalake_bucket'. Erro: {e}. Usando fallback...")
    S3_BUCKET_NAME = "nyc-taxi-data-lake-jha-case-ifood"
    
# --- Variáveis de Caminho ---
CONSUMER_PATH  = f"s3a://{S3_BUCKET_NAME}/consumer/trips_delta/" 
REPORTING_PATH = f"s3a://{S3_BUCKET_NAME}/analytics/reporting/" 

# 2. Leitura da Tabela Delta (Camada Consumer)
print(f"Iniciando leitura da tabela Delta em: {CONSUMER_PATH}")

# Leitura com suporte Delta Lake (configurado via default_arguments no Terraform)
df_trips = spark.read.format("delta").load(CONSUMER_PATH)

# --- 3. Função de Análise e Reporting ---

def run_analytics_reporting(df):
    """
    Executa as consultas de negócio (Q1 e Q2) e salva os resultados no S3 
    (Camada Reporting), garantindo que as tabelas sejam acessíveis via Athena.
    """
    
    # Adicionando colunas de data/hora essenciais para agregação
    df_with_dates = df.withColumn("trip_year", F.year(F.col("tpep_pickup_datetime"))) \
                      .withColumn("trip_month", F.month(F.col("tpep_pickup_datetime"))) \
                      .withColumn("pickup_hour", F.hour(F.col("tpep_pickup_datetime")))
    
    # ----------------------------------------------------------------------
    # PERGUNTA 1: Média de valor total (total_amount) por mês
    # ----------------------------------------------------------------------
    
    print("\n--- Processando Q1: Média de Valor Total por Mês ---")
    
    # Cria a chave de agrupamento Ano-Mês formatada (ex: 2023-01)
    df_q1 = df_with_dates.withColumn(
        "report_month", F.concat(F.col("trip_year"), F.lit("-"), F.format_string("%02d", F.col("trip_month")))
    )

    # Calcula a média mensal
    df_result_q1 = df_q1.groupBy("report_month").agg(
        F.avg("total_amount").alias("avg_total_amount")
    ).orderBy("report_month")

    # Salva o resultado no S3 Reporting (Pasta Q1)
    output_path_q1 = f"{REPORTING_PATH}q1_monthly_revenue/"
    print(f"Salvando resultados da Q1 em: {output_path_q1}")
    df_result_q1.write.mode("overwrite").parquet(output_path_q1)


    # ----------------------------------------------------------------------
    # PERGUNTA 2: Média de passageiros por cada hora do dia, por tipo de viagem
    # ----------------------------------------------------------------------
    
    print("\n--- Processando Q2: Média de Passageiros por Hora e Tipo de Viagem ---")
    
    # Agrupamento pela hora e cálculo da média de passageiros (incluindo o tipo de viagem)
    df_result_q2 = df_with_dates.groupBy("pickup_hour", "trip_type").agg(
        F.avg("passenger_count").alias("avg_passenger_count")
    ).withColumnRenamed("pickup_hour", "report_hour") # Renomeia para o catálogo
    
    # Salva o resultado no S3 Reporting (Pasta Q2)
    output_path_q2 = f"{REPORTING_PATH}q2_hourly_passengers/"
    print(f"Salvando resultados da Q2 em: {output_path_q2}")
    df_result_q2.write.mode("overwrite").parquet(output_path_q2)

    print("\n--- Relatórios Q1 e Q2 criados na Camada Reporting. ---")

# 4. Orquestração e Execução
if __name__ == '__main__':
    run_analytics_reporting(df_trips)
    job.commit()
