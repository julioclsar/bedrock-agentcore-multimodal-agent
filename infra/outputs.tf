output "aws_region" {
  description = "Região AWS usada para provisionar os recursos (útil para o login no ECR)."
  value       = var.aws_region
}

output "ecr_repository_url" {
  description = "URL do repositório ECR onde a imagem do agente deve ser publicada (docker build/push)."
  value       = aws_ecr_repository.agent.repository_url
}

output "agent_execution_role_arn" {
  description = "ARN da execution role usada pelo AgentCore Runtime."
  value       = aws_iam_role.agent_execution.arn
}

output "memory_id" {
  description = "ID do recurso de memória do AgentCore usado pelo agente."
  value       = aws_bedrockagentcore_memory.agent.id
}

output "agent_runtime_arn" {
  description = "ARN do AgentCore Runtime implantado — use como AGENT_RUNTIME_ARN nos clientes (client_invoke.py, streamlit_app.py)."
  value       = aws_bedrockagentcore_agent_runtime.agent.agent_runtime_arn
}
