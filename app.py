import os
import re
import shutil
from pathlib import Path
import streamlit as st

# Configuration de la page (DOIT ÊTRE LA PREMIÈRE COMMANDE STREAMLIT)
st.set_page_config(
    page_title="EduManager AI",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Importations après la config
from utils.auth import initialize_firebase, login_user, register_user, reset_password
from utils.email import send_email
from scripts.code3 import code3
from scripts.code2 import code2

# ================== DESIGN & CSS ==================
def local_css():
    st.markdown("""
    <style>
        /* Importation d'une police Google Font sympa */
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600&display=swap');

        html, body, [class*="css"] {
            font-family: 'Poppins', sans-serif;
        }

        /* Style des boutons */
        .stButton > button {
            background-color: #4F46E5; /* Indigo */
            color: white;
            border-radius: 12px;
            padding: 0.5rem 1rem;
            border: none;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            transition: all 0.3s ease;
            width: 100%;
        }
        .stButton > button:hover {
            background-color: #4338ca;
            transform: translateY(-2px);
            box-shadow: 0 6px 8px rgba(0, 0, 0, 0.15);
        }

        /* Style des inputs */
        .stTextInput > div > div > input {
            border-radius: 10px;
            border: 1px solid #E5E7EB;
        }

        /* Cartes pour les conteneurs */
        .css-1r6slb0 {
            background-color: #F3F4F6;
            padding: 20px;
            border-radius: 15px;
        }
        
        /* Titres colorés */
        h1, h2, h3 {
            color: #111827;
        }
        
        /* Sidebar jolie */
        [data-testid="stSidebar"] {
            background-color: #f9fafb;
            border-right: 1px solid #e5e7eb;
        }
    </style>
    """, unsafe_allow_html=True)

# Appliquer le CSS
local_css()

# ================== CONFIGURATION & PATHS ==================
APP_ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("DATA_DIR", str(APP_ROOT / "data")))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DOCS_DIR = Path(os.getenv("DOCS_DIR", str(APP_ROOT / "documents")))
DOCS_DIR.mkdir(parents=True, exist_ok=True)

def _user_slug(email: str) -> str:
    base = (email or "anonymous").split("@")[0]
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", base)

def _user_workdir(email: str) -> Path:
    slug = _user_slug(email)
    d = DATA_DIR / "ben" / slug
    d.mkdir(parents=True, exist_ok=True)
    return d

# ================== PAGES ==================

def show_auth_page():
    initialize_firebase()
    
    # Centrage du formulaire de connexion avec des colonnes
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("<h1 style='text-align: center;'>🎓 EduManager AI</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: gray;'>Votre assistant pédagogique intelligent</p>", unsafe_allow_html=True)
        st.write("") # Spacer

        if 'auth' not in st.session_state:
            st.session_state.auth = {'logged_in': False, 'user_email': None, 'user_name': None}

        # Carte blanche pour le login (effet visuel)
        with st.container():
            tab_login, tab_register, tab_reset = st.tabs(["🔑 Connexion", "📝 Inscription", "❓ Oubli ?"])

            # --- CONNEXION ---
            with tab_login:
                st.write("")
                login_email = st.text_input("Adresse email", key="login_email", placeholder="exemple@ecole.com")
                login_pass = st.text_input("Mot de passe", type="password", key="login_pass")
                st.write("")
                if st.button("Se connecter", key="login_btn"):
                    if not login_email or not login_pass:
                        st.warning("⚠️ Veuillez remplir tous les champs")
                    else:
                        with st.spinner("Connexion en cours..."):
                            result = login_user(login_email, login_pass)
                        if result.get("success"):
                            st.session_state.auth = {
                                'logged_in': True,
                                'user_email': login_email,
                                'user_name': login_email.split('@')[0]
                            }
                            st.toast("Connexion réussie ! 🚀", icon="✅")
                            st.session_state.page = "files"
                            st.rerun()
                        else:
                            st.error(f"Erreur : {result.get('error')}")

            # --- INSCRIPTION ---
            with tab_register:
                st.write("")
                reg_email = st.text_input("Adresse email", key="reg_email")
                reg_name = st.text_input("Nom et Prénom", key="reg_name")
                st.write("")
                if st.button("Créer un compte", key="register_btn"):
                    if not reg_email or not reg_name:
                        st.warning("⚠️ Champs manquants")
                    else:
                        with st.spinner("Création du compte..."):
                            result = register_user(reg_email, reg_name)
                        if result.get("success"):
                            # Email logic (inchangé)
                            email_content = f"""
                            <h3>Bienvenue, {reg_name} !</h3>
                            <p>Compte créé.</p>
                            <p><strong>Email :</strong> {reg_email}</p>
                            <p><strong>Mot de passe :</strong> {result['password']}</p>
                            <p>Code Classroom : iah5b574</p>
                            """
                            send_email(reg_email, "Bienvenue", email_content)
                            st.success("Compte créé ! Vérifiez vos emails.")
                        else:
                            st.error(f"Erreur : {result.get('error')}")

            # --- RESET ---
            with tab_reset:
                st.write("")
                reset_email = st.text_input("Email pour réinitialiser", key="reset_email")
                if st.button("Envoyer le lien", key="reset_btn"):
                    if not reset_email:
                        st.warning("Email requis")
                    else:
                        result = reset_password(reset_email)
                        if result.get("success"):
                            st.success("Lien envoyé par email !")
                        else:
                            st.error(f"Erreur : {result.get('error')}")


