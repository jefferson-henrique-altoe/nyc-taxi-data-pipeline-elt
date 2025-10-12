# Importações necessárias
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
import pyspark.sql.functions as F
from awsglue.dynamicframe import DynamicFrame 

# 1. Configuração do Glue

# --- Variáveis de Caminho ---
S3_BUCKET_NAME = "nyc-taxi-data-lake-jha-case-ifood"
# Leitura direta. O S3 agora contém apenas a última versão do arquivo.
LANDING_PATH   = f"s3a://{S3_BUCKET_NAME}/landing/" 
CONSUMER_PATH  = f"s3a://{S3_BUCKET_NAME}/consumer/trips_delta/" 

# Colunas OBRIGATÓRIAS e colunas de partição a serem mantidas
COLUMNS_MAPPING = {
    "VendorID": "vendor_id",
    "passenger_count": "passenger_count",
    "total_amount": "total_amount",
    "tpep_pickup_datetime": "pickup_datetime",
    "tpep_dropoff_datetime": "dropoff_datetime",
}

# Colunas de partição que o Spark deve inferir do caminho S3 (mantidas na seleção)
PARTITION_COLUMNS = ["trip_type", "partition_date"]

# 2. Definição do Contexto Glue
sc = SparkContext.getOrCreate()
glueContext = GlueContext(sc)
spark = glueContext.spark_session 
job = Job(glueContext)

# 3. Lógica de Função (Transformação e DQ)
def apply_data_quality_and_transform(df):
    """Aplica transformações e regras de Data Quality (DQ)."""
    
    # 1. Seleção e Renomeação de Colunas, incluindo as partições
    # Garante que as colunas de partição e as obrigatórias sejam selecionadas
    selection_cols = [F.col(k).alias(v) for k, v in COLUMNS_MAPPING.items()] + \
                     [F.col(c) for c in PARTITION_COLUMNS]
    
    df_transformed = df.select(*selection_cols)
    
    # 2. Regras de Data Quality (DQ)
    df_dq = df_transformed.filter(F.col("passenger_count").isNotNull() & (F.col("passenger_count") > 0))
    df_dq = df_dq.filter(F.col("total_amount").isNotNull() & (F.col("total_amount") > 0))
    df_dq = df_dq.filter(F.col("pickup_datetime").isNotNull() & F.col("dropoff_datetime").isNotNull())

    # 3. Engenharia de Features (Criação de Partição para o Sink)
    df_dq = df_dq.withColumn("trip_year", F.year(F.col("pickup_datetime")))
    df_dq = df_dq.withColumn("trip_month", F.month(F.col("pickup_datetime")))
    
    print(f"Número de registros após o DQ: {df_dq.count()}")
    return df_dq

# 4. Orquestração e Execução
if __name__ == '__main__':
    
    # Configuração para garantir que o Spark tente inferir o tipo de dados correto
    spark.conf.set("spark.sql.sources.partitionColumnTypeInference.enabled", "true") 
    
    print(f"Iniciando leitura da Landing Zone em: {LANDING_PATH}")
    
    # 🚨 CORREÇÃO PRINCIPAL: Leitura via DynamicFrame com instrução explícita de chaves.
    dynamic_frame = glueContext.create_dynamic_frame.from_options(
        connection_type="s3",
        connection_options={
            "paths": [LANDING_PATH],
            "recurse": True,
            # 🚨 CRÍTICO: Informa explicitamente as chaves de partição que o Glue deve buscar no caminho
            "partitionKeys": PARTITION_COLUMNS 
        },
        format="parquet",
        format_options={
            "mergeSchema": True 
        },
    )
    
    # Converte o DynamicFrame para um Spark DataFrame para usar as funções F.col()
    df_landing = dynamic_frame.toDF()

    # 🚨 Ponto de Verificação CRÍTICO (agora mais confiável):
    # Garantir que as colunas de partição foram inferidas corretamente
    for col in PARTITION_COLUMNS:
        if col not in df_landing.columns:
            # Esta exceção só deve ser lançada se a Lambda não estiver criando a estrutura Hive.
            raise Exception(f"ERRO: Coluna de partição '{col}' não foi inferida. Verifique se a Lambda está criando a estrutura S3 como 'key=value/'.")

    print(f"Registros lidos: {df_landing.count()}")

    # 5. Transformação e DQ (Sem ranqueamento complexo!)
    df_consumer = apply_data_quality_and_transform(df_landing)

    # 6. Escrita em Delta Lake (Sink)
    print(f"Iniciando escrita da camada Consumer (Delta Lake) em: {CONSUMER_PATH}")
    
    # O modo 'overwrite' substitui APENAS as partições (ano/mês) modificadas no Delta Lake
    df_consumer.write.mode("overwrite") \
              .format("delta") \
              .partitionBy("trip_year", "trip_month") \
              .save(CONSUMER_PATH)

    print("Escrita em Delta Lake concluída.")
    job.commit()
