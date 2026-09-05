variable "aws_region" {
  description = "Região AWS onde os recursos serão provisionados."
  type        = string
  default     = "us-west-2"
}

variable "project_name" {
  description = "Nome base usado para nomear os recursos (ECR, IAM, AgentCore Runtime, Memory). Sem espaços ou hífens no meio, por causa das regras de nomenclatura do AgentCore Runtime."
  type        = string
  default     = "deltaGray"
}

variable "image_tag" {
  description = "Tag da imagem publicada no ECR que o AgentCore Runtime deve executar."
  type        = string
  default     = "latest"
}

variable "model_id" {
  description = "ID do modelo Bedrock usado pelo agente Strands e pela análise multimodal (Converse API)."
  type        = string
  default     = "us.amazon.nova-pro-v1:0"
}

variable "memory_event_expiry_days" {
  description = "Dias até os eventos armazenados na memória do agente expirarem (entre 7 e 365)."
  type        = number
  default     = 30
}

variable "network_mode" {
  description = "Modo de rede do AgentCore Runtime: PUBLIC (sem VPC) ou VPC."
  type        = string
  default     = "PUBLIC"
}
