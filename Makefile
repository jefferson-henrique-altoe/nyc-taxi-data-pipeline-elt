# Nome do diretório onde está a infraestrutura do Terraform
INFRA_DIR = infra

# Nome da pasta de deployment da Lambda
LAMBDA_DEPLOY_DIR = lambda_deployment_package

# Regra principal: executa o processo completo de preparação e deployment
deploy: prepare_lambda_package terraform_apply

# ----------------------------------------------------
# 1. PREPARAÇÃO
# ----------------------------------------------------

prepare_lambda_package:
	@echo "--- 1. Preparando o pacote Lambda ---"
	mkdir -p $(LAMBDA_DEPLOY_DIR)
	pip install --target $(LAMBDA_DEPLOY_DIR) -r requirements.txt
	cp src/ingest_data.py $(LAMBDA_DEPLOY_DIR)/
	@echo "--- Pacote Lambda pronto em $(LAMBDA_DEPLOY_DIR) ---"

# ----------------------------------------------------
# 2. TERRAFORM (Aplica e Destrói)
# ----------------------------------------------------

terraform_apply:
	@echo "--- 2. Executando Terraform Apply ---"
	cd $(INFRA_DIR) && terraform apply -auto-approve

# Destrói toda a infraestrutura gerenciada pelo Terraform
destroy:
	@echo "--- 3. EXECUTANDO TERRAFORM DESTROY ---"
	cd $(INFRA_DIR) && terraform destroy -auto-approve
	rm -rf $(LAMBDA_DEPLOY_DIR)

# ----------------------------------------------------
# 4. UTILITY (Limpeza Local)
# ----------------------------------------------------

clean:
	@echo "--- 4. Limpando arquivos temporários locais ---"
	rm -rf $(LAMBDA_DEPLOY_DIR)
	rm -rf $(INFRA_DIR)/tmp
	rm -rf $(INFRA_DIR)/.terraform
	rm -f $(INFRA_DIR)/terraform.tfstate
	@echo "--- Limpeza concluída. ---"
