#!/bin/bash

# 🚀 Script de démarrage rapide Telia Backend
# Usage: chmod +x start.sh && ./start.sh

echo "=========================================="
echo "🚀 Telia Backend - Démarrage"
echo "=========================================="
echo ""

# Vérifier si Python est installé
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 n'est pas installé!"
    exit 1
fi

echo "✅ Python détecté: $(python3 --version)"
echo ""

# Créer un environnement virtuel si nécessaire
if [ ! -d "venv" ]; then
    echo "📦 Création de l'environnement virtuel..."
    python3 -m venv venv
    echo "✅ Environnement virtuel créé"
else
    echo "✅ Environnement virtuel existant trouvé"
fi
echo ""

# Activer l'environnement virtuel
echo "🔧 Activation de l'environnement virtuel..."
source venv/bin/activate 2>/dev/null || source venv/Scripts/activate 2>/dev/null
echo ""

# Installer les dépendances
echo "📥 Installation des dépendances..."
pip install -q -r requirements.txt
echo "✅ Dépendances installées"
echo ""

# Créer le fichier .env si nécessaire
if [ ! -f ".env" ]; then
    echo "⚙️  Création du fichier .env..."
    cp .env.example .env
    echo "✅ Fichier .env créé (pensez à changer le SECRET_KEY en production!)"
else
    echo "✅ Fichier .env existant"
fi
echo ""

# Créer la base de données
echo "🗄️  Initialisation de la base de données..."
python3 -c "from app.database import Base, engine; Base.metadata.create_all(bind=engine); print('✅ Base de données initialisée')"
echo ""

# Proposer de créer un superadmin
echo "=========================================="
echo "👤 Création d'un compte superadmin"
echo "=========================================="
read -p "Voulez-vous créer un compte superadmin maintenant? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    python3 create_superadmin.py
fi
echo ""

# Démarrer le serveur
echo "=========================================="
echo "🌐 Démarrage du serveur"
echo "=========================================="
echo ""
echo "📍 API: http://localhost:8000"
echo "📖 Docs: http://localhost:8000/docs"
echo "📚 ReDoc: http://localhost:8000/redoc"
echo ""
echo "Appuyez sur Ctrl+C pour arrêter le serveur"
echo ""

# Lancer le serveur avec uvicorn
uvicorn main:app --reload --host 0.0.0.0 --port 8000
