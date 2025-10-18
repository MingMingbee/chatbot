FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PORT=8080
EXPOSE 8080
CMD ["bash", "-c", "streamlit run app${BOT_TYPE:-1}.py --server.address=0.0.0.0 --server.port ${PORT}"]
