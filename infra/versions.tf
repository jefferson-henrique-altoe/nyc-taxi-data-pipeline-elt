terraform {
  # Versão mínima requerida do Terraform
  required_version = ">= 1.0.0"

  # Configuração dos provedores necessários (apenas AWS neste caso)
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  
  # A seção backend foi INTENCIONALMENTE REMOVIDA para usar o backend LOCAL.
  # O arquivo 'terraform.tfstate' será gerado na pasta 'infra/' após 'terraform init'.
}

# Define o provider e a região onde os recursos serão criados
provider "aws" {
  region = "us-east-2" # Escolha sua região de preferência (ex: us-east-1 ou sa-east-1)
}
