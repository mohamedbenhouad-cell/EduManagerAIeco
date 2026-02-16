import os
import shutil
from pathlib import Path
from uuid import uuid4
import streamlit as st

# ========= CHEMINS PORTABLES (REMOTE) =========
# Racine du projet (fallback sur cwd si __file__ indisponible)
try:
    APP_ROOT = Path(__file__).resolve().parent
except NameError:
    APP_ROOT = Path.cwd()

# Dossier de travail (modifiable via env vars)
DATA_DIR = Path(os.getenv("DATA_DIR", APP_ROOT / "data"))
DOCS_DIR = Path(os.getenv("DOCS_DIR", APP_ROOT / "documents"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DOCS_DIR.mkdir(parents=True, exist_ok=True)  # ok si déjà présent

# Un sous-dossier de travail isolé par session (évite collisions multi-utilisateurs)
if "workdir" not in st.session_state:
    st.session_state.workdir = f"session-{uuid4().hex[:8]}"

BEN_DIR = DATA_DIR / "ben" / st.session_state.workdir
BEN_DIR.mkdir(parents=True, exist_ok=True)

# Chemins vers les fichiers (dans le workdir de la session)
student_pdf_path = BEN_DIR / "Etudiant.pdf"
prof_pdf_path = BEN_DIR / "prof.pdf"


# ========= FONCTION : téléchargement du PDF étudiant =========
def download_student_file():
    uploaded_file = st.file_uploader(
        "Télécharger votre fichier étudiant (PDF uniquement)", type=["pdf"], key="student_uploader"
    )
    if uploaded_file is not None:
        with open(student_pdf_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success(f"Votre fichier étudiant a été enregistré : {student_pdf_path}")
    else:
        st.info("Veuillez sélectionner un PDF étudiant.")


# ========= FONCTION : sélection (ou upload) du PDF professeur =========
def select_professor_file():
    # PDFs disponibles dans le dossier documents/
    files = sorted([p.name for p in DOCS_DIR.glob("*.pdf")])

    if files:
        selected_file = st.selectbox("Sélectionner un fichier professeur (documents/)", files)
        if st.button("Utiliser ce fichier professeur"):
            shutil.copy2(DOCS_DIR / selected_file, prof_pdf_path)
            st.success(f"Le fichier '{selected_file}' a été copié vers : {prof_pdf_path}")
    else:
        st.warning("Aucun PDF trouvé dans le dossier 'documents/'. Vous pouvez en envoyer un ci-dessous.")
        uploaded_prof = st.file_uploader(
            "Uploader un fichier professeur (PDF)", type=["pdf"], key="prof_uploader"
        )
        if uploaded_prof is not None:
            with open(prof_pdf_path, "wb") as f:
                f.write(uploaded_prof.getbuffer())
            st.success(f"Fichier professeur chargé vers : {prof_pdf_path}")
# BEN HOUAD