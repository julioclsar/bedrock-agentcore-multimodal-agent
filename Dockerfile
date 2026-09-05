# Usa uma versão leve do Python como base
FROM public.ecr.aws/docker/library/python:3.11-slim

# Define a pasta de trabalho dentro da nuvem
WORKDIR /app

# Copia o arquivo de dependências primeiro
COPY requirements.txt .

# Instala as bibliotecas que você definiu
RUN pip install --no-cache-dir -r requirements.txt

# Copia o resto do seu código (app.py, etc)
COPY . .

# Comando padrão para manter o contêiner rodando
CMD ["python", "src/main.py"]