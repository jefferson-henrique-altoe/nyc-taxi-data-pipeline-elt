# Importações necessárias
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
import pyspark.sql.functions as F
from awsglue.dynamicframe import DynamicFrame
from awsglue.utils import getResolvedOptions
import sys
import boto3 # NOVO: Importação para integração com AWS APIs (Athena)

# 1. Configuração do Glue e Argumentos
# --------------------------------------------------------------------------------
# NOVO: Recebe argumentos do Job injetados pela Step Function
try:
    args = getResolvedOptions(sys.argv, ['JOB_NAME', 'trip_type_filter'])
except:
    # Caso de teste local ou manual, define um valor default (ex: 'yellow')
    print("AVISO: Argumento 'trip_type_filter' não encontrado. Usando default 'yellow' para teste.")
    args = {'trip_type_filter': 'yellow', 'JOB_NAME': 'local_test_job'}

TRIP_TYPE_FILTER = args['trip_type_filter']
S3_BUCKET_NAME = "nyc-taxi-data-lake-jha-case-ifood" # Esta variável deve ser injetada via argumentos em ambiente produtivo

# AJUSTADO: O caminho de leitura agora é específico, permitindo o Partition Pruning
LANDING_PATH   = f"s3a://{S3_BUCKET_NAME}/landing/trip_type={TRIP_TYPE_FILTER}/" 
CONSUMER_PATH  = f"s3a://{S3_BUCKET_NAME}/consumer/trips_delta/" 

# 2. Definição do Contexto Glue
# --------------------------------------------------------------------------------
sc = SparkContext.getOrCreate()
glueContext = GlueContext(sc)
spark = glueContext.spark_session 
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

# 3. Lógica de Função (Transformação e DQ)
# --------------------------------------------------------------------------------
def apply_data_quality_and_transform(df):
    """
    Aplica transformações e regras de Data Quality (DQ).
    Cria colunas unificadas (pickup/dropoff_datetime) para uso interno (DQ/Features), 
    mas as descarta no resultado final.
    """
    
    # 1. Unificação e Normalização de Colunas Essenciais
    # Estas colunas unificadas são criadas APENAS para uso em filtros (DQ) e extração de features.
    df_transformed = df \
        .withColumnRenamed("VendorID", "vendor_id") \
        .withColumn(
            "pickup_datetime_unified", 
            # Garante que a coluna de data seja preenchida, seja por tpep (Yellow) ou lpep (Green)
            F.coalesce(F.col("tpep_pickup_datetime"), F.col("lpep_pickup_datetime"))
        ) \
        .withColumn(
            "dropoff_datetime_unified", 
            F.coalesce(F.col("tpep_dropoff_datetime"), F.col("lpep_dropoff_datetime"))
        )

    # 2. Regras de Data Quality (DQ) - Utiliza as colunas unificadas
    df_dq = df_transformed.filter(
        # Passengeiros válidos
        F.col("passenger_count").isNotNull() & (F.col("passenger_count") > 0)
    ).filter(
        # Valor total não negativo
        F.col("total_amount").isNotNull() & (F.col("total_amount") >= 0)
    ).filter(
        # Datas unificadas preenchidas
        F.col("pickup_datetime_unified").isNotNull() & F.col("dropoff_datetime_unified").isNotNull()
    )

    # 3. Engenharia de Features (Criação de Partição para o Sink)
    # Usa a coluna unificada para criar as chaves de partição de destino
    df_final = df_dq.withColumn("trip_year", F.year(F.col("pickup_datetime_unified")))
    df_final = df_final.withColumn("trip_month", F.month(F.col("pickup_datetime_unified")))
    
    # 4. Seleção Final das Colunas para o Sink (Excluindo as colunas temporárias/redundantes)
    # Excluímos: pickup_datetime_unified, dropoff_datetime_unified e partition_date
    df_final_select = df_final.select(
        "vendor_id", 
        "passenger_count",
        "total_amount",
        # Datas Originais (mantidas no Delta Lake)
        F.col("tpep_pickup_datetime").alias("tpep_pickup_datetime"),
        F.col("tpep_dropoff_datetime").alias("tpep_dropoff_datetime"), 
        F.col("lpep_pickup_datetime").alias("lpep_pickup_datetime"), 
        F.col("lpep_dropoff_datetime").alias("lpep_dropoff_datetime"),
        # Colunas de Partição (trip_type, trip_year, trip_month)
        "trip_type",
        "trip_year", 
        "trip_month"
    )

    print(f"Número de registros após o DQ: {df_final_select.count()}")
    return df_final_select

# NOVO: Função para Sincronização
# --------------------------------------------------------------------------------
def sync_glue_partitions(database_name, table_name, output_s3):
    """
    Executa MSCK REPAIR TABLE via AWS Athena para sincronizar as partições
    do Delta Lake no Glue Catalog. Requer permissão de Athena e S3.
    """
    print(f"Sincronizando partições para {database_name}.{table_name} via Athena...")
    # Assume que a região e credenciais são herdadas do ambiente Glue
    athena_client = boto3.client('athena')
    query = f"MSCK REPAIR TABLE {table_name};"
    
    try:
        response = athena_client.start_query_execution(
            QueryString=query,
            QueryExecutionContext={
                'Database': database_name
            },
            ResultConfiguration={
                # O Athena precisa de um bucket para resultados de consulta
                'OutputLocation': output_s3 
            }
        )
        # Não precisa esperar a conclusão, apenas o início é suficiente
        print(f"MSCK REPAIR iniciado com sucesso. Query Execution ID: {response['QueryExecutionId']}")
    except Exception as e:
        print(f"AVISO: Falha ao iniciar MSCK REPAIR via Athena. As partições precisarão de sincronização manual ou via Step Function. Erro: {e}")
        # O job não falha, mas avisa sobre a falha de sincronização.

