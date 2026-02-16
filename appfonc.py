import streamlit as st
import os
import shutil
from utils.auth import initialize_firebase, login_user, register_user, reset_password
from utils.email import send_email
from scripts.code3 import code3
from scripts.code2 import code2
# =============== AUTH PAGE (Firebase) ===============
def show_auth_page():
    initialize_firebase()
    st.title("🔐 Authentification")

    if 'auth' not in st.session_state:
        st.session_state.auth = {'logged_in': False, 'user_email': None, 'user_name': None}

    tab_login, tab_register, tab_reset = st.tabs(["Connexion", "Inscription", "Mot de passe oublié"])

    # Connexion
    with tab_login:
        st.subheader("Connectez-vous à votre compte")
        login_email = st.text_input("Adresse email", key="login_email")
        login_pass = st.text_input("Mot de passe", type="password", key="login_pass")
        if st.button("Se connecter", key="login_btn"):
            if not login_email or not login_pass:
                st.warning("Veuillez remplir tous les champs")
            else:
                result = login_user(login_email, login_pass)
                if result["success"]:
                    st.session_state.auth = {
                        'logged_in': True,
                        'user_email': login_email,
                        'user_name': login_email.split('@')[0]
                    }
                    st.success("Connexion réussie !")
                    st.session_state.page = "files"
                    st.rerun()
                else:
                    st.error(f"Erreur : {result['error']}")

    # Inscription
    with tab_register:
        st.subheader("Créez un nouveau compte")
        reg_email = st.text_input("Adresse email", key="reg_email")
        reg_name = st.text_input("Nom complet", key="reg_name")
        if st.button("S'inscrire", key="register_btn"):
            if not reg_email or not reg_name:
                st.warning("Veuillez remplir tous les champs")
            else:
                result = register_user(reg_email, reg_name)
                if result["success"]:
                    email_content = f"""
                    <h3>Bienvenue sur Gestion Budgétaire, {reg_name} !</h3>
                    <p>Votre compte a été créé avec succès.</p>
                    <p><strong>Email :</strong> {reg_email}</p>
                    <p><strong>Mot de passe temporaire :</strong> {result['password']}</p>
                    <p>Vous pouvez changer ce mot de passe dans la section 'Mot de passe oublié'.</p>
                    """
                    send_email(reg_email, "Bienvenue sur Gestion Budgétaire", email_content)
                    st.success("Compte créé avec succès ! Un email avec votre mot de passe a été envoyé.")
                else:
                    st.error(f"Erreur lors de l'inscription : {result['error']}")

    # Réinitialisation mot de passe
    with tab_reset:
        st.subheader("Réinitialisez votre mot de passe")
        reset_email = st.text_input("Entrez votre email", key="reset_email")
        if st.button("Envoyer le lien de réinitialisation", key="reset_btn"):
            if not reset_email:
                st.warning("Veuillez entrer votre adresse email")
            else:
                result = reset_password(reset_email)
                if result["success"]:
                    st.success("Un email de réinitialisation vous a été envoyé.")
                else:
                    st.error(f"Erreur : {result['error']}")

    # Sidebar navigation
    if st.session_state.auth['logged_in']:
        st.sidebar.success(f"Connecté en tant que {st.session_state.auth['user_email']}")
        if st.sidebar.button("Déconnexion"):
            st.session_state.auth = {'logged_in': False, 'user_email': None, 'user_name': None}
            st.session_state.page = "auth"
            st.rerun()
        if st.sidebar.button("Accéder à la correction automatique"):
            st.session_state.page = "files"
            st.rerun()


# =============== PAGE FICHIERS & EXECUTION (Code 1 / 2) ===============
def show_file_and_execution_page(user_email):
    st.title("Espace de dépôt et d'exécution")
    st.info(f"Vous êtes connecté(e) en tant que : {user_email}")

    # 1. Téléchargement du fichier étudiant
    st.header("Étape 1 : Télécharger le fichier étudiant")
    uploaded_file = st.file_uploader("Télécharger votre fichier étudiant (PDF uniquement)", type=["pdf"])
    if uploaded_file is not None:
        ben_folder = os.path.join("/Volumes/D/my_streamlit_app6", "ben")
        if not os.path.exists(ben_folder):
            os.makedirs(ben_folder)
        student_pdf_path = os.path.join(ben_folder, "Etudiant.pdf")
        with open(student_pdf_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success("Votre fichier a été téléchargé avec succès.")

    # 2. Sélection du fichier professeur
    st.header("Étape 2 : Sélectionner le fichier professeur")
    documents_folder = os.path.join("/Volumes/D/my_streamlit_app6", "documents")
    files = [f for f in os.listdir(documents_folder) if f.endswith('.pdf')] if os.path.exists(documents_folder) else []
    selected_file = None
    if files:
        selected_file = st.selectbox('Sélectionner un fichier professeur', files)
        if selected_file:
            ben_folder = os.path.join("/Volumes/D/my_streamlit_app6", "ben")
            if not os.path.exists(ben_folder):
                os.makedirs(ben_folder)
            prof_pdf_path = os.path.join(ben_folder, "prof.pdf")
            shutil.copy2(os.path.join(documents_folder, selected_file), prof_pdf_path)
            st.success(f"Le fichier '{selected_file}' a été sélectionné avec succès comme fichier professeur.")
            st.session_state.selected_prof_file = selected_file  # Stocké pour le code 3
    else:
        st.warning("Aucun fichier PDF trouvé dans le dossier 'documents'.")

    from scripts.code2 import code2

    # --- Code 1/2 (visualiser la performance) ---
    if st.button("Cliquer ici pour visualiser votre performance"):
        st.write("Historique de votre performance.")
        code2(user_email)  # Affichage direct dans Streamlit


    # --- Bouton pour l'analyse de votre travail (code 3) ---
    if "performance_result" in st.session_state:
        if st.button("Cliquer ici pour l’analyse de votre travail"):
            st.session_state.page = "analyse"
            st.rerun()

    if st.sidebar.button("Déconnexion"):
        st.session_state.auth = {'logged_in': False, 'user_email': None, 'user_name': None}
        st.session_state.page = "auth"
        st.rerun()

# =============== PAGE ANALYSE (Code 3) ===============
def show_analyse_page():
    from scripts.code3 import code3
    st.title("Analyse automatique (Code 3)")
    user_email = st.session_state.auth['user_email']
    selected_file = st.session_state.get("selected_prof_file", None)

    if selected_file:
        result_code3 = code3(user_email, selected_file)
        st.write(result_code3)
    else:
        st.warning("Veuillez sélectionner un fichier professeur sur la page précédente.")

    if st.button("Revenir à l'espace d'exécution"):
        st.session_state.page = "files"
        st.rerun()

# =============== NAVIGATION ===============
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
