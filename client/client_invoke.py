import base64
import json
import os
import uuid

import boto3


AWS_REGION = os.environ.get("AWS_REGION", "us-west-2")
AGENT_RUNTIME_ARN = os.environ.get(
    "AGENT_RUNTIME_ARN",
    "arn:aws:bedrock-agentcore:us-west-2:651644924182:runtime/deltaGray_Agent-iwoGq59I2r",
)
IMAGE_PATH = os.environ.get("IMAGE_PATH", "imagem.png")
PROMPT = os.environ.get("PROMPT", "Descreva a imagem enviada em portugues do Brasil.")


def encode_image_to_base64(path: str) -> str:
    with open(path, "rb") as file:
        return base64.b64encode(file.read()).decode("utf-8")


def infer_image_format(path: str) -> str:
    lowered = path.lower()
    if lowered.endswith(".jpg") or lowered.endswith(".jpeg"):
        return "jpeg"
    if lowered.endswith(".webp"):
        return "webp"
    return "png"


def format_agent_output(result: dict) -> str:
    if result.get("ok") is not True:
        return result.get("error", "Erro desconhecido.")

    payload = result.get("result", {})
    final_response = payload.get("final_response")
    analysis = payload.get("analysis")

    parts = [final_response or analysis or "Sem resposta."]

    if analysis and analysis != final_response:
        parts.append("\n[Analise bruta da imagem]\n" + analysis)

    metadata = []
    if payload.get("model_id"):
        metadata.append(f"modelo={payload['model_id']}")
    if result.get("memory_enabled") is not None:
        metadata.append(
            "memoria=ativada" if result["memory_enabled"] else "memoria=desativada"
        )
    if result.get("session_id"):
        metadata.append(f"session_id={result['session_id']}")

    if metadata:
        parts.append("\n[Metadados]\n" + "\n".join(metadata))

    return "\n".join(parts)


def main():
    payload_dict = {
        "prompt": PROMPT,
    }

    if IMAGE_PATH and os.path.exists(IMAGE_PATH):
        payload_dict["image_base64"] = encode_image_to_base64(IMAGE_PATH)
        payload_dict["image_format"] = infer_image_format(IMAGE_PATH)

    client = boto3.client("bedrock-agentcore", region_name=AWS_REGION)

    response = client.invoke_agent_runtime(
        agentRuntimeArn=AGENT_RUNTIME_ARN,
        runtimeSessionId=str(uuid.uuid4()),
        payload=json.dumps(payload_dict).encode("utf-8"),
        qualifier="DEFAULT",
    )

    chunks = []
    for chunk in response.get("response", []):
        if isinstance(chunk, (bytes, bytearray)):
            chunks.append(chunk.decode("utf-8"))
        else:
            chunks.append(str(chunk))

    joined = "".join(chunks)

    try:
        parsed = json.loads(joined)
        print(format_agent_output(parsed))
    except json.JSONDecodeError:
        print(joined)


if __name__ == "__main__":
    main()
