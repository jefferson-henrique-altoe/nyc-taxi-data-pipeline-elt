from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
import pyspark.sql.functions as F
from pyspark.sql.window import Window # 🚨 NOVO: Para a lógica de ranqueamento

# 1. Configuração do Glue
# O Glue automaticamente configura o S3, eliminando a necessidade de chaves!

# --- Variáveis de Caminho ---
# O nome do bucket deve ser inferido do ambiente (melhor prática), mas usaremos o valor para o caminho
S3_BUCKET_NAME = "nyc-taxi-data-lake-jha-case-ifood"
LANDING_PATH   = f"s3a://{S3_BUCKET_NAME}/landing/" # Lemos do root da landing
CONSUMER_PATH  = f"s3a://{S3_BUCKET_NAME}/consumer/trips_delta/" # 🚨 NOVO: Caminho para tabela Delta

# Colunas OBRIGATÓRIAS (mantidas)
COLUMNS_MAPPING = {
    "VendorID": "vendor_id",
    "passenger_count": "passenger_count",
    "total_amount": "total_amount",
    "tpep_pickup_datetime": "pickup_datetime",
    "tpep_dropoff_datetime": "dropoff_datetime",
}

# 2. Definição do Contexto Glue
sc = SparkContext.getOrCreate()
glueContext = GlueContext(sc)
spark = glueContext.spark_session 
job = Job(glueContext)

# 3. Lógica de Função (Mantida)
def apply_data_quality_and_transform(df):
    """Aplica transformações e regras de Data Quality (DQ)."""
    
    print(f"Número de registros brutos (última versão) antes do DQ: {df.count()}")
    
    # 1. Seleção e Renomeação de Colunas
    df_transformed = df.select([F.col(k).alias(v) for k, v in COLUMNS_MAPPING.items()])
    
    # 2. Regras de Data Quality (DQ)
    df_dq = df_transformed.filter(F.col("passenger_count").isNotNull() & (F.col("passenger_count") > 0))
    df_dq = df_dq.filter(F.col("total_amount").isNotNull() & (F.col("total_amount") > 0))
    df_dq = df_dq.filter(F.col("pickup_datetime").isNotNull() & F.col("dropoff_datetime").isNotNull())

    # 3. Engenharia de Features (Criação de Partição)
    df_dq = df_dq.withColumn("trip_year", F.year(F.col("pickup_datetime")))
    df_dq = df_dq.withColumn("trip_month", F.month(F.col("pickup_datetime")))
    
    print(f"Número de registros após o DQ: {df_dq.count()}")
    return df_dq

# 4. Orquestração e Execução
if __name__ == '__main__':
    
    # 🚨 NOVO: Leitura e Seleção da Última Versão
    
    # O Spark/Glue infere as colunas de partição: trip_type, partition_date, ingest_ts
    print(f"Iniciando leitura de todas as versões da Landing Zone em: {LANDING_PATH}")
    df_landing = spark.read.parquet(LANDING_PATH)

    # 4.1. Definir a Window Function (Particionar por mês/tipo e ordenar por TS)
    # Colunas de partição implícitas: 'trip_type', 'partition_date' (que é YYYYMM)
    window_spec = Window.partitionBy("trip_type", "partition_date")\
                        .orderBy(F.col("ingest_ts").desc())

    # 4.2. Aplicar ranqueamento (o TS mais novo recebe rank = 1)
    df_ranked = df_landing.withColumn("rank", F.rank().over(window_spec))

    # 4.3. Filtrar apenas o rank 1 (última versão ingerida) e remover a coluna de ranqueamento
    df_latest = df_ranked.filter(F.col("rank") == 1).drop("rank")
    
    print(f"Registros filtrados (apenas última versão): {df_latest.count()}")

    # 5. Transformação e DQ
    df_consumer = apply_data_quality_and_transform(df_latest)

    # 6. Escrita em Delta Lake (Sink)
    print(f"Iniciando escrita da camada Consumer (Delta Lake) em: {CONSUMER_PATH}")
    
    # 🚨 NOVO SINK: Uso do formato 'delta'
    # NOTA: O modo 'overwrite' substitui APENAS as partições modificadas no Delta Lake
    # quando a instrução é particionada, garantindo o "Overwrite Partition".
    df_consumer.write.mode("overwrite") \
             .format("delta") \
             .partitionBy("trip_year", "trip_month") \
             .save(CONSUMER_PATH)

    print("Escrita em Delta Lake concluída.")
    job.commit()