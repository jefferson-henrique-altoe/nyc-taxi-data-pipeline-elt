# Este arquivo anexa as políticas necessárias à Role de Execução do Step Function (SFN).
# Estas permissões são CRÍTICAS para permitir que o SFN orquestre o Glue Jobs de forma síncrona (.sync).

# Assumimos que a role 'aws_iam_role.sfn_execution_role' já está definida em outro arquivo.

# 1. Permissões para orquestrar o Glue Jobs (CORREÇÃO)
# AWSGlueConsoleFullAccess contém as permissões 'glue:*' necessárias para o .sync
resource "aws_iam_role_policy_attachment" "sfn_glue_full_access" {
  # O nome da role deve ser o mesmo do seu recurso aws_iam_role.sfn_execution_role
  role       = aws_iam_role.sfn_execution_role.name 
  # Esta política substitui a incorreta AWSGlueServiceRole
  policy_arn = "arn:aws:iam::aws:policy/AWSGlueConsoleFullAccess"
}

# 2. Permissões para invocar a Lambda Function
# Necessário para o primeiro passo (InvokeIngestionLambda).
resource "aws_iam_role_policy_attachment" "sfn_lambda_exec" {
  role       = aws_iam_role.sfn_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/AWSLambda_FullAccess"
}

# 3. Permissões de Logs e Logs de Serviço (Prática recomendada)
# Permite que o Step Function envie logs para o CloudWatch.
resource "aws_iam_role_policy_attachment" "sfn_logs" {
  role       = aws_iam_role.sfn_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess"
}
