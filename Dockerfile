FROM python:3.11-slim

# Configurar timezone
ENV TZ=America/Sao_Paulo
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

WORKDIR /app

# Instalar dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar projeto
COPY . .

# Garantir pasta de dados
RUN mkdir -p data && chmod +x start.sh

# Fly.io health check na porta do dashboard
EXPOSE 8765

CMD ["./start.sh"]
