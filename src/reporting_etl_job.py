# from pyspark.context import SparkContext
# from awsglue.context import GlueContext
# from awsglue.job import Job
# import pyspark.sql.functions as F
# from awsglue.utils import getResolvedOptions
# import sys
# try:
#     from awsglue.utils import getResolvedOptions
# except ImportError:
#     pass

# # 1. Definição do Contexto Glue e Argumentos
# sc = SparkContext.getOrCreate()
# glueContext = GlueContext(sc)
# spark = glueContext.spark_session
# job = Job(glueContext)

# # Pega os argumentos passados pelo Step Functions/Glue Job
# try:
#     # Tenta obter argumentos do Step Function
#     args = getResolvedOptions(sys.argv, ['JOB_NAME', 'datalake_bucket'])
#     S3_BUCKET_NAME = args['datalake_bucket']
# except Exception as e:
#     # Fallback para o caso de teste local ou erro (usar valor padrão)
#     print(f"ATENÇÃO: Não foi possível obter o argumento 'datalake_bucket'. Erro: {e}. Usando fallback...")
#     # ATENÇÃO: Substituir pelo nome real do bucket se testado localmente.
#     S3_BUCKET_NAME = "nyc-taxi-data-lake-jha-case-ifood"
    
# # --- Variáveis de Caminho ---
# # Assumimos que o Glue Job anterior salvou os dados limpos neste caminho
# CONSUMER_PATH  = f"s3a://{S3_BUCKET_NAME}/consumer/trips_delta/" 
# REPORTING_PATH = f"s3a://{S3_BUCKET_NAME}/analytics/reporting/" 

# # 2. Leitura da Tabela Delta (Camada Consumer)
# print(f"Iniciando leitura da tabela Delta em: {CONSUMER_PATH}")

# # Leitura com suporte Delta Lake (configurado via default_arguments no Terraform)
# df_trips = spark.read.format("delta").load(CONSUMER_PATH)

# # --- 3. Função de Análise e Reporting ---

# def run_analytics_reporting(df):
#     """
#     Executa as consultas de negócio (Q1 e Q2) e salva os resultados no S3 
#     (Camada Reporting), garantindo que as tabelas sejam acessíveis via Athena.
#     """
    
#     # Adicionando colunas de data/hora essenciais para agregação
#     # Usando os nomes de coluna padronizados ('pickup_datetime')
#     df_with_dates = df.withColumn("trip_year", F.year(F.col("pickup_datetime"))) \
#                       .withColumn("trip_month", F.month(F.col("pickup_datetime"))) \
#                       .withColumn("pickup_hour", F.hour(F.col("pickup_datetime")))
    
#     # ----------------------------------------------------------------------
#     # PERGUNTA 1: Média de valor total (total_amount) por mês
#     # ----------------------------------------------------------------------
    
#     print("\n--- Processando Q1: Média de Valor Total por Mês ---")
    
#     # Cria a chave de agrupamento Ano-Mês formatada (ex: 2023-01)
#     df_q1 = df_with_dates.withColumn(
#         "report_month", F.concat(F.col("trip_year"), F.lit("-"), F.format_string("%02d", F.col("trip_month")))
#     )

#     # Calcula a média mensal
#     df_result_q1 = df_q1.groupBy("report_month").agg(
#         F.avg("total_amount").alias("avg_total_amount")
#     ).orderBy("report_month")

#     # Salva o resultado no S3 Reporting (Pasta Q1)
#     output_path_q1 = f"{REPORTING_PATH}q1_monthly_revenue/"
#     print(f"Salvando resultados da Q1 em: {output_path_q1}")
#     df_result_q1.write.mode("overwrite").parquet(output_path_q1)


#     # ----------------------------------------------------------------------
#     # PERGUNTA 2: Média de passageiros por cada hora do dia, por tipo de viagem
#     # ----------------------------------------------------------------------
    
#     print("\n--- Processando Q2: Média de Passageiros por Hora e Tipo de Viagem ---")
    
#     # Agrupamento pela hora e cálculo da média de passageiros (incluindo o tipo de viagem)
#     df_result_q2 = df_with_dates.groupBy("pickup_hour", "trip_type").agg(
#         F.avg("passenger_count").alias("avg_passenger_count")
#     ).withColumnRenamed("pickup_hour", "report_hour") # Renomeia para o catálogo
    
#     # Salva o resultado no S3 Reporting (Pasta Q2)
#     output_path_q2 = f"{REPORTING_PATH}q2_hourly_passengers/"
#     print(f"Salvando resultados da Q2 em: {output_path_q2}")
#     df_result_q2.write.mode("overwrite").parquet(output_path_q2)

#     print("\n--- Relatórios Q1 e Q2 criados na Camada Reporting. ---")
#     return True

# # 4. Orquestração e Execução
# if __name__ == '__main__':
    
#     df_trips_count = df_trips.count()
#     print(f"Registros lidos da Camada Consumer (Delta Lake): {df_trips_count}")

