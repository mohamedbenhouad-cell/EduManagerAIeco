# app.py
import streamlit as st
import pandas as pd
import os
import shutil

from scripts.code2 import code_2
from scripts.code3 import code_3  # Importer le code 3

# Chemin vers le fichier Excel
excel_file_path = "/Volumes/D/my_streamlit_app4/Gestion des utilisateurs et des notes.xlsx"

# Initialisation de st.session_state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.nom_utilisateur = None

# Exception personnalisée pour gérer les erreurs sans afficher de traçage complet
class ExitScript(Exception):
    pass

# Charger le fichier Excel
try:
    df = pd.read_excel(excel_file_path)
except FileNotFoundError:
    st.error(f"Erreur : Le fichier '{excel_file_path}' est introuvable.")
    raise ExitScript()

# Fonction pour l'authentification
def verifier_utilisateur(nom_utilisateur, nom, prenom, numero_confidentiel):
    try:
        required_columns = ["Nom de l'utilisateur", "Nom", "Prénom", "Numéro confidentiel"]
        for col in required_columns:
            if col not in df.columns:
                st.error(f"Erreur : La colonne '{col}' est manquante dans le fichier Excel.")
                raise ExitScript()

        numero_confidentiel_str = str(numero_confidentiel)

        utilisateur_data = df[(df["Nom de l'utilisateur"] == nom_utilisateur) & 
                              (df["Nom"] == nom) & 
                              (df["Prénom"] == prenom) &
                              (df["Numéro confidentiel"].astype(str) == numero_confidentiel_str)]
        if not utilisateur_data.empty:
            st.success("Vous êtes connecté(e) à l'application.")
            return True
        else:
            st.error("Informations incorrectes. Veuillez contacter l'administrateur.")
            raise ExitScript()
    except Exception as e:
        st.error(f"Une erreur s'est produite : {e}")
        raise ExitScript()

# Fonction pour télécharger le fichier étudiant
def download_student_file():
    uploaded_file = st.file_uploader("Télécharger votre fichier étudiant (PDF uniquement)", type=["pdf"])
    if uploaded_file is not None:
        ben_folder = os.path.join("/Volumes/D/my_streamlit_app4", "ben")
        if not os.path.exists(ben_folder):
            os.makedirs(ben_folder)
        student_pdf_path = os.path.join(ben_folder, "Etudiant.pdf")
        with open(student_pdf_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success("Votre fichier a été téléchargé avec succès.")
    else:
        st.warning("Veuillez télécharger un fichier au format PDF.")

# Fonction pour sélectionner le fichier professeur
def select_professor_file():
    documents_folder = os.path.join("/Volumes/D/my_streamlit_app", "documents")
    files = [f for f in os.listdir(documents_folder) if f.endswith('.pdf')]
    if files:
        selected_file = st.selectbox('Sélectionner un fichier professeur', files)
        if selected_file:
            ben_folder = os.path.join("/Volumes/D/my_streamlit_app", "ben")
            if not os.path.exists(ben_folder):
                os.makedirs(ben_folder)
            prof_pdf_path = os.path.join(ben_folder, "prof.pdf")
            shutil.copy2(os.path.join(documents_folder, selected_file), prof_pdf_path)
            st.success(f"Le fichier '{selected_file}' a été sélectionné avec succès comme fichier professeur.")
            return selected_file
    else:
        st.warning("Aucun fichier PDF trouvé dans le dossier 'documents'.")
    return None

# Fonction pour la page d'exécution des codes
def execution_page(nom_utilisateur):
    st.title("Exécution de codes Python")
    
    st.header("Étape 1 : Télécharger le fichier étudiant")
    download_student_file()

    st.header("Étape 2 : Sélectionner le fichier professeur")
    selected_file = select_professor_file()

    if st.button("Cliquer ici pour visualiser votre performance"):
        st.write("Historique de votre performance.")
        result = code_2(nom_utilisateur)
        if result.startswith("Résultat du Code 2. Graphique enregistré à : "):
            image_path = result.split("Graphique enregistré à : ")[1]
            st.image(image_path)
        else:
            st.write(result)
    
    if st.button("Cliquer ici pour afficher votre note"):
        if selected_file:
            result_code_3 = code_3(nom_utilisateur, selected_file)  # Passer selected_file comme argument
            st.write(result_code_3)
        else:
            st.warning("Veuillez sélectionner un fichier professeur.")

# Authentification de l'utilisateur
st.title("Authentification")
nom_utilisateur = st.text_input("Nom d'utilisateur")
nom = st.text_input("Nom")
prenom = st.text_input("Prénom")
numero_confidentiel = st.text_input("Numéro confidentiel", type="password")

# Vérifier l'authentification si les champs sont remplis
if nom_utilisateur and nom and prenom and numero_confidentiel:
    try:
        if verifier_utilisateur(nom_utilisateur, nom, prenom, numero_confidentiel):
            # Redirection vers la page d'exécution avec les paramètres d'authentification
            st.session_state.authenticated = True
            st.session_state.nom_utilisateur = nom_utilisateur
    except ExitScript:
        st.error("Le script s'est arrêté en raison d'une erreur.")

# Affichage de la page correspondante si authentifié
if st.session_state.authenticated:
    execution_page(st.session_state.nom_utilisateur)