# 4. Orquestração e Execução
# --------------------------------------------------------------------------------
if __name__ == '__main__':
    
    # Configuração para garantir que o Spark tente inferir o tipo de dados correto
    spark.conf.set("spark.sql.sources.partitionColumnTypeInference.enabled", "true") 
    
    print(f"Processando dados para TRIP_TYPE: {TRIP_TYPE_FILTER}")
    print(f"Iniciando leitura da Landing Zone filtrada em: {LANDING_PATH}")
    
    # Uso do leitor nativo do Spark para forçar o Partition Pruning
    try:
        df_landing = spark.read.format("parquet") \
                         .option("mergeSchema", "true") \
                         .load(LANDING_PATH) # <-- Agora, este caminho é filtrado!
    except Exception as e:
        print(f"Falha ao ler dados da Landing Zone em {LANDING_PATH}: {e}")
        # Lança a exceção para que o Step Function falhe
        raise
        
    df_landing.printSchema() 
    
    # CORREÇÃO DO SCHEMA (Partition Date): Remove 'partition_date' para evitar problemas de schema 
    # (conforme relatado pelo usuário), já que não é usada na lógica de ETL.
    if 'partition_date' in df_landing.columns:
        df_landing = df_landing.drop('partition_date')
        print("Coluna 'partition_date' removida do DataFrame para evitar problemas de schema.")

    # CORREÇÃO CRÍTICA: Adiciona a coluna 'trip_type' que foi usada no filtro do caminho
    # mas que não é automaticamente incluída no schema do DataFrame lido.
    df_landing = df_landing.withColumn("trip_type", F.lit(TRIP_TYPE_FILTER))
    print(f"Coluna 'trip_type' adicionada com valor constante: {TRIP_TYPE_FILTER}")
    
    # NOVO PASSO DE CORREÇÃO DE SCHEMA: 
    # Adiciona colunas ausentes como NULL para garantir que a unificação na função de transformação funcione.
    print(f"Verificando e completando schema para trip_type: {TRIP_TYPE_FILTER}")
    
    if TRIP_TYPE_FILTER == 'yellow':
        # Dados Yellow não contêm as colunas lpep_*, então as adicionamos como NULL de tipo Timestamp
        if 'lpep_pickup_datetime' not in df_landing.columns:
            df_landing = df_landing.withColumn("lpep_pickup_datetime", F.lit(None).cast("timestamp"))
        if 'lpep_dropoff_datetime' not in df_landing.columns:
            df_landing = df_landing.withColumn("lpep_dropoff_datetime", F.lit(None).cast("timestamp"))
            
    elif TRIP_TYPE_FILTER == 'green':
        # Dados Green não contêm as colunas tpep_*, então as adicionamos como NULL de tipo Timestamp
        if 'tpep_pickup_datetime' not in df_landing.columns:
            df_landing = df_landing.withColumn("tpep_pickup_datetime", F.lit(None).cast("timestamp"))
        if 'tpep_dropoff_datetime' not in df_landing.columns:
            df_landing = df_landing.withColumn("tpep_dropoff_datetime", F.lit(None).cast("timestamp"))

    print(f"Registros lidos: {df_landing.count()}")

    # 5. Transformação e DQ
    df_consumer = apply_data_quality_and_transform(df_landing)

    # 6. Escrita em Delta Lake (Sink)
    print(f"Iniciando escrita da camada Consumer (Delta Lake) em: {CONSUMER_PATH}")

    # A escrita usará a estratégia de sobrescrita PARTÍCIONADA.
    # Como a leitura foi filtrada, apenas a partição de destino correspondente será afetada.
    df_consumer.write.mode("overwrite") \
             .format("delta") \
             .option("overwriteSchema", "true") \
             .partitionBy("trip_type", "trip_year", "trip_month") \
             .save(CONSUMER_PATH)

    print(f"Escrita em Delta Lake concluída para trip_type={TRIP_TYPE_FILTER}.")
    
    # 7. Sincronização de Partições (Boa Prática de Automação)
    # --------------------------------------------------------------------------------
    # Definir o local S3 para resultados de consulta do Athena (necessário para MSCK REPAIR)
    ATHENA_S3_STAGING_DIR = f"s3://{S3_BUCKET_NAME}/athena-query-results/" 
    
    # *ATENÇÃO: Mude 'nyc_taxi_db' e 'trips_consumer' para o nome real do seu database/tabela no Glue Catalog.*
    GLUE_DATABASE_NAME = "nyc_taxi_db" 
    GLUE_TABLE_NAME = "trips_consumer"
    
    sync_glue_partitions(GLUE_DATABASE_NAME, GLUE_TABLE_NAME, ATHENA_S3_STAGING_DIR)
    
    job.commit()
