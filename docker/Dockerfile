# Basisimage Python 3.12
FROM python:3.12-slim@sha256:d75c4b6cdd039ae966a34cd3ccab9e0e5f7299280ad76fe1744882d86eedce0b

# Install curl
RUN apt-get update && apt-get install -y curl

WORKDIR /src

# Python Packages installieren
COPY ../requirements.txt /src/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# App in image kopieren
COPY ../src/app /src/app

# Port für FastAPI
EXPOSE 8000

# Start der API über uvicorn
CMD ["uvicorn", "app.api_client:app", "--host", "0.0.0.0", "--port", "8000"]
