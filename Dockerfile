# Usar una imagen oficial de Python ligera como base
FROM python:3.10-slim

# Evitar que Python escriba archivos .pyc en el disco y activar logs des-abanderados (unbuffered)
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Establecer nuestro directorio de trabajo en la imagen
WORKDIR /app

# Copiar el archivo de requerimientos e instalarlos
COPY requirements.txt .

# Instalar dependencias (no cache para mantener imagen ligera)
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el grueso de la aplicación al contenedor
COPY . .

# Cloud Run escucha en el puerto 8080 por defecto. 
EXPOSE 8080

# Comando para ejecutar el app de FastAPI, ligándolo al puerto $PORT proveído por GCP
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
