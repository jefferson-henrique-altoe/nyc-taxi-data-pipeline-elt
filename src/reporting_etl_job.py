# Importações necessárias
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
import pyspark.sql.functions as F
from awsglue.utils import getResolvedOptions
# Importações de Tipos para definir schemas explicitamente
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, IntegerType
import sys

# 1. Configuração do Glue e Argumentos
sc = SparkContext.getOrCreate()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)

# --- Variáveis de Caminho ---
try:
    # O argumento 'datalake_bucket' é necessário para construir os caminhos S3
    args = getResolvedOptions(sys.argv, ['JOB_NAME', 'datalake_bucket'])
    S3_BUCKET_NAME = args['datalake_bucket']
except Exception:
    # Fallback para ambiente de desenvolvimento/teste local
    S3_BUCKET_NAME = "nyc-taxi-data-lake-jha-case-ifood"
    
# Caminhos das Duas Tabelas Delta na Camada Consumer
YELLOW_PATH = f"s3a://{S3_BUCKET_NAME}/consumer/trips_delta/trip_type=yellow/"
GREEN_PATH = f"s3a://{S3_BUCKET_NAME}/consumer/trips_delta/trip_type=green/"

# Caminhos de Escrita para a Camada Reporting (definidos nos arquivos reporting_tables.tf)
REPORTING_Q1_PATH = f"s3a://{S3_BUCKET_NAME}/analytics/reporting/q1_avg_total_amount_monthly/"
REPORTING_Q2_PATH = f"s3a://{S3_BUCKET_NAME}/analytics/reporting/q2_avg_passengers_hourly_may/"


# Schemas de saída explícitos para DataFrames vazios (resolve o ValueError: can not infer schema)
Q1_SCHEMA = StructType([
    StructField("report_month", StringType(), True),
    StructField("avg_total_amount", DoubleType(), True)
])

Q2_SCHEMA = StructType([
    # CORRIGIDO: Deve ser IntegerType para compatibilidade com o Glue Catalog/Athena
    StructField("report_hour", IntegerType(), True), 
    StructField("avg_passenger_count", DoubleType(), True),
    StructField("trip_type", StringType(), True)
])


def read_delta_table(s3_path):
    """Tenta ler uma tabela Delta Lake. Retorna None se o caminho for inválido ou o DF estiver vazio."""
    print(f"Tentando ler Delta Table em: {s3_path}")
    try:
        # Tenta ler o Delta
        df = spark.read.format("delta").load(s3_path)
        count = df.count()
        if count == 0:
            print(f"AVISO: DataFrame lido de {s3_path} está vazio.")
            return None
        print(f"Sucesso: {count} registros lidos de {s3_path}.")
        return df
    except Exception as e:
        # Nota: Retorna None em caso de falha de leitura (e.g., caminho inexistente)
        print(f"ERRO ao ler {s3_path}. O caminho ou a tabela podem não existir: {e}")
        return None

def write_empty_report(s3_path, schema):
    """Cria e escreve um DataFrame vazio com o schema fornecido."""
    print(f"Escrevendo esquema vazio em: {s3_path}")
    empty_df = spark.createDataFrame([], schema)
    # Garante que o arquivo de metadados Parquet seja criado
    empty_df.write.mode("overwrite").parquet(s3_path)


def analyze_q1(df_yellow):
    """
    Relatório Q1: Média de valor total (total_amount) por mês para yellow táxis.
    """
    if df_yellow is None:
        write_empty_report(REPORTING_Q1_PATH, Q1_SCHEMA)
        return None
        
    print("-" * 50)
    print("Iniciando Análise Q1 (Yellow Taxis)")
    print("-" * 50)

    # 1. Agregação
    df_q1 = df_yellow.groupBy(F.col("trip_year"), F.col("trip_month")) \
                      .agg(F.avg("total_amount").alias("avg_total_amount"))
    
    # 2. Formatação
    df_q1 = df_q1.withColumn("report_month", 
                              F.concat_ws("-", F.col("trip_year"), F.lpad(F.col("trip_month"), 2, "0"))) \
                  .select("report_month", F.round(F.col("avg_total_amount"), 2).alias("avg_total_amount"))

    # VERIFICAÇÃO DE VAZIO PÓS-AGREGAÇÃO
    if df_q1.count() == 0:
        print("AVISO: DataFrame Q1 está vazio após agregação. Escrevendo esquema Q1 vazio.")
        write_empty_report(REPORTING_Q1_PATH, Q1_SCHEMA)
        return None

    # 3. Escrita
    print(f"Escrevendo Q1 ({df_q1.count()} registros) em: {REPORTING_Q1_PATH}")
    df_q1.write.mode("overwrite").parquet(REPORTING_Q1_PATH)
    
    df_q1.show()
    return df_q1


def analyze_q2(df_yellow, df_green):
    """
    Relatório Q2: Média de passageiros por hora do dia, filtrado por Maio.
    """
    # 1. Checagem inicial de dados
    if df_yellow is None and df_green is None:
        print("AVISO: Dados Yellow e Green (Q2) indisponíveis. Escrevendo esquema Q2 vazio.")
        write_empty_report(REPORTING_Q2_PATH, Q2_SCHEMA)
        return None
        
    print("-" * 50)
    print("Iniciando Análise Q2 (Todos os Taxis)")
    print("-" * 50)

    # 2. União: Consolida os dados Yellow e Green
    if df_yellow is None:
        df_all = df_green
    elif df_green is None:
        df_all = df_yellow
    else:
        df_all = df_yellow.unionByName(df_green, allowMissingColumns=True)
        
    # 3. Filtragem e Feature Engineering: Filtra por Maio (Mês 5) e extrai a hora
    df_q2 = df_all.filter(F.col("trip_month") == 5)  # Filtra por Maio
    
    # Checagem se há dados em Maio
    if df_q2.count() == 0:
        print("AVISO: Nenhum dado de Maio (Mês 5) encontrado após a união ou filtro. Relatório Q2 será vazio.")
        write_empty_report(REPORTING_Q2_PATH, Q2_SCHEMA)
        return None

    # CORREÇÃO CRÍTICA: Extrai a hora como INTEGER (0-23), garantindo que o tipo Parquet seja INT
    df_q2 = df_q2.withColumn("report_hour", F.hour(F.col("pickup_datetime")))

    # 4. Agregação
    df_q2 = df_q2.groupBy(F.col("report_hour"), F.col("trip_type")) \
                  .agg(F.avg("passenger_count").alias("avg_passenger_count")) \
                  .select("report_hour", F.round(F.col("avg_passenger_count"), 2).alias("avg_passenger_count"), "trip_type")
    
    # 5. Escrita
    print(f"Escrevendo Q2 em: {REPORTING_Q2_PATH}")
    df_q2.write.mode("overwrite").parquet(REPORTING_Q2_PATH)
    
    df_q2.show()
    return df_q2

# 2. Orquestração e Execução
if __name__ == '__main__':
    
    # Lendo os DataFrames da Camada Consumer
    df_yellow = read_delta_table(YELLOW_PATH)
    df_green = read_delta_table(GREEN_PATH)
    
    # Executa a análise Q1 (apenas Yellow)
    analyze_q1(df_yellow)
    
    # Executa a análise Q2 (Yellow + Green)
    analyze_q2(df_yellow, df_green)
    
    job.commit()
