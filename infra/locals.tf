locals {
  account_id = data.aws_caller_identity.current.account_id

  # Escopo dos recursos que o AgentCore pode assumir/gerenciar nesta conta/região.
  agentcore_arn_like = "arn:aws:bedrock-agentcore:${var.aws_region}:${local.account_id}:*"

  common_tags = {
    Project   = var.project_name
    ManagedBy = "terraform"
  }
}