#     if df_trips_count == 0:
#         # 🚨 Ponto de Falha de Diagnóstico: Se 0, o job anterior falhou ao gravar.
#         print("WARNING: O DataFrame de entrada da Camada Consumer está vazio. Job finalizado sem gerar relatórios.")
#         job.commit()
#         # Garante que o Glue Job termine como SUCESSO, já que não havia dados para processar
#         sys.exit(0) 

#     # Se houver dados, executa a análise
#     run_analytics_reporting(df_trips)
#     job.commit()

# Importações necessárias
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
import pyspark.sql.functions as F
from awsglue.utils import getResolvedOptions
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
    S3_BUCKET_NAME = "nyc-taxi-data-lake-jha-case-ifood"
    
# Caminhos das Duas Tabelas Delta na Camada Consumer
YELLOW_PATH = f"s3a://{S3_BUCKET_NAME}/consumer/trips_delta/yellow/"
GREEN_PATH = f"s3a://{S3_BUCKET_NAME}/consumer/trips_delta/green/"

# Caminhos de Escrita para a Camada Reporting (definidos nos arquivos reporting_tables.tf)
REPORTING_Q1_PATH = f"s3a://{S3_BUCKET_NAME}/analytics/reporting/q1_avg_total_amount_monthly/"
REPORTING_Q2_PATH = f"s3a://{S3_BUCKET_NAME}/analytics/reporting/q2_avg_passengers_hourly_may/"


def read_delta_table(s3_path):
    """Tenta ler uma tabela Delta Lake. Retorna um DataFrame vazio se o caminho for inválido ou o DF estiver vazio."""
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
        print(f"ERRO ao ler {s3_path}. O caminho ou a tabela podem não existir: {e}")
        return None

def analyze_q1(df_yellow):
    """
    Relatório Q1: Qual a média de valor total (total_amount) recebido em um mês 
    considerando todos os yellow táxis da frota?
    """
    if df_yellow is None:
        return None
        
    print("-" * 50)
    print("Iniciando Análise Q1 (Yellow Taxis)")
    print("-" * 50)

    # 1. Agregação: Agrupa por ano/mês e calcula a média do total_amount
    df_q1 = df_yellow.groupBy(F.col("trip_year"), F.col("trip_month")) \
                     .agg(F.avg("total_amount").alias("avg_total_amount"))
    
    # 2. Formatação: Cria a coluna report_month no formato YYYY-MM
    df_q1 = df_q1.withColumn("report_month", 
                             F.concat_ws("-", F.col("trip_year"), F.lpad(F.col("trip_month"), 2, "0"))) \
                 .select("report_month", "avg_total_amount")
    
    # 3. Escrita: Salva o resultado no Reporting Layer
    print(f"Escrevendo Q1 em: {REPORTING_Q1_PATH}")
    df_q1.write.mode("overwrite").parquet(REPORTING_Q1_PATH)
    
    df_q1.show()
    return df_q1

def analyze_q2(df_yellow, df_green):
    """
    Relatório Q2: Qual a média de passageiros (passenger_count) por cada hora do dia
    que pegaram táxi no mês de maio considerando todos os táxis da frota?
    """
    # Verifica se há dados disponíveis para a união
    if df_yellow is None and df_green is None:
        return None
        
    print("-" * 50)
    print("Iniciando Análise Q2 (Todos os Taxis)")
    print("-" * 50)

    # 1. União: Consolida os dados Yellow e Green (se houver)
    if df_yellow is None:
        df_all = df_green
    elif df_green is None:
        df_all = df_yellow
    else:
        df_all = df_yellow.unionByName(df_green)
        
    # 2. Filtragem e Feature Engineering: Filtra por Maio (Mês 5) e extrai a hora
    # O campo 'trip_month' é um inteiro (1 a 12)
    df_q2 = df_all.filter(F.col("trip_month") == 5) 
    
    # Ponto de checagem para garantir que há dados em Maio
    if df_q2.count() == 0:
        print("AVISO: Nenhum dado de Maio (Mês 5) encontrado após a união. Relatório Q2 será vazio.")
        # Cria um DF vazio com o schema correto
        empty_schema = ["report_hour", "avg_passenger_count", "trip_type"]
        empty_df = spark.createDataFrame([], empty_schema)
        empty_df.write.mode("overwrite").parquet(REPORTING_Q2_PATH)
        return empty_df

    df_q2 = df_q2.withColumn("report_hour", F.hour(F.col("pickup_datetime")))

    # 3. Agregação: Agrupa por hora e tipo de táxi (para visualização)
    df_q2 = df_q2.groupBy(F.col("report_hour"), F.col("trip_type")) \
                 .agg(F.avg("passenger_count").alias("avg_passenger_count")) \
                 .select("report_hour", "avg_passenger_count", "trip_type")
    
    # 4. Escrita: Salva o resultado no Reporting Layer
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
