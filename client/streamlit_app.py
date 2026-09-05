import os
import json
import uuid
import base64
import boto3
import streamlit as st

# -------------------------
# Configurações
# -------------------------
AWS_REGION = os.environ.get("AWS_REGION", "us-west-2")
AGENT_RUNTIME_ARN = os.environ.get("AGENT_RUNTIME_ARN", "arn:aws:bedrock-agentcore:us-west-2:651644924182:runtime/deltaGray_Agent-iwoGq59I2r")

client = boto3.client("bedrock-agentcore", region_name=AWS_REGION)

st.set_page_config(page_title="Chat multimodal com AgentCore", page_icon="🧠")
st.title("Chat multimodal com AgentCore Runtime")

# -------------------------
# Memória local da interface
# -------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

if "runtime_session_id" not in st.session_state:
    st.session_state.runtime_session_id = str(uuid.uuid4())

# -------------------------
# Sidebar
# -------------------------
with st.sidebar:
    st.subheader("Configuração")
    st.write(f"**Região:** {AWS_REGION}")
    st.write(f"**Session ID:** `{st.session_state.runtime_session_id}`")

    if st.button("Nova conversa"):
        st.session_state.messages = []
        st.session_state.runtime_session_id = str(uuid.uuid4())
        st.rerun()

# -------------------------
# Exibir histórico
# -------------------------
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("image_name"):
            st.caption(f"Imagem enviada: {msg['image_name']}")

# -------------------------
# Upload de imagem
# -------------------------
uploaded_file = st.file_uploader(
    "Anexe uma imagem (opcional)",
    type=["png", "jpg", "jpeg", "webp"]
)

# -------------------------
# Entrada do usuário
# -------------------------
prompt = st.chat_input("Digite sua mensagem...")

def infer_image_format(filename: str) -> str:
    name = filename.lower()
    if name.endswith(".jpg") or name.endswith(".jpeg"):
        return "jpeg"
    if name.endswith(".webp"):
        return "webp"
    return "png"

def file_to_base64(uploaded) -> str:
    return base64.b64encode(uploaded.getvalue()).decode("utf-8")

def invoke_agent(prompt_text: str, uploaded):
    payload = {
        "prompt": prompt_text
    }

    if uploaded is not None:
        payload["image_base64"] = file_to_base64(uploaded)
        payload["image_format"] = infer_image_format(uploaded.name)

    response = client.invoke_agent_runtime(
        agentRuntimeArn=AGENT_RUNTIME_ARN,
        runtimeSessionId=st.session_state.runtime_session_id,
        payload=json.dumps(payload).encode("utf-8"),
        qualifier="DEFAULT"
    )

    chunks = []
    for chunk in response.get("response", []):
        if isinstance(chunk, (bytes, bytearray)):
            chunks.append(chunk.decode("utf-8"))
        else:
            chunks.append(str(chunk))

    joined = "".join(chunks)

    try:
        return json.loads(joined)
    except json.JSONDecodeError:
        return {"raw_response": joined}


def extract_display_payload(result: dict) -> dict:
    if result.get("ok") is not True:
        return {
            "answer": result.get("error", "Erro desconhecido."),
            "analysis": None,
            "metadata": {},
        }

    payload = result.get("result", {})
    final_response = payload.get("final_response")
    analysis = payload.get("analysis")

    # In the multimodal flow, analysis is the raw visual grounding and
    # final_response is the user-facing answer refined with memory/tools.
    answer = final_response or analysis or "Sem resposta."

    metadata = {
        "session_id": result.get("session_id"),
        "memory_enabled": result.get("memory_enabled"),
        "model_id": payload.get("model_id"),
        "stop_reason": payload.get("stop_reason"),
    }

    return {
        "answer": answer,
        "analysis": analysis if analysis and analysis != answer else None,
        "metadata": metadata,
    }

# -------------------------
# Envio
# -------------------------
if prompt:
    user_msg = {
        "role": "user",
        "content": prompt,
        "image_name": uploaded_file.name if uploaded_file else None
    }
    st.session_state.messages.append(user_msg)

    with st.chat_message("user"):
        st.markdown(prompt)
        if uploaded_file:
            st.caption(f"Imagem enviada: {uploaded_file.name}")

    with st.chat_message("assistant"):
        with st.spinner("Consultando o agente..."):
            try:
                result = invoke_agent(prompt, uploaded_file)
                display = extract_display_payload(result)
                answer = display["answer"]

                st.markdown(answer)

                if display["analysis"]:
                    with st.expander("Analise bruta da imagem"):
                        st.write(display["analysis"])

                metadata = display["metadata"]
                if metadata.get("model_id") or metadata.get("memory_enabled") is not None:
                    details = []
                    if metadata.get("model_id"):
                        details.append(f"Modelo: `{metadata['model_id']}`")
                    if metadata.get("memory_enabled") is not None:
                        details.append(
                            "Memoria: `ativada`"
                            if metadata["memory_enabled"]
                            else "Memoria: `desativada`"
                        )
                    if metadata.get("session_id"):
                        details.append(f"Session ID: `{metadata['session_id']}`")
                    if metadata.get("stop_reason"):
                        details.append(f"Stop reason: `{metadata['stop_reason']}`")
                    st.caption(" | ".join(details))

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer
                })

            except Exception as e:
                error_msg = f"Erro ao invocar o AgentCore: {e}"
                st.error(error_msg)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": error_msg
                })
