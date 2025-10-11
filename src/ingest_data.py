import requests
import boto3

# --- Configurações ---
# O NOME DO SEU BUCKET S3. MUDAR para o nome real!
S3_BUCKET_NAME = "nyc-taxi-data-lake-jha-case-ifood"

# Base da URL de distribuição via AWS CloudFront
BASE_CDN_URL = "https://d37ci6vzurychx.cloudfront.net/trip-data/"

# Meses e Ano de interesse (Janeiro a Maio de 2023)
YEAR = "2023"
MONTHS = ["01", "02", "03", "04", "05"]

# Tipos de táxi (Yellow e Green)
TRIP_TYPES = ["yellow", "green"] 

# Inicializa o cliente S3
s3_client = boto3.client('s3')

def generate_url_and_key(trip_type, year, month):
    """Gera a URL completa de download e a chave S3 de destino."""
    
    # Exemplo: yellow_tripdata_2023-01.parquet
    file_name = f"{trip_type}_tripdata_{year}-{month}.parquet"
    
    # URL completa para download
    download_url = f"{BASE_CDN_URL}{file_name}"
    
    # Chave S3 (Landing Zone/Original Data)
    s3_key = f"landing/{trip_type}/{file_name}"
    
    return download_url, s3_key

def download_and_upload(url, bucket, key):
    """Baixa um arquivo via HTTP e faz o upload direto para o S3."""
    
    print(f"-> Iniciando download: {url}")
    
    # 1. Requisição HTTP em modo stream (evita carregar arquivos grandes na memória)
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()  # Levanta erro para status 4xx/5xx

        # 2. Upload para o S3 usando o objeto de stream (raw) da resposta
        # O S3 transferirá o arquivo em partes, de forma otimizada.
        s3_client.upload_fileobj(
            Fileobj=response.raw,
            Bucket=bucket,
            Key=key
        )
        
        print(f"   [SUCESSO] Upload concluído para s3://{bucket}/{key}")
        
    except requests.exceptions.HTTPError as e:
        print(f"   [ERRO] Falha ao baixar {url}: Status {e.response.status_code}. Pulando.")
    except Exception as e:
        print(f"   [ERRO] Ocorreu um erro no upload de {key}: {e}")

def main():
    print(f"--- Iniciando Ingestão de Dados (2023) ---")
    print(f"Bucket de Destino: {S3_BUCKET_NAME}")
    
    if S3_BUCKET_NAME == "nyc-taxi-data-lake-desafio-seu-nome-unico":
         print("\n*** ERRO: Por favor, altere a variável S3_BUCKET_NAME no código! ***\n")
         return

    total_files = len(TRIP_TYPES) * len(MONTHS)
    processed_count = 0
    
    for trip_type in TRIP_TYPES:
        for month in MONTHS:
            processed_count += 1
            print(f"\n--- Processando {processed_count}/{total_files} - Tipo: {trip_type}, Mês: {month} ---")
            
            url, s3_key = generate_url_and_key(trip_type, YEAR, month)
            download_and_upload(url, S3_BUCKET_NAME, s3_key)

    print("\n--- Ingestão Concluída! ---")

if __name__ == "__main__":
    main()
