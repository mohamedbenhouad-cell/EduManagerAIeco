import os
import json
import numpy as np
import streamlit as st

# Matplotlib en mode "Agg" (pas d'interface graphique requise)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import firebase_admin
from firebase_admin import credentials, firestore


# ---------- Initialisation Firebase (remote-friendly) ----------
def _init_firebase():
    """Initialise Firebase à partir de st.secrets['firebase'], d'une variable
    d'env FIREBASE_SERVICE_ACCOUNT (JSON), ou des ADC (GOOGLE_APPLICATION_CREDENTIALS)."""
    if firebase_admin._apps:
        return

    cred = None

    # 1) Streamlit secrets (recommandé)
    # Dans .streamlit/secrets.toml :
    # [firebase]
    # type="service_account"
    # project_id="..."
    # private_key_id="..."
    # private_key="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
    # client_email="..."
    # client_id="..."
    # token_uri="https://oauth2.googleapis.com/token"
    if "firebase" in st.secrets:
        try:
            cred = credentials.Certificate(dict(st.secrets["firebase"]))
        except Exception as e:
            st.error(f"Secrets Firebase invalides : {e}")
            st.stop()

    # 2) Variable d'env FIREBASE_SERVICE_ACCOUNT contenant le JSON complet
    if cred is None and os.getenv("FIREBASE_SERVICE_ACCOUNT"):
        try:
            svc = json.loads(os.environ["FIREBASE_SERVICE_ACCOUNT"])
            cred = credentials.Certificate(svc)
        except Exception as e:
            st.error(f"FIREBASE_SERVICE_ACCOUNT invalide : {e}")
            st.stop()

    # 3) Application Default Credentials (GOOGLE_APPLICATION_CREDENTIALS ou identité GCP)
    try:
        if cred is not None:
            firebase_admin.initialize_app(cred)
        else:
            firebase_admin.initialize_app()
    except Exception as e:
        st.error(
            "Impossible d'initialiser Firebase. "
            "Ajoutez vos identifiants dans st.secrets['firebase'] ou définissez "
            "FIREBASE_SERVICE_ACCOUNT / GOOGLE_APPLICATION_CREDENTIALS. "
            f"Détail : {e}"
        )
        st.stop()


# ---------- Cache lecture Firestore ----------
@st.cache_data(ttl=60)
def _load_all_notes():
    """Charge toutes les notes depuis Firestore (cache 60s)."""
    db = firestore.client()
    docs = db.collection("notes_etudiants").stream()
    notes_all_users = {}
    for d in docs:
        try:
            notes_all_users[d.id] = d.to_dict() or {}
        except Exception:
            notes_all_users[d.id] = {}
    return notes_all_users


def code2(email_utilisateur: str):
    """
    Affiche la courbe de performance et le tableau des notes
    pour l'utilisateur identifié par email_utilisateur.
    Affiche aussi la moyenne, la moyenne max/min, et le rang utilisateur.
    """
    # 1) Firebase (remote OK)
    _init_firebase()

    if not email_utilisateur:
        st.warning("Impossible d'afficher vos résultats : utilisateur non authentifié.")
        return

    # 2) Récupérer toutes les notes
    try:
        notes_all_users = _load_all_notes()
    except Exception as e:
        st.error(f"Erreur lors de la lecture des notes : {e}")
        return

    if not notes_all_users:
        st.warning("Aucune note n'est disponible pour le moment.")
        return

    # 3) Calculer la moyenne pour chaque utilisateur
    moyennes_utilisateurs = {}
    for user, notes_dict in notes_all_users.items():
        vals = [v for v in notes_dict.values() if isinstance(v, (int, float, np.floating))]
        moyennes_utilisateurs[user] = float(np.mean(vals)) if vals else 0.0

    # 4) Notes de l'utilisateur courant
    user_notes_dict = notes_all_users.get(email_utilisateur)
    if not user_notes_dict:
        st.warning("Aucune note trouvée pour vous.")
        return

    # Tri des cas pour l'affichage
    noms_cas = sorted(list(user_notes_dict.keys()))
    notes = [float(user_notes_dict[n]) if isinstance(user_notes_dict[n], (int, float, np.floating)) else 0.0
             for n in noms_cas]

    # 5) Courbe
    plt.figure(figsize=(10, 5))
    plt.plot(noms_cas, notes, marker="o", linestyle="-", label="Votre performance")
    plt.ylabel("Note")
    plt.xlabel("Cas / Fichier")
    plt.ylim(0, 20)
    plt.title("Votre performance par cas")
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    plt.legend()
    st.pyplot(plt)
    plt.close()

    # 6) Statistiques globales
    all_means = list(moyennes_utilisateurs.values())
    moyenne_all = float(np.mean(all_means)) if all_means else 0.0
    min_all = float(np.min(all_means)) if all_means else 0.0
    max_all = float(np.max(all_means)) if all_means else 0.0
    moyenne_user = moyennes_utilisateurs[email_utilisateur]

    # Rang (1 = meilleur)
    sorted_moyennes = sorted(all_means, reverse=True)
    rang = sorted_moyennes.index(moyenne_user) + 1 if sorted_moyennes else 1

    st.info(f"**Moyenne de la classe :** {moyenne_all:.2f}")
    st.info(f"**Moyenne min de la classe :** {min_all:.2f}")
    st.info(f"**Moyenne max de la classe :** {max_all:.2f}")
    st.info(f"**Votre moyenne :** {moyenne_user:.2f}")
    st.info(f"**Votre rang dans la classe :** {rang} sur {len(moyennes_utilisateurs)}")

    # 7) Détail des notes
    st.markdown("### Détail de vos notes")
    for cas, note in user_notes_dict.items():
        if isinstance(note, (int, float, np.floating)):
            st.write(f"**{cas}** : {float(note):.2f}")
        else:
            st.write(f"**{cas}** : (valeur non numérique)")


# Astuces de déploiement :
# - Streamlit Cloud / serveur : placez l'objet de service Firebase dans .streamlit/secrets.toml (bloc [firebase]).
# - Docker/K8s : exportez FIREBASE_SERVICE_ACCOUNT (JSON complet) ou montez GOOGLE_APPLICATION_CREDENTIALS.
# - Le cache (ttl=60) réduit les lectures Firestore et accélère l'affichage.
