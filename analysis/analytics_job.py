# Script de Análise Simples (Roda localmente após o pipeline Glue)
# Este script assume que o AWS CLI e o PyAthena estão instalados e configurados.

import pandas as pd
from pyathena import connect
from pyathena.pandas.cursor import PandasCursor
import os

# --- Configurações de Conexão ---
# Verifique se estas variáveis estão corretas para o seu ambiente AWS
AWS_REGION = "us-east-2" 
# Configure um S3 bucket para o Athena salvar resultados de consultas temporárias
S3_BUCKET_NAME = "nyc-taxi-data-lake-jha-case-ifood"
ATHENA_S3_STAGING_DIR = f"s3://{S3_BUCKET_NAME}/athena-query-results/"

DATABASE_NAME = "nyc_taxi_db"

def run_analysis():
    try:
        # Conexão ao Athena
        conn = connect(
            s3_staging_dir=ATHENA_S3_STAGING_DIR,
            region_name=AWS_REGION,
            cursor_class=PandasCursor
        )
        print(f"Conexão ao Athena estabelecida na região: {AWS_REGION}. Database: {DATABASE_NAME}")

        # --- Consulta Q1: Média Mensal de Receita ---
        QUERY_Q1 = f"""
        SELECT 
            report_month, 
            avg_total_amount 
        FROM 
            "{DATABASE_NAME}"."q1_monthly_revenue"
        ORDER BY 
            report_month
        """
        df_q1 = pd.read_sql(QUERY_Q1, conn)
        print("\n--- Relatório Q1: Média Mensal de Receita ---")
        print(df_q1)

        # --- Consulta Q2: Média Horária de Passageiros ---
        QUERY_Q2 = f"""
        SELECT 
            report_hour, 
            trip_type,
            avg_passenger_count 
        FROM 
            "{DATABASE_NAME}"."q2_hourly_passengers"
        ORDER BY 
            report_hour, trip_type
        """
        df_q2 = pd.read_sql(QUERY_Q2, conn)
        print("\n--- Relatório Q2: Média Horária de Passageiros ---")
        print(df_q2)

    except Exception as e:
        print(f"\nERRO: Não foi possível executar a análise no Athena. Verifique o S3 Staging Path e as credenciais AWS.")
        print(f"Detalhes do erro: {e}")

if __name__ == '__main__':
    run_analysis()
