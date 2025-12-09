# Basisimage Python 3.12
FROM python:3.12-slim

WORKDIR /src

# Python Packages installieren
COPY ../requirements.txt /src/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# App kopieren
COPY ../src/app /src/app

# Port für FastAPI
EXPOSE 8000

# Start von API
CMD ["uvicorn", "app.api_server:app", "--host", "0.0.0.0", "--port", "8000"]
