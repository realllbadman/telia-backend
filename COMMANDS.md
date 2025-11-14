# 📋 Commandes Utiles - Telia Backend

## 🚀 Démarrage rapide

### Option 1: Script automatique (Recommandé)
```bash
chmod +x start.sh
./start.sh
```

### Option 2: Manuel
```bash
# Installer les dépendances
pip install -r requirements.txt

# Démarrer le serveur
uvicorn main:app --reload
```

## 🔧 Configuration

### Créer le fichier .env
```bash
cp .env.example .env
# Ensuite éditez .env et changez le SECRET_KEY
```

### Générer une clé secrète sécurisée
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## 👤 Gestion des utilisateurs

### Créer un superadmin
```bash
python create_superadmin.py
```

### Tester l'API
```bash
python test_api.py
```

## 📦 Gestion des dépendances

### Installer les dépendances de production
```bash
pip install -r requirements.txt
```

### Installer les dépendances de développement
```bash
pip install -r requirements-dev.txt
```

### Mettre à jour les dépendances
```bash
pip install --upgrade -r requirements.txt
```

## 🗄️ Base de données

### Créer/initialiser la base de données
```bash
python -c "from app.database import Base, engine; Base.metadata.create_all(bind=engine)"
```

### Supprimer et recréer la base de données
```bash
rm telia.db
python -c "from app.database import Base, engine; Base.metadata.create_all(bind=engine)"
```

### Migration vers PostgreSQL
```bash
# Installer le driver
pip install psycopg2-binary

# Modifier .env
DATABASE_URL=postgresql://user:password@localhost/telia

# Démarrer normalement
uvicorn main:app --reload
```

## 🧪 Tests et développement

### Lancer le serveur en mode développement
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Lancer le serveur sur un port différent
```bash
uvicorn main:app --reload --port 8001
```

### Tester avec curl

#### Inscription
```bash
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "username": "testuser",
    "password": "testpass123",
    "role": "customer"
  }'
```

#### Connexion
```bash
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "testpass123"
  }'
```

#### Accès route protégée
```bash
# Remplacez TOKEN par votre token JWT
curl -X GET "http://localhost:8000/auth/me" \
  -H "Authorization: Bearer TOKEN"
```

## 📊 Debugging et logs

### Voir les logs du serveur
Le serveur affiche automatiquement les logs dans la console.

### Mode debug détaillé
```bash
uvicorn main:app --reload --log-level debug
```

### Tester l'importation des modules
```bash
python -c "from app.database import Base, engine; print('✅ Modules OK')"
python -c "from app.auth.utils import create_access_token; print('✅ Auth OK')"
python -c "from main import app; print('✅ App OK')"
```

## 🔒 Sécurité

### Vérifier les dépendances de sécurité
```bash
pip install safety
safety check
```

### Scanner les vulnérabilités
```bash
pip install bandit
bandit -r app/
```

## 📝 Code quality

### Formatter le code (Black)
```bash
pip install black
black app/ main.py
```

### Linter (flake8)
```bash
pip install flake8
flake8 app/ main.py --max-line-length=100
```

### Type checking (mypy)
```bash
pip install mypy
mypy app/ main.py
```

## 🐳 Docker (optionnel)

### Créer un Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Build et run
```bash
docker build -t telia-backend .
docker run -p 8000:8000 telia-backend
```

## 📦 Environnement virtuel

### Créer un environnement virtuel
```bash
python -m venv venv
```

### Activer l'environnement virtuel

#### Linux/Mac
```bash
source venv/bin/activate
```

#### Windows
```bash
venv\Scripts\activate
```

### Désactiver l'environnement virtuel
```bash
deactivate
```

## 🔄 Workflows courants

### Développement d'une nouvelle feature
```bash
# 1. Activer l'environnement
source venv/bin/activate

# 2. Créer une branche
git checkout -b feature/ma-nouvelle-feature

# 3. Coder et tester
uvicorn main:app --reload

# 4. Formater le code
black app/ main.py

# 5. Commit
git add .
git commit -m "feat: ajout de ma nouvelle feature"
```

### Mise en production
```bash
# 1. Configurer l'environnement de production
cp .env.example .env.production
# Éditer .env.production avec les vraies valeurs

# 2. Utiliser Gunicorn (production)
pip install gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app

# 3. Ou avec uvicorn en production
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

## 📖 Documentation

### Accéder à la documentation interactive
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Générer la documentation OpenAPI
```bash
curl http://localhost:8000/openapi.json > openapi.json
```

## 🆘 Troubleshooting

### Port déjà utilisé
```bash
# Trouver le processus
lsof -i :8000  # Mac/Linux
netstat -ano | findstr :8000  # Windows

# Tuer le processus
kill -9 PID  # Mac/Linux
taskkill /PID PID /F  # Windows

# Ou utiliser un autre port
uvicorn main:app --reload --port 8001
```

### Module non trouvé
```bash
# Réinstaller les dépendances
pip install --force-reinstall -r requirements.txt
```

### Base de données verrouillée
```bash
# Fermer tous les processus puis
rm telia.db
python -c "from app.database import Base, engine; Base.metadata.create_all(bind=engine)"
```

## 📚 Liens utiles

- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **SQLAlchemy Docs**: https://docs.sqlalchemy.org/
- **Pydantic Docs**: https://docs.pydantic.dev/
- **JWT.io**: https://jwt.io/
- **Python Docs**: https://docs.python.org/3/

## 💡 Astuces

### Recharger automatiquement lors des changements
```bash
# Déjà activé avec --reload
uvicorn main:app --reload
```

### Voir les requêtes SQL
```python
# Dans app/database.py, ajouter echo=True
engine = create_engine(
    settings.DATABASE_URL,
    echo=True  # Active les logs SQL
)
```

### Déboguer avec ipdb
```bash
pip install ipdb

# Dans votre code
import ipdb; ipdb.set_trace()
```

### Variables d'environnement temporaires
```bash
# Linux/Mac
SECRET_KEY=my-temp-key uvicorn main:app --reload

# Windows
set SECRET_KEY=my-temp-key && uvicorn main:app --reload
```
