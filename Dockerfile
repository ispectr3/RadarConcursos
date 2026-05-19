FROM python:3.11-slim

# Configurar timezone para o agendador funcionar corretamente
ENV TZ=America/Sao_Paulo
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /app

# Instalar dependências primeiro (aproveita o cache do Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar os arquivos do projeto
COPY . .

# Garantir que a pasta de dados exista
RUN mkdir -p data

# Rodar o bot
CMD ["python", "main.py"]
