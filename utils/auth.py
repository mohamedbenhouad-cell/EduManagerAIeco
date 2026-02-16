# Fichier: utils/auth.py
import firebase_admin
from firebase_admin import credentials, auth
import requests
import random
import string
from pathlib import Path
import streamlit as st
import json
import os

def initialize_firebase():
    """Initialise Firebase de manière compatible Cloud & Local."""
    if not firebase_admin._apps:
        # 1. Essayer via st.secrets (Pour Streamlit Cloud)
        if "firebase" in st.secrets:
            cred = credentials.Certificate(dict(st.secrets["firebase"]))
            firebase_admin.initialize_app(cred)
            return

        # 2. Essayer via fichier local (Pour votre PC)
        # Chemin vers votre fichier JSON téléchargé
        cred_path = Path("credentials") / "adminsdk.json" 
        # Note: Renommez votre fichier json long en 'adminsdk.json' pour simplifier
        
        if cred_path.exists():
            cred = credentials.Certificate(str(cred_path))
            firebase_admin.initialize_app(cred)
        else:
            st.warning("⚠️ Configuration Firebase non trouvée (ni secrets, ni fichier local).")

def generate_password(length=12):
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(random.choice(chars) for _ in range(length))

# Dans utils/auth.py

def register_user(email, username):
    """Crée l'utilisateur et retourne le mot de passe généré."""
    
    # --- ETAPE DE DEBUG ET NETTOYAGE ---
    print(f"DEBUG AVANT: Email reçu = '{email}'") # Affiche ce que la fonction reçoit
    
    # 1. Sécurité : On s'assure que c'est une chaine de caractères
    if not isinstance(email, str):
        return {"success": False, "error": "L'email n'est pas une chaîne de texte valide."}
    
    # 2. Nettoyage radical : on enlève les espaces avant/après
    email = email.strip()
    
    # 3. Vérification si vide après nettoyage
    if not email:
        return {"success": False, "error": "L'adresse email est vide."}
        
    print(f"DEBUG APRES: Email envoyé à Firebase = '{email}'")
    # -----------------------------------

    try:
        password = generate_password()
        
        # Création Firebase
        user = auth.create_user(
            email=email,
            password=password,
            display_name=username
        )
        
        return {"success": True, "password": password, "user": user}
        
    except ValueError as e:
        # Erreur souvent liée au format (ex: pas de @, pas de .com)
        return {"success": False, "error": f"Format email invalide (Firebase refuse) : {str(e)}"}
        
    except Exception as e:
        # Autres erreurs (déjà existant, problème serveur...)
        return {"success": False, "error": str(e)}

def login_user(email, password):
    """Connecte l'utilisateur via l'API REST."""
    try:
        # Clé API Web (Project Settings > General > Web API Key)
        # Mettez la vôtre ici ou dans st.secrets
        FIREBASE_WEB_API_KEY = "AIzaSyCXahnsJKJdCi55aBlLZvBAJzIGaJyLYbs"
        
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_WEB_API_KEY}"
        response = requests.post(url, json={
            "email": email,
            "password": password,
            "returnSecureToken": True
        })
        data = response.json()
        
        if "idToken" in data:
            return {"success": True, "data": data}
        else:
            error_msg = data.get("error", {}).get("message", "Erreur inconnue")
            return {"success": False, "error": error_msg}
    except Exception as e:
        return {"success": False, "error": str(e)}

def reset_password(email):
    """Envoie un lien de reset password."""
    try:
        FIREBASE_WEB_API_KEY = "AIzaSyCXahnsJKJdCi55aBlLZvBAJzIGaJyLYbs"
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={FIREBASE_WEB_API_KEY}"
        response = requests.post(url, json={
            "requestType": "PASSWORD_RESET",
            "email": email
        })
        if response.status_code == 200:
            return {"success": True}
        else:
            return {"success": False, "error": response.json().get("error", {}).get("message")}
    except Exception as e:
        return {"success": False, "error": str(e)}