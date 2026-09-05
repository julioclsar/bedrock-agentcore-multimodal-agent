# Memória de curto/longo prazo da sessão do agente (fatos, preferências,
# resumos e episódios), consumida por AgentCoreMemorySessionManager em
# src/main.py.
resource "aws_bedrockagentcore_memory" "agent" {
  name                  = "${var.project_name}_Agent_mem"
  description           = "Memória de sessão do agente multimodal ${var.project_name}"
  event_expiry_duration = var.memory_event_expiry_days

  tags = local.common_tags
}
