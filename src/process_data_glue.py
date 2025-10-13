# Importações necessárias
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
import pyspark.sql.functions as F
from awsglue.dynamicframe import DynamicFrame 

# 1. Configuração do Glue
# Para a execução com Step Function, a variável S3_BUCKET_NAME deve ser injetada via argumentos
S3_BUCKET_NAME = "nyc-taxi-data-lake-jha-case-ifood"
# Usamos s3a:// no código Python para compatibilidade com Spark/Hadoop
LANDING_PATH   = f"s3a://{S3_BUCKET_NAME}/landing/" 
CONSUMER_PATH  = f"s3a://{S3_BUCKET_NAME}/consumer/trips_delta/" 

# Colunas de partição a serem lidas (inferidas pelo Spark)
PARTITION_COLUMNS = ["trip_type", "partition_date"]

# 2. Definição do Contexto Glue
sc = SparkContext.getOrCreate()
glueContext = GlueContext(sc)
spark = glueContext.spark_session 
job = Job(glueContext)

# 3. Lógica de Função (Transformação e DQ)
def apply_data_quality_and_transform(df):
    """
    Aplica transformações e regras de Data Quality (DQ).
    Unifica colunas de data/hora (tpep_* e lpep_*) usando coalesce.
    """
    
    # 1. Unificação e Normalização de Colunas Essenciais
    df_transformed = df \
        .withColumnRenamed("VendorID", "vendor_id") \
        .withColumn(
            "pickup_datetime", 
            # Garante que a coluna de data seja preenchida, seja por tpep (Yellow) ou lpep (Green)
            F.coalesce(F.col("tpep_pickup_datetime"), F.col("lpep_pickup_datetime"))
        ) \
        .withColumn(
            "dropoff_datetime", 
            F.coalesce(F.col("tpep_dropoff_datetime"), F.col("lpep_dropoff_datetime"))
        )

    # 2. Seleção das Colunas Finais (Mantendo apenas as necessárias e padronizadas)
    # CORREÇÃO: Incluindo as colunas originais (tpep_* e lpep_*) no resultado final
    df_transformed = df_transformed.select(
        "vendor_id", 
        "passenger_count",
        "total_amount",
        # Datas Unificadas (sempre preenchidas)
        "pickup_datetime", 
        "dropoff_datetime", 
        # Datas Originais (preenchidas apenas para o tipo de táxi correspondente)
        F.col("tpep_pickup_datetime").alias("tpep_pickup_datetime"), # Garantindo a seleção
        F.col("tpep_dropoff_datetime").alias("tpep_dropoff_datetime"), 
        F.col("lpep_pickup_datetime").alias("lpep_pickup_datetime"), 
        F.col("lpep_dropoff_datetime").alias("lpep_dropoff_datetime"),
        "trip_type", 
        "partition_date" # Coluna de ingestão/partição original
    )

    # 3. Regras de Data Quality (DQ)
    # passenger_count > 0 
    df_dq = df_transformed.filter(F.col("passenger_count").isNotNull() & (F.col("passenger_count") > 0))
    # total_amount >= 0 (permite zero para cancelamentos)
    df_dq = df_dq.filter(F.col("total_amount").isNotNull() & (F.col("total_amount") >= 0))
    # Ambas as datas unificadas devem estar preenchidas
    df_dq = df_dq.filter(F.col("pickup_datetime").isNotNull() & F.col("dropoff_datetime").isNotNull())

    # 4. Engenharia de Features (Criação de Partição para o Sink)
    # As colunas de partição de destino (Consumer) devem ser baseadas no datetime da viagem
    df_dq = df_dq.withColumn("trip_year", F.year(F.col("pickup_datetime")))
    df_dq = df_dq.withColumn("trip_month", F.month(F.col("pickup_datetime")))
    
    print(f"Número de registros após o DQ: {df_dq.count()}")
    return df_dq

# 4. Orquestração e Execução
if __name__ == '__main__':
    
    # Configuração para garantir que o Spark tente inferir o tipo de dados correto
    spark.conf.set("spark.sql.sources.partitionColumnTypeInference.enabled", "true") 
    
    print(f"Iniciando leitura da Landing Zone em: {LANDING_PATH}")
    
    # Uso do leitor nativo do Spark para forçar o Partition Discovery
    try:
        df_landing = spark.read.format("parquet") \
                       .option("mergeSchema", "true") \
                       .load(LANDING_PATH)
    except Exception as e:
        # Se a leitura falhar, imprima o erro original para depuração
        print(f"Falha ao ler dados da Landing Zone: {e}")
        # Lança a exceção para que o Step Function falhe
        raise
        
    df_landing.printSchema() 

    # Garantir que as colunas de partição foram inferidas corretamente
    for col in PARTITION_COLUMNS:
        if col not in df_landing.columns:
            raise Exception(f"ERRO CRÍTICO: Coluna de partição '{col}' não foi inferida pelo Spark. Verifique se o caminho do S3 é estritamente 'key=value/'.")

    print(f"Registros lidos: {df_landing.count()}")

    # 5. Transformação e DQ
    df_consumer = apply_data_quality_and_transform(df_landing)

    # 6. Escrita em Delta Lake (Sink)
    print(f"Iniciando escrita da camada Consumer (Delta Lake) em: {CONSUMER_PATH}")

    # NOVO: Incluindo 'trip_type' como a primeira chave de partição
    # Isso garantirá a estrutura: /trips_delta/trip_type=yellow/trip_year=2023/...
    # E também: /trips_delta/trip_type=green/trip_year=2023/...
    df_consumer.write.mode("overwrite") \
            .format("delta") \
            .option("overwriteSchema", "true") \
            .partitionBy("trip_type", "trip_year", "trip_month") \
            .save(CONSUMER_PATH)

    print("Escrita em Delta Lake concluída.")
    job.commit()
