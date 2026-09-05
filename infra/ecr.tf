# O nome com o prefixo "bedrock-agentcore-" segue a convenção usada pelas
# policies gerenciadas do AgentCore Runtime (ver iam.tf), permitindo aplicar
# permissões de ECR com escopo restrito em vez de "Resource": "*".
resource "aws_ecr_repository" "agent" {
  name                 = "bedrock-agentcore-${lower(var.project_name)}"
  image_tag_mutability = "MUTABLE"

  # Facilita o "terraform destroy" ao final do desafio, mesmo com imagens publicadas.
  force_delete = true

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = local.common_tags
}
