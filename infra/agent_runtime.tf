# O AgentCore Runtime só pode ser criado depois que a imagem já existe no ECR
# (ver README, seção "Provisionando com Terraform" — é um apply em duas etapas).
resource "aws_bedrockagentcore_agent_runtime" "agent" {
  agent_runtime_name = "${var.project_name}_Agent"
  role_arn           = aws_iam_role.agent_execution.arn
  description        = "Agente multimodal ${var.project_name} (Strands Agents + Amazon Bedrock AgentCore Runtime)"

  agent_runtime_artifact {
    container_configuration {
      container_uri = "${aws_ecr_repository.agent.repository_url}:${var.image_tag}"
    }
  }

  network_configuration {
    network_mode = var.network_mode
  }

  environment_variables = {
    AWS_REGION                  = var.aws_region
    MODEL_ID                    = var.model_id
    BEDROCK_AGENTCORE_MEMORY_ID = aws_bedrockagentcore_memory.agent.id
  }

  tags = local.common_tags

  depends_on = [aws_iam_role_policy.agent_execution]
}
