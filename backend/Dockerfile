FROM python:3.12-slim
WORKDIR /app
COPY requirements.lock.txt .
RUN pip install --no-cache-dir -r requirements.lock.txt
COPY fyd ./fyd
RUN useradd --create-home fyd
USER fyd
EXPOSE 8000
CMD ["uvicorn","fyd.api:app","--host","0.0.0.0","--port","8000"]
