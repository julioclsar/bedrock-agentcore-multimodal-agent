import base64
import binascii
import os

import boto3
from bedrock_agentcore.memory.integrations.strands.config import (
    AgentCoreMemoryConfig,
    RetrievalConfig,
)
from bedrock_agentcore.memory.integrations.strands.session_manager import (
    AgentCoreMemorySessionManager,
)
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool

from mcp_client.client import get_streamable_http_mcp_client
from model.load import load_model, load_model_id

app = BedrockAgentCoreApp()
log = app.logger

AWS_REGION = os.environ.get("AWS_REGION", "us-west-2")
MEMORY_ID = os.environ.get("BEDROCK_AGENTCORE_MEMORY_ID", "deltaGray_Agent_mem-U4sB1T6tTR")
MODEL_ID = load_model_id()

bedrock_runtime = boto3.client("bedrock-runtime", region_name=AWS_REGION)
mcp_client = get_streamable_http_mcp_client()


@tool
def add_numbers(a: int, b: int) -> int:
    """Return the sum of two numbers."""
    return a + b


def _normalize_image_format(image_format: str) -> str:
    if not image_format:
        return "png"

    image_format = image_format.lower().strip()
    if image_format == "jpg":
        return "jpeg"
    return image_format


def _build_converse_messages(prompt: str, image_bytes: bytes, image_format: str):
    return [
        {
            "role": "user",
            "content": [
                {"text": prompt},
                {
                    "image": {
                        "format": image_format,
                        "source": {"bytes": image_bytes},
                    }
                },
            ],
        }
    ]


def _extract_text_from_converse_response(response: dict) -> str:
    parts = response.get("output", {}).get("message", {}).get("content", [])
    texts = []

    for item in parts:
        if isinstance(item, dict) and "text" in item:
            texts.append(item["text"])

    return "\n".join(texts).strip()


def _invoke_multimodal_model(prompt: str, image_b64: str, image_format: str) -> dict:
    try:
        image_bytes = base64.b64decode(image_b64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("image_base64 invalido ou corrompido.") from exc

    normalized_format = _normalize_image_format(image_format)

    response = bedrock_runtime.converse(
        modelId=MODEL_ID,
        messages=_build_converse_messages(prompt, image_bytes, normalized_format),
        inferenceConfig={
            "maxTokens": 700,
            "temperature": 0.2,
            "topP": 0.9,
        },
    )

    text = _extract_text_from_converse_response(response)
    return {
        "model_id": MODEL_ID,
        "analysis": text,
        "stop_reason": response.get("stopReason"),
        "usage": response.get("usage", {}),
    }


def _build_session_manager(session_id: str, user_id: str):
    if not MEMORY_ID:
        log.warning(
            "BEDROCK_AGENTCORE_MEMORY_ID is not set. Memory will be disabled."
        )
        return None

    return AgentCoreMemorySessionManager(
        AgentCoreMemoryConfig(
            memory_id=MEMORY_ID,
            session_id=session_id,
            actor_id=user_id,
            retrieval_config={
                f"/facts/{user_id}/": RetrievalConfig(top_k=10, relevance_score=0.4),
                f"/preferences/{user_id}/": RetrievalConfig(
                    top_k=5, relevance_score=0.5
                ),
                f"/summaries/{user_id}/{session_id}/": RetrievalConfig(
                    top_k=5, relevance_score=0.4
                ),
                f"/episodes/{user_id}/{session_id}/": RetrievalConfig(
                    top_k=5, relevance_score=0.4
                ),
            },
        ),
        AWS_REGION,
    )

def _get_mcp_tools():
    try:
        with mcp_client as client:
            return client.list_tools_sync()
    except Exception as exc:
        log.warning("MCP tools unavailable: %s", exc)
        return []


def _build_agent(session_manager, session_id: str):
    tools = [add_numbers]
    tools.extend(_get_mcp_tools())

    return Agent(
        model=load_model(),
        session_manager=session_manager,
        system_prompt=(
            "You are a helpful multimodal assistant. "
            "Use the provided analysis as factual grounding when available. "
            "Answer in Brazilian Portuguese unless the user explicitly asks otherwise. "
            "Use tools when they add value."
        ),
        tools=tools,
    )


async def _collect_agent_text(agent: Agent, prompt: str) -> str:
    chunks = []
    stream = agent.stream_async(prompt)

    async for event in stream:
        if "data" in event and isinstance(event["data"], str):
            chunks.append(event["data"])

    return "".join(chunks).strip()


def _build_orchestration_prompt(user_prompt: str) -> str:
    return (
        "Voce e um agente multimodal. "
        "Analise a imagem enviada e responda em portugues do Brasil. "
        "Se houver texto visivel, inclua-o. "
        "Se houver objetos, descreva-os. "
        f"Instrucao do usuario: {user_prompt}"
    )


def _build_refinement_prompt(user_prompt: str, raw_analysis: str) -> str:
    return (
        "O usuario enviou uma imagem para analise.\n"
        f"Pedido original do usuario: {user_prompt}\n\n"
        "Resultado bruto da analise multimodal:\n"
        f"{raw_analysis}\n\n"
        "Com base no contexto recuperado da memoria da sessao e nas preferencias do usuario, "
        "gere a resposta final em portugues do Brasil. "
        "Nao invente detalhes que nao estejam no resultado bruto. "
        "Se houver alguma incerteza, deixe isso explicito."
    )


@app.entrypoint
async def invoke(payload, context=None):
    try:
        if not isinstance(payload, dict):
            return {
                "ok": False,
                "error": "Payload invalido. O payload deve ser um JSON/objeto.",
            }

        prompt = payload.get(
            "prompt",
            "Analise a imagem e descreva seu conteudo visual de forma objetiva.",
        )
        image_b64 = payload.get("image_base64")
        image_format = payload.get("image_format", "png")
        user_id = payload.get("user_id") or "default-user"
        session_id = getattr(context, "session_id", None) or payload.get(
            "session_id", "default"
        )

        session_manager = _build_session_manager(session_id, user_id)
        agent = _build_agent(session_manager, session_id)

        if image_b64:
            multimodal_result = _invoke_multimodal_model(
                prompt=_build_orchestration_prompt(prompt),
                image_b64=image_b64,
                image_format=image_format,
            )

            final_response = await _collect_agent_text(
                agent,
                _build_refinement_prompt(prompt, multimodal_result["analysis"]),
            )

            return {
                "ok": True,
                "agent_framework": "Strands Agents",
                "runtime": "Amazon Bedrock AgentCore Runtime",
                "memory_enabled": bool(session_manager),
                "session_id": session_id,
                "user_id": user_id,
                "result": {
                    "model_id": multimodal_result["model_id"],
                    "analysis": multimodal_result["analysis"],
                    "final_response": final_response or multimodal_result["analysis"],
                    "stop_reason": multimodal_result["stop_reason"],
                    "usage": multimodal_result["usage"],
                },
            }

        final_response = await _collect_agent_text(agent, prompt)

        return {
            "ok": True,
            "agent_framework": "Strands Agents",
            "runtime": "Amazon Bedrock AgentCore Runtime",
            "memory_enabled": bool(session_manager),
            "session_id": session_id,
            "user_id": user_id,
            "result": {
                "final_response": final_response,
            },
        }

    except Exception as exc:
        log.exception("Invocation failed")
        return {
            "ok": False,
            "error": str(exc),
        }


if __name__ == "__main__":
    app.run()
