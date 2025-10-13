import os
import requests
import boto3
from datetime import datetime
from urllib.parse import urlparse
import sys
try:
    from awsglue.utils import getResolvedOptions
except ImportError:
    pass

# --- Configurações Fixas (Não dependem do ambiente) ---
# Base da URL de distribuição via AWS CloudFront
BASE_CDN_URL = "https://d37ci6vzurychx.cloudfront.net/trip-data/"


def generate_url_and_key(trip_type, year, month):
    """Gera a URL completa de download e a chave S3 de destino."""

    # CRÍTICO: Garante que o mês tenha sempre 2 dígitos (ex: "01", "05")
    month_padded = month.zfill(2) 

    # Formato de partição YYYYMM (ex: 202301)
    partition_date = f"{year}{month_padded}"

    # Exemplo: yellow_tripdata_2023-01.parquet. Agora usa month_padded para consistência.
    file_name = f"{trip_type}_tripdata_{year}-{month_padded}.parquet"

    # URL completa para download
    download_url = f"{BASE_CDN_URL}{file_name}"

    # Chave S3 (Landing Zone/Original Data)
    # Ex: /landing/trip_type=yellow/partition_date=202301/yellow_tripdata_2023-01.parquet
    # Usa month_padded na parte final para corresponder ao filename
    s3_key = f"landing/trip_type={trip_type}/partition_date={partition_date}/{trip_type}_tripdata_{year}-{month_padded}.parquet"

    return download_url, s3_key


def download_and_upload(s3_client, url, bucket, key):
    """Baixa um arquivo via HTTP e faz o upload direto para o S3."""
    
    print(f"-> Iniciando download: {url}")
    
    try:
        # 1. Requisição HTTP em modo stream
        response = requests.get(url, stream=True)
        response.raise_for_status()

        # 2. Upload para o S3 usando o objeto de stream
        s3_client.upload_fileobj(
            Fileobj=response.raw,
            Bucket=bucket,
            Key=key
        )
        
        print(f"   [SUCESSO] Upload concluído para s3://{bucket}/{key}")
        return True
        
    except requests.exceptions.HTTPError as e:
        print(f"   [ERRO] Falha ao baixar {url}: Status {e.response.status_code}. Pulando.")
    except Exception as e:
        print(f"   [ERRO] Ocorreu um erro no upload de {key}: {e}")
        
    return False


def handler(event, context):
    """
    Função principal executada pelo AWS Lambda.
    Recebe configurações de execução via payload (event).
    """
    
    # 1. Obter Nome do Bucket (Variável de Ambiente, configurada via Terraform)
    S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME")
    if not S3_BUCKET_NAME:
        print("ERRO: Variável de ambiente S3_BUCKET_NAME não configurada.")
        return {'statusCode': 500, 'body': 'Configuration Error'}
        
    # 🚨 NOVO: Gera um timestamp único para esta execução. 
    INGEST_TIMESTAMP = datetime.now().strftime('%Y%m%d%H%M%S')
    print(f"Timestamp da Ingestão: {INGEST_TIMESTAMP}")
    

    # 2. Definir VARIÁVEIS DE EXECUÇÃO (com defaults)
    YEAR = str(event.get("year", "2023")) 
    # Garante que os meses de input também tenham zero-padding
    input_months = event.get("months", ["01", "02", "03", "04", "05"])
    MONTHS = [str(m).zfill(2) for m in input_months] 
    TRIP_TYPES = event.get("trip_types", ["yellow", "green"])
    
    # 3. Inicialização e Execução
    s3_client = boto3.client('s3')
    
    print(f"--- Iniciando Ingestão de Dados (Ano: {YEAR}) via AWS Lambda ---")

    total_files = len(TRIP_TYPES) * len(MONTHS)
    successful_uploads = 0
    processed_count = 0
    
    for trip_type in TRIP_TYPES:
        for month in MONTHS:
            processed_count += 1
            
            # A chamada à função generate_url_and_key já garante o zero-padding
            url, s3_key = generate_url_and_key(trip_type, YEAR, month)
            
            if download_and_upload(s3_client, url, S3_BUCKET_NAME, s3_key):
                successful_uploads += 1

    print(f"\n--- Ingestão Concluída! Total de arquivos carregados: {successful_uploads} ---")
    
    return {
        'statusCode': 200,
        'body': f'Ingestão concluída. {successful_uploads} de {total_files} arquivos carregados.',
        # Retornamos o timestamp para o Step Functions usar (opcional)
        'ingestion_timestamp': INGEST_TIMESTAMP 
    }
