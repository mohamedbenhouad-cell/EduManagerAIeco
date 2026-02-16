# 1. On utilise une version légère de Python
FROM python:3.9-slim

# 2. On évite les fichiers temporaires Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 3. On crée le dossier de l'application
WORKDIR /app

# 4. On copie les fichiers nécessaires et on installe les librairies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. On copie tout le reste du code (y compris .streamlit/secrets.toml)
COPY . .

# 6. On ouvre le port 8080 (Standard Google Cloud)
EXPOSE 8080

# 7. La commande de démarrage
CMD streamlit run app.py --server.port=8080 --server.address=0.0.0.0