def show_file_and_execution_page(user_email: str):
    # Sidebar améliorée
    with st.sidebar:
        st.markdown(f"### 👋 Bonjour, \n**{user_email.split('@')[0]}**")
        st.divider()
        if st.button("🚪 Déconnexion"):
            st.session_state.auth = {'logged_in': False, 'user_email': None, 'user_name': None}
            st.session_state.page = "auth"
            st.rerun()
        st.divider()
        st.info("💡 **Astuce**\nAssurez-vous que vos PDF sont lisibles.")

    # Titre principal
    st.title("📂 Espace de Travail")
    st.markdown("---")

    workdir = _user_workdir(user_email)
    student_pdf_path = workdir / "Etudiant.pdf"
    prof_pdf_path = workdir / "prof.pdf"

    # Layout en 2 colonnes pour UPLOAD vs SELECT
    col1, col2 = st.columns(2, gap="large")

    with col1:
        st.markdown("### 1️⃣ Votre Devoir")
        st.markdown("_Déposez votre fichier ici_")
        uploaded_file = st.file_uploader("", type=["pdf"], key="stu_up")
        
        if uploaded_file is not None:
            with open(student_pdf_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            st.success("✅ Fichier étudiant reçu")
            st.session_state.uploaded_student = True
        else:
            st.info("En attente du fichier...")

    with col2:
        st.markdown("### 2️⃣ Le Corrigé Professeur")
        st.markdown("_Sélectionnez ou uploadez le corrigé_")
        
        files = sorted([f.name for f in DOCS_DIR.glob("*.pdf")])
        
        tab_select, tab_upload = st.tabs(["📚 Liste", "📤 Upload"])
        
        with tab_select:
            if files:
                selected_file = st.selectbox('Choisir un fichier disponible', files)
                if st.button("Valider ce choix"):
                    shutil.copy2(DOCS_DIR / selected_file, prof_pdf_path)
                    st.success(f"✅ '{selected_file}' sélectionné")
                    st.session_state.selected_prof_file = selected_file
                    st.session_state.uploaded_prof = True
            else:
                st.warning("Aucun fichier disponible sur le serveur.")

        with tab_upload:
            uploaded_prof = st.file_uploader("Uploader un corrigé (PDF)", type=["pdf"], key="prof_up_new")
            if uploaded_prof is not None:
                with open(prof_pdf_path, "wb") as f:
                    f.write(uploaded_prof.getbuffer())
                st.success("✅ Corrigé chargé manuellement")
                st.session_state.selected_prof_file = "Upload manuel"
                st.session_state.uploaded_prof = True

    st.markdown("---")

    # Zone d'actions (Gros boutons centrés)
    st.subheader("🚀 Actions")
    
    c_act1, c_act2 = st.columns(2)
    
    with c_act1:
        st.markdown("#### Performance")
        if st.button("📊 Voir mes statistiques", use_container_width=True):
            code2(user_email)
            
    with c_act2:
        st.markdown("#### Correction")
        # Logique pour activer/désactiver le bouton
        student_ok = st.session_state.get("uploaded_student", False)
        prof_ok = st.session_state.get("uploaded_prof", False)
        
        if st.button("✨ Lancer l'analyse IA", disabled=not(student_ok and prof_ok), use_container_width=True):
            st.session_state.page = "analyse"
            st.rerun()
        
        if not (student_ok and prof_ok):
            st.caption("⚠️ *Chargez les 2 fichiers pour activer l'analyse*")


def show_analyse_page():
    # Bouton retour en haut
    if st.button("⬅️ Retour aux fichiers"):
        st.session_state.page = "files"
        st.rerun()
        
    st.title("🤖 Analyse Automatique")
    st.markdown("---")

    user_email = st.session_state.auth['user_email'] if 'auth' in st.session_state else None
    selected_file = st.session_state.get("selected_prof_file", None)

    if user_email:
        with st.spinner("L'IA analyse vos documents... Cela peut prendre quelques secondes."):
            # Appel du script d'analyse
            result_code3 = code3(user_email, selected_file)
            
        if result_code3 is not None:
            # Affichage joli du résultat
            st.container().write(result_code3)
            st.balloons() # Petite animation festive
    else:
        st.error("Session expirée. Veuillez vous reconnecter.")


# ================== NAVIGATION ROUTER ==================
if 'page' not in st.session_state:
    st.session_state.page = "auth"

if st.session_state.page == "auth":
    show_auth_page()
elif st.session_state.page == "files":
    if 'auth' in st.session_state and st.session_state.auth.get('logged_in', False):
        show_file_and_execution_page(st.session_state.auth['user_email'])
    else:
        st.session_state.page = "auth"
        st.rerun()
elif st.session_state.page == "analyse":
    show_analyse_page()
