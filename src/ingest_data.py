import os
import requests
import boto3
from datetime import datetime # 🚨 NOVO: Importa datetime

# --- Configurações Fixas (Não dependem do ambiente) ---
# Base da URL de distribuição via AWS CloudFront
BASE_CDN_URL = "https://d37ci6vzurychx.cloudfront.net/trip-data/"


def generate_url_and_key(trip_type, year, month, ingest_ts): # 🚨 ALTERADO: Recebe ingest_ts
    """Gera a URL completa de download e a chave S3 de destino."""
    
    # Formato de partição YYYYMM (ex: 202301)
    partition_date = f"{year}{month}"
    
    # Exemplo: yellow_tripdata_2023-01.parquet
    file_name = f"{trip_type}_tripdata_{year}-{month}.parquet"
    
    # URL completa para download
    download_url = f"{BASE_CDN_URL}{file_name}"
    
    # Chave S3 (Landing Zone/Original Data)
    # 🚨 NOVO FORMATO DE CHAVE: Inclui a partição ingest_ts para versionamento
    # Ex: /landing/yellow/partition_date=202301/ingest_ts=20251015143000/yellow_tripdata_2023-01.parquet
    s3_key = f"landing/{trip_type}/partition_date={partition_date}/ingest_ts={ingest_ts}/{file_name}"
    
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
    # Formato: YYYYMMDDHHMMSS
    INGEST_TIMESTAMP = datetime.now().strftime('%Y%m%d%H%M%S')
    print(f"Timestamp da Ingestão: {INGEST_TIMESTAMP}")
    

    # 2. Definir VARIÁVEIS DE EXECUÇÃO (com defaults)
    # Mantendo os defaults do desafio inicial (Jan-Mai 2023)
    YEAR = str(event.get("year", "2023")) 
    MONTHS = event.get("months", ["01", "02", "03", "04", "05"])
    TRIP_TYPES = event.get("trip_types", ["yellow", "green"])
    
    # 3. Inicialização e Execução
    s3_client = boto3.client('s3')
    
    print(f"--- Iniciando Ingestão de Dados (Ano: {YEAR}) via AWS Lambda ---")
    print(f"Meses a processar: {MONTHS}")
    print(f"Tipos de Táxi: {TRIP_TYPES}")
    print(f"Bucket de Destino: {S3_BUCKET_NAME}")

    total_files = len(TRIP_TYPES) * len(MONTHS)
    successful_uploads = 0
    processed_count = 0
    
    for trip_type in TRIP_TYPES:
        for month in MONTHS:
            processed_count += 1
            print(f"\n--- Processando {processed_count}/{total_files} - Tipo: {trip_type}, Mês: {month} ---")
            
            # 🚨 ALTERADO: Passa o timestamp para a função de geração de chave
            url, s3_key = generate_url_and_key(trip_type, YEAR, month, INGEST_TIMESTAMP)
            
            if download_and_upload(s3_client, url, S3_BUCKET_NAME, s3_key):
                successful_uploads += 1

    print(f"\n--- Ingestão Concluída! Total de arquivos carregados: {successful_uploads} ---")
    
    return {
        'statusCode': 200,
        'body': f'Ingestão concluída. {successful_uploads} de {total_files} arquivos carregados.',
        # É uma boa prática retornar o timestamp para o Step Functions monitorar
        'ingestion_timestamp': INGEST_TIMESTAMP 
    }
