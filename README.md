# Agente Multimodal com Amazon Bedrock AgentCore

Agente de IA generativa capaz de interpretar imagens e texto, construído com [Strands Agents](https://strandsagents.com/) e implantado na nuvem através do **Amazon Bedrock AgentCore Runtime**.

O agente recebe um prompt em texto e, opcionalmente, uma imagem em base64. Quando uma imagem é enviada, o agente:

1. Analisa a imagem com um modelo multimodal da Amazon Bedrock (Nova Pro).
2. Usa o resultado dessa análise como contexto factual.
3. Refina a resposta final com um agente Strands, que também tem acesso a memória de sessão e a ferramentas externas via MCP.

Toda a resposta é gerada em português do Brasil.

## Arquitetura

```
src/
├── main.py            # Entrypoint do agente (BedrockAgentCoreApp) e orquestração do fluxo multimodal
├── model/
│   └── load.py        # Carrega o modelo de linguagem usado pelo agente Strands
└── mcp_client/
    └── client.py       # Cliente MCP (Model Context Protocol) usado como fonte de ferramentas externas

client/
├── client_invoke.py       # Script de linha de comando para invocar o agente já implantado (via boto3)
├── streamlit_app.py       # Interface de chat multimodal em Streamlit para testar o agente
├── sample_payload.json    # Exemplo de payload aceito pelo agente
└── IAMBedrockAgentCoreAccess.json  # Policy IAM mínima necessária para invocar o agente

infra/
├── ecr.tf              # Repositório ECR onde a imagem do agente é publicada
├── iam.tf              # Execution role e policy do AgentCore Runtime (permissões mínimas)
├── memory.tf           # Recurso de memória do AgentCore usado pelo agente
├── agent_runtime.tf    # O próprio AgentCore Runtime (aponta para a imagem no ECR)
├── variables.tf / outputs.tf / providers.tf / versions.tf / locals.tf
└── terraform.tfvars.example

test/
└── test_main.py        # Testes do entrypoint do agente
```

### Fluxo de uma requisição com imagem

1. O cliente envia `{"prompt": "...", "image_base64": "...", "image_format": "png"}` para o runtime.
2. `src/main.py` decodifica a imagem e chama o modelo multimodal (`bedrock-runtime.converse`) para obter uma análise visual bruta.
3. Essa análise é usada como contexto em um novo prompt, processado por um agente Strands com memória de sessão (Bedrock AgentCore Memory) e ferramentas (MCP + ferramentas locais).
4. O agente devolve a resposta final, já refinada, junto com metadados (modelo usado, `session_id`, se a memória está ativa, etc).

Se nenhuma imagem for enviada, o fluxo pula direto para o agente Strands com o prompt de texto.

## Pré-requisitos

- Python 3.10+
- Conta AWS com acesso ao Amazon Bedrock e ao Bedrock AgentCore, na região `us-west-2` (ou a região configurada)
- [AgentCore CLI](https://strandsagents.com/latest/documentation/docs/user-guide/deploy/deploy_to_bedrock_agentcore/python/) instalado (`pip install bedrock-agentcore-starter-toolkit`)
- Credenciais AWS configuradas (`aws configure` ou variáveis de ambiente)

## Rodando localmente

```bash
python -m venv .venv
source .venv/bin/activate  # No Windows: .venv\Scripts\activate
pip install -r requirements.txt

agentcore dev
```

Isso sobe o agente localmente em `0.0.0.0:8080`. Em outro terminal, é possível invocá-lo diretamente:

```bash
agentcore invoke --dev "O que você pode fazer?"
```

## Deploy no Amazon Bedrock AgentCore

Existem duas formas de provisionar a infraestrutura na AWS. As duas terminam no mesmo lugar: um AgentCore Runtime rodando a imagem do agente, com uma execution role e um recurso de memória associados.

### Opção A: AgentCore CLI (rápido, provisionamento automático)

```bash
agentcore configure   # opcional, para customizar o projeto
agentcore deploy
```

O `agentcore` cria automaticamente o repositório ECR, a execution role e o próprio runtime, e retorna o ARN do runtime, que deve ser usado pelos clientes (variável `AGENT_RUNTIME_ARN`).

Use `agentcore invoke` para testar rapidamente:

```bash
agentcore invoke '{"prompt": "Olá, quem é você?"}'
```

### Opção B: Terraform (infraestrutura como código)

A pasta `infra/` contém a definição completa da infraestrutura em Terraform: repositório ECR, execution role do AgentCore Runtime (com permissões mínimas — sem `"Resource": "*"` além do estritamente exigido pela própria AWS), o recurso de memória e o AgentCore Runtime.

Como o AgentCore Runtime referencia uma imagem que precisa existir no ECR, o processo é feito em duas etapas: primeiro cria-se o repositório, depois a imagem é publicada, e só então o runtime é criado.

**Pré-requisitos adicionais**: [Terraform](https://developer.hashicorp.com/terraform/downloads) >= 1.5, [Docker](https://docs.docker.com/get-docker/) com suporte a `buildx` (o AgentCore Runtime exige imagens `linux/arm64`).

```bash
cd infra
terraform init

# 1) Cria só o repositório ECR
terraform apply -target=aws_ecr_repository.agent

# 2) Publica a imagem do agente no ECR (arquitetura ARM64, exigida pelo AgentCore Runtime)
REPO_URL=$(terraform output -raw ecr_repository_url)
AWS_REGION=$(terraform output -raw aws_region)
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "${REPO_URL%%/*}"

cd ..
docker buildx build --platform linux/arm64 -t "$REPO_URL:latest" --push .
cd infra

# 3) Cria a execution role, a memória e o AgentCore Runtime apontando para a imagem publicada
terraform apply
```

Ao final, os outputs trazem tudo o que os clientes precisam:

```bash
terraform output agent_runtime_arn
terraform output memory_id
```

Use o valor de `agent_runtime_arn` como `AGENT_RUNTIME_ARN` na seção [Testando o agente implantado](#testando-o-agente-implantado).

Se preferir customizar região, nome do projeto ou tag da imagem, copie `terraform.tfvars.example` para `terraform.tfvars` e ajuste os valores antes do `terraform apply`.

## Variáveis de ambiente

| Variável | Descrição | Padrão |
|---|---|---|
| `AWS_REGION` | Região AWS usada pelo runtime e pelos clientes | `us-west-2` |
| `AGENT_RUNTIME_ARN` | ARN do agente implantado no Bedrock AgentCore (usado pelos clientes) | — |
| `MODEL_ID` | Modelo usado pelo agente Strands | `us.amazon.nova-pro-v1:0` |
| `BEDROCK_AGENTCORE_MEMORY_ID` | ID do recurso de memória do AgentCore (se vazio, a memória de sessão fica desativada) | — |

## Testando o agente implantado

Depois do deploy, use os clientes em `client/` para testar o agente:

### Via script (linha de comando)

```bash
cd client
AGENT_RUNTIME_ARN="<arn-do-seu-agente>" \
IMAGE_PATH="imagem.png" \
python client_invoke.py
```

### Via interface de chat (Streamlit)

```bash
cd client
AGENT_RUNTIME_ARN="<arn-do-seu-agente>" streamlit run streamlit_app.py
```

A interface permite conversar com o agente e anexar imagens (`png`, `jpg`, `jpeg`, `webp`) diretamente pelo navegador.

### Permissões necessárias

O papel/usuário usado para invocar o agente precisa, no mínimo, das permissões descritas em `client/IAMBedrockAgentCoreAccess.json` (`bedrock:InvokeModel`, `bedrock:InvokeModelWithResponseStream` e `bedrock-agentcore:InvokeAgentRuntime`).

## Testes

```bash
pytest test/
```

## Desprovisionamento

Após concluir os testes, é importante remover os recursos criados na AWS para evitar custos indesejados.

- **Se o deploy foi feito com a Opção A (AgentCore CLI)**: use `agentcore destroy`, quando disponível, ou remova manualmente pelo console/CLI o runtime, a memória, o repositório ECR e a execution role criados.
- **Se o deploy foi feito com a Opção B (Terraform)**:

  ```bash
  cd infra
  terraform destroy
  ```

  Isso remove o AgentCore Runtime, a memória, a execution role e o repositório ECR (com suas imagens, já que ele foi criado com `force_delete = true`).
