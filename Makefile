# ==============================================================================
# Variáveis de Configuração
# ==============================================================================

# O diretório onde está o arquivo main.tf do Terraform.
INFRA_DIR = infra

# O diretório que o Terraform zipará para o Lambda.
LAMBDA_DEPLOY_DIR = lambda_deployment_package

# O arquivo de dependências da Lambda (assumimos que está na raiz do projeto).
REQUIREMENTS_FILE = requirements.txt

# ==============================================================================
# Regras Principais
# ==============================================================================

.PHONY: deploy destroy clean prepare_lambda_package terraform_apply terraform_init

# ----------------------------------------------------
# Ação Principal: Prepara o pacote e executa o deployment
# Uso: make deploy
deploy: prepare_lambda_package terraform_init terraform_apply

# ----------------------------------------------------
# 1. PREPARAÇÃO DO PACOTE LAMBDA
# ----------------------------------------------------

prepare_lambda_package:
	@echo "--- 1. Preparando o pacote Lambda em $(LAMBDA_DEPLOY_DIR) ---"
	# 1. Garante que a pasta de deployment exista
	mkdir -p $(LAMBDA_DEPLOY_DIR)
	# 2. Instala as dependências (Usando pip3 para maior compatibilidade)
	pip3 install --target $(LAMBDA_DEPLOY_DIR) -r $(REQUIREMENTS_FILE)
	# 3. Copia o código principal (handler) para dentro do pacote
	cp src/ingest_data.py $(LAMBDA_DEPLOY_DIR)/
	@echo "--- ✅ Pacote Lambda pronto. ---"

# ----------------------------------------------------
# 2. TERRAFORM (Aplica a Infraestrutura)
# ----------------------------------------------------

terraform_init:
	@echo "--- 2. Inicializando Terraform na pasta $(INFRA_DIR) ---"
	cd $(INFRA_DIR) && terraform init

terraform_apply:
	@echo "--- 3. Executando Terraform Apply ---"
	cd $(INFRA_DIR) && terraform apply -auto-approve

# ----------------------------------------------------
# 3. DESTRUIR INFRAESTRUTURA
# ----------------------------------------------------

# Uso: make destroy
destroy:
	@echo "--- ⚠️ EXECUTANDO TERRAFORM DESTROY ---"
	cd $(INFRA_DIR) && terraform destroy -auto-approve
	rm -rf $(LAMBDA_DEPLOY_DIR)

# ----------------------------------------------------
# 4. UTILITY (Limpeza Local)
# ----------------------------------------------------

# Uso: make clean
clean:
	@echo "--- 🗑️ Limpando arquivos temporários locais ---"
	# Remove o pacote Lambda gerado
	rm -rf $(LAMBDA_DEPLOY_DIR)
	# Remove os arquivos internos do Terraform (cache e estado local)
	rm -rf $(INFRA_DIR)/.terraform
	rm -f $(INFRA_DIR)/terraform.tfstate
	rm -f $(INFRA_DIR)/terraform.tfstate.backup
	@echo "--- ✅ Limpeza concluída. ---"
