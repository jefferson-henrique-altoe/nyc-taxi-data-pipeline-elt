from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
import pyspark.sql.functions as F
import sys # Necessário para getResolvedOptions
from pyspark.sql.types import StringType # 🚨 IMPORTAÇÃO NOVA: Para forçar o tipo de dado
try:
    from awsglue.utils import getResolvedOptions
except ImportError:
    pass

# 1. Configuração do Glue

# --- Variáveis de Caminho ---
# O nome do bucket é passado como argumento do Glue Job (Ex: --datalake-bucket)
try:
    # 🚨 OBTÉM o novo argumento trip_type_filter passado pelo Step Function
    args = getResolvedOptions(sys.argv, ['JOB_NAME', 'datalake_bucket', 'trip_type_filter'])
    S3_BUCKET_NAME = args['datalake_bucket']
    TRIP_TYPE_FILTER = args['trip_type_filter']
except Exception:
    # Caso não esteja rodando com argumentos (ex: teste local)
    S3_BUCKET_NAME = "nyc-taxi-data-lake-jha-case-ifood"
    TRIP_TYPE_FILTER = "yellow" # Default para teste local
    print(f"ATENÇÃO: Usando valores default S3: {S3_BUCKET_NAME}, Trip Type: {TRIP_TYPE_FILTER}")
    
# 🚨 NOVO: O LANDING_PATH AGORA É FILTRADO PELO TIPO DE VIAGEM!
# O S3 armazena os dados na Landing Zone particionados como 'trip_type=yellow/'
LANDING_PATH    = f"s3a://{S3_BUCKET_NAME}/landing/trip_type={TRIP_TYPE_FILTER}/"
# 🚨 NOVO: O CONSUMER_PATH AGORA É SEPARADO POR TIPO DE VIAGEM!
CONSUMER_PATH  = f"s3a://{S3_BUCKET_NAME}/consumer/trips_delta/{TRIP_TYPE_FILTER}/"

# Colunas OBRIGATÓRIAS e colunas de partição a serem mantidas
# NOTA: Removemos os mapeamentos de datetime daqui, pois serão tratados dinamicamente.
COLUMNS_MAPPING = {
    "VendorID": "vendor_id",
    "passenger_count": "passenger_count",
    "total_amount": "total_amount",
    # Os campos de data/hora serão resolvidos dinamicamente na função
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
    """Aplica transformações e regras de Data Quality (DQ) e unifica schemas."""
    
    # Lógica de unificação de schemas (já existente):
    # 1. Checa o prefixo 'lpep_' (Green)
    if "lpep_pickup_datetime" in df.columns:
        df = df.withColumnRenamed("lpep_pickup_datetime", "pickup_datetime") \
               .withColumnRenamed("lpep_dropoff_datetime", "dropoff_datetime")
    
    # 2. Checa o prefixo 'tpep_' (Yellow)
    elif "tpep_pickup_datetime" in df.columns:
        df = df.withColumnRenamed("tpep_pickup_datetime", "pickup_datetime") \
               .withColumnRenamed("tpep_dropoff_datetime", "dropoff_datetime")
                
    # Agora, 'pickup_datetime' e 'dropoff_datetime' existem, independentemente da origem.

    # 1. Seleção e Renomeação de Colunas
    
    # Adicionamos os campos de data/hora unificados (pickup_datetime, dropoff_datetime) 
    # e as colunas VendorID, passenger_count, total_amount, além das partições.
    
    selection_cols = [F.col(k).alias(v) for k, v in COLUMNS_MAPPING.items()] + \
                     [F.col("pickup_datetime"), F.col("dropoff_datetime")] + \
                     [F.col(c) for c in PARTITION_COLUMNS]
    
    df_transformed = df.select(*selection_cols)
    
    # 2. Regras de Data Quality (DQ)
    # Ajustando filtros para serem mais flexíveis (total_amount >= 0 para incluir cancelamentos/erros)
    df_dq = df_transformed.filter(F.col("passenger_count").isNotNull() & (F.col("passenger_count") >= 0))
    df_dq = df_dq.filter(F.col("total_amount").isNotNull())
    df_dq = df_dq.filter(F.col("pickup_datetime").isNotNull() & F.col("dropoff_datetime").isNotNull())

    # 3. Engenharia de Features (Criação de Partição para o Sink)
    df_dq = df_dq.withColumn("trip_year", F.year(F.col("pickup_datetime")))
    df_dq = df_dq.withColumn("trip_month", F.month(F.col("pickup_datetime")))
    
    return df_dq

# 4. Orquestração e Execução
if __name__ == '__main__':
    
    # Configuração para garantir que o Spark tente inferir o tipo de dados correto
    spark.conf.set("spark.sql.sources.partitionColumnTypeInference.enabled", "true") 
    
    print(f"Iniciando leitura da Landing Zone FILTRADA para: {TRIP_TYPE_FILTER} em: {LANDING_PATH}")
    
    # 🚨 CORREÇÃO CRÍTICA: Leitura Direta via Spark
    # A leitura agora é apenas para o tipo de viagem atual (Yellow ou Green), 
    # garantindo que o schema seja consistente.
    df_landing = spark.read.parquet(LANDING_PATH)
    
    # 🚨 CORREÇÃO DE INFERÊNCIA CRÍTICA: Adiciona a coluna 'trip_type' manualmente.
    # O Spark não infere esta coluna quando o caminho já está filtrado por ela ('trip_type=yellow/').
    # Precisamos adicioná-la de volta ao DataFrame com o valor do filtro, para que possa ser usada 
    # na seleção de colunas e na escrita subsequente.
    df_landing = df_landing.withColumn("trip_type", F.lit(TRIP_TYPE_FILTER))

    # 🚨 CORREÇÃO DE SCHEMA 1: Converte a coluna VendorID para String para evitar conflitos IntegerType vs LongType
    # Mantemos esta conversão como uma camada de proteção.
    if "VendorID" in df_landing.columns:
        df_landing = df_landing.withColumn("VendorID", F.col("VendorID").cast(StringType()))
    
    print(f"Schema do DataFrame lido (Verifique PARTITION_COLUMNS abaixo):")
    df_landing.printSchema()
    
    # Ponto de Verificação CRÍTICO (agora mais confiável):
    # Garantir que as colunas de partição foram inferidas corretamente
    for col in PARTITION_COLUMNS:
        if col not in df_landing.columns:
            # Esta exceção só deve ser lançada se a estrutura no S3 não for 'key=value/'
            # Como corrigimos adicionando 'trip_type' manualmente, esta checagem agora é mais robusta para 'partition_date'.
            raise Exception(f"ERRO: Coluna de partição '{col}' não foi inferida. Verifique se a estrutura S3 em '{LANDING_PATH}' está correta (key=value/).")

    print(f"Registros lidos: {df_landing.count()}")

    # 5. Transformação e DQ 
    df_consumer = apply_data_quality_and_transform(df_landing)

    # 6. Escrita em Delta Lake (Sink)
    # A escrita é feita em um caminho exclusivo para o tipo de viagem atual (CONSUMER_PATH inclui o filtro)
    print(f"Iniciando escrita da camada Consumer (Delta Lake) em: {CONSUMER_PATH}")
    
    # Usamos 'overwrite' porque estamos sobrescrevendo apenas a partição específica (yellow ou green)
    df_consumer.write.mode("overwrite") \
             .format("delta") \
             .option("mergeSchema", "true") \
             .partitionBy("trip_year", "trip_month") \
             .save(CONSUMER_PATH)

    print("Escrita em Delta Lake concluída.")
    job.commit()
