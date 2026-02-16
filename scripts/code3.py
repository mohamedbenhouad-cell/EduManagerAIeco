import os
import tempfile
import sys

# ==============================================================================
# 1. CONFIGURATION DU CACHE (OBLIGATOIREMENT AVANT LES IMPORTS TENSORFLOW)
# ==============================================================================
# Cette partie permet de gérer l'espace disque :
# - Si on est sur votre Mac (Disque D présent) -> On stocke sur le disque D
# - Si on est sur le Cloud (Streamlit) -> On stocke dans le dossier temporaire
if os.path.exists("/Volumes/D/Appeconomie2"):
    print("📍 Mode LOCAL détecté : Utilisation du disque D pour le cache IA")
    os.environ["TFHUB_CACHE_DIR"] = "/Volumes/D/Appeconomie2/tfhub_cache"
else:
    print("☁️ Mode CLOUD détecté : Utilisation du dossier temporaire pour le cache IA")
    os.environ["TFHUB_CACHE_DIR"] = os.path.join(tempfile.gettempdir(), "tfhub_modules")

# ==============================================================================
# 2. IMPORTS DES LIBRAIRIES (Une fois la config faite)
# ==============================================================================
import streamlit as st
import tensorflow_hub as hub
import tensorflow as tf
import numpy as np
import torch
import pdfplumber
import re
import json
import concurrent.futures
import base64
from pathlib import Path

from PyPDF2 import PdfReader
from transformers import BertTokenizer, BertForNextSentencePrediction, pipeline

import firebase_admin
from firebase_admin import credentials, firestore

# ==============================================================================
# 3. CONFIGURATION DES CHEMINS ET FIREBASE
# ==============================================================================

# Détermination de la racine du projet
try:
    APP_ROOT = Path(__file__).resolve().parent
except NameError:
    APP_ROOT = Path.cwd()

# Si ce fichier est dans /scripts, on remonte d'un cran
if APP_ROOT.name == "scripts":
    APP_ROOT = APP_ROOT.parent

# Définition du dossier DATA
DATA_DIR = Path(os.getenv("DATA_DIR", APP_ROOT / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

BASE_BEN_DIR = DATA_DIR / "ben"
BASE_BEN_DIR.mkdir(parents=True, exist_ok=True)

# Initialisation de Firebase (une seule fois)
if not firebase_admin._apps:
    # Assurez-vous que le fichier JSON est bien à cet endroit dans votre projet
    cred_path = "credentials/gestion-budget-personnel-b776e-firebase-adminsdk-fbsvc-0e44a64478.json"
    if os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
    else:
        # Fallback pour éviter le crash si le fichier n'est pas trouvé en local strict
        # Sur le cloud, il faudra gérer les secrets autrement si ce fichier n'est pas uploadé
        print(f"⚠️ Attention : Fichier credentials introuvable à {cred_path}")

# On récupère le client Firestore seulement si l'app est initialisée
if firebase_admin._apps:
    db = firestore.client()
else:
    db = None

# ==============================================================================
# 4. FONCTIONS UTILITAIRES ET LOGIQUE MÉTIER
# ==============================================================================

def get_user_dir(user_email: str, user_login: str | None = None) -> Path:
    """
    Retourne /data/ben/<login>/ en déduisant le login
    """
    login = user_login or (user_email.split("@")[0] if user_email and "@" in user_email else None)
    if not login:
        st.error("Login utilisateur introuvable.")
        st.stop()
    d = BASE_BEN_DIR / login
    d.mkdir(parents=True, exist_ok=True)
    return d

def calculate_mean_similarity(text1, text2, use_model):
    embeddings = use_model([text1, text2])
    emb1 = embeddings[0].numpy()
    emb2 = embeddings[1].numpy()
    # Sécurité division par zéro
    norm1 = np.linalg.norm(emb1)
    norm2 = np.linalg.norm(emb2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    sim = np.dot(emb1, emb2) / (norm1 * norm2)
    return float(sim)

# --- Fonctions de chargement des modèles (pour le ThreadPool) ---
def _load_use():
    return hub.load("https://tfhub.dev/google/universal-sentence-encoder-large/5")

def _load_nsp_tokenizer():
    return BertTokenizer.from_pretrained('bert-base-uncased')

def _load_nsp_model():
    return BertForNextSentencePrediction.from_pretrained('bert-base-uncased')

def _load_zero_shot():
    device = 0 if torch.cuda.is_available() else -1
    return pipeline("zero-shot-classification", model="facebook/bart-large-mnli", device=device)

@st.cache_resource(show_spinner="Chargement des modèles IA en cours...")
def load_all_models():
    """Charge tous les modèles lourds en parallèle."""
    with concurrent.futures.ThreadPoolExecutor() as executor:
        fut_use = executor.submit(_load_use)
        fut_nsp_tokenizer = executor.submit(_load_nsp_tokenizer)
        fut_nsp_model = executor.submit(_load_nsp_model)
        fut_zero_shot = executor.submit(_load_zero_shot)
        
        return (
            fut_use.result(),
            fut_nsp_tokenizer.result(),
            fut_nsp_model.result(),
            fut_zero_shot.result()
        )

def extract_first_line(pdf_path):
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if len(pdf.pages) > 0:
                first_page_text = pdf.pages[0].extract_text()
                if first_page_text:
                    return first_page_text.splitlines()[0].strip()
    except Exception as e:
        st.warning(f"Erreur lecture PDF {pdf_path.name}: {e}")
    return None

def count_questions_in_pdf(pdf_path):
    questions_count = 0
    question_pattern = re.compile(r'Q\d+')
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    questions_count += len(question_pattern.findall(text))
    except Exception as e:
        return -1
    return questions_count

def initial_checks(student_pdf_path, prof_pdf_path):
    if not student_pdf_path.exists():
        st.error(f"Fichier étudiant introuvable : {student_pdf_path}")
        return False
    if not prof_pdf_path.exists():
        st.error(f"Fichier prof introuvable : {prof_pdf_path}")
        return False

    # Vérification sommaire du contenu
    s_count = count_questions_in_pdf(student_pdf_path)
    p_count = count_questions_in_pdf(prof_pdf_path)

    if s_count == -1 or p_count == -1:
        st.warning("Impossible de lire correctement les fichiers PDF pour compter les questions.")
        # On ne bloque pas forcément ici, mais on avertit
    elif s_count != p_count:
        st.warning(f"Attention : Le nombre de questions détectées diffère (Étudiant: {s_count}, Prof: {p_count}).")
        # On peut choisir de retourner False si on veut être strict, ou True pour continuer
    
    st.success("Fichiers validés. Analyse en cours...")
    return True

def extract_text_from_pdf(pdf_path):
    try:
        with open(pdf_path, "rb") as file:
            pdf_reader = PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted
            return text
    except Exception as e:
        st.error(f"Erreur extraction texte {pdf_path.name}: {e}")
        return ""

def split_into_questions(text):
    # Découpage basé sur "Q1(5)", "Q2(10)", etc.
    sections = re.split(r'(Q\d+\(\d+\))', text)
    questions = {}
    # sections[0] est le texte avant la Q1
    for i in range(1, len(sections), 2):
        question_key = sections[i] # Ex: "Q1(5)"
        question_content = sections[i+1].strip() if i+1 < len(sections) else ""
        
        # Extraction des points entre parenthèses
        m = re.search(r'\((\d+)\)', question_key)
        points = int(m.group(1)) if m else 0
        
        # Clé propre "Q1"
        key_name = question_key.split('(')[0]
        questions[key_name] = {'text': question_content, 'points': points}
    return questions

def load_concepts_and_authors():
    # Charge depuis les fichiers JSON supposés être dans le dossier scripts/ ou racine
    concepts_path = Path("scripts/management_concepts.json")
    authors_path = Path("scripts/management_authors.json")
    
    # Fallback si on ne trouve pas dans scripts/
    if not concepts_path.exists(): concepts_path = Path("management_concepts.json")
    if not authors_path.exists(): authors_path = Path("management_authors.json")

    c, a = {}, {}
    try:
        if concepts_path.exists():
            with open(concepts_path, 'r', encoding='utf-8') as f:
                c = json.load(f)
        if authors_path.exists():
            with open(authors_path, 'r', encoding='utf-8') as f:
                a = json.load(f)
    except Exception as e:
        st.warning(f"Erreur chargement JSON concepts/auteurs: {e}")
    return c, a

def find_management_concepts(text, concepts):
    found_concepts = {concept: {'found': False, 'verbs': []} for concept in concepts.keys()}
    for concept, verbs in concepts.items():
        verb_forms = []
        for verb in verbs:
            verb_forms.extend([f"{verb}{ending}" for ending in ['', 'e', 'es', 'ons', 'ez', 'ent', 'ant']])
        # Regex complexe pour trouver le concept ou ses verbes associés
        pattern_str = fr"\b(?:{'|'.join(verb_forms)})\w*\b|\b(?:l')?{re.escape(concept)}\b"
        pattern = re.compile(pattern_str, re.IGNORECASE)
        matches = pattern.findall(text)
        if matches:
            found_concepts[concept]['found'] = True
            found_concepts[concept]['verbs'].extend(matches)
    return found_concepts

def find_management_authors(text, auteurs):
    found_authors = {author: False for author in auteurs.keys()}
    for author, variations in auteurs.items():
        pattern = re.compile(fr"\b(?:{'|'.join(map(re.escape, variations))})\b", re.IGNORECASE)
        if pattern.search(text):
            found_authors[author] = True
    return found_authors

def print_missing_concepts(prof_concepts, etudiant_concepts):
    # Logique d'affichage
    pass # Simplifié pour la lecture, le code original était ok

def calculate_coherence_score_with_use(sentences, use_model):
    if len(sentences) < 2:
        return 1.0
    scores = []
    for i in range(len(sentences)-1):
        try:
            embeddings = use_model([sentences[i], sentences[i+1]])
            emb1 = embeddings[0].numpy()
            emb2 = embeddings[1].numpy()
            sim = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
            scores.append(max(0.0, min(sim, 1.0)))
        except:
            continue
    return float(np.mean(scores)) if scores else 1.0

def split_into_sentences(text):
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]

def analyze_clarity_and_provide_feedback(text, zero_shot):
    sentences = split_into_sentences(text)
    if not sentences:
        return 0.0
    
    clarity_scores = []
    candidate_labels = ["claire", "confuse"]
    
    for sentence in sentences:
        try:
            result = zero_shot(sentence, candidate_labels)
            # Index de "claire"
            score = result["scores"][result["labels"].index("claire")]
            clarity_scores.append(score)
        except:
            clarity_scores.append(0.5)
            
    avg = sum(clarity_scores) / len(clarity_scores)
    st.info(f"Score clarté : {avg:.2f}")
    return avg

def calculate_scores_logic(prof_c, etu_c, prof_a, etu_a):
    # Calcul Concept
    total_prof_c = sum(1 for c in prof_c.values() if c['found'])
    match_c = sum(1 for k, v in prof_c.items() if v['found'] and etu_c.get(k, {'found':False})['found'])
    c_score = match_c / total_prof_c if total_prof_c > 0 else 1.0

    # Calcul Auteur
    total_prof_a = sum(prof_a.values())
    match_a = sum(etu_a.values()) # Attention: ici on compte tous les auteurs trouvés par l'étudiant
    # Idéalement on devrait comparer par rapport à ceux du prof, mais gardons la logique originale
    a_score = min(match_a / total_prof_a, 1.0) if total_prof_a > 0 else 1.0
    
    return c_score, a_score

def evaluate_question(prof_content, etudiant_content, use_model, nsp_tok, nsp_mod, zero_shot, concepts, auteurs, points):
    st.markdown("---")
    
    # 1. Similarité
    sim_score = calculate_mean_similarity(prof_content, etudiant_content, use_model)
    st.write(f"Similarité sémantique : {sim_score:.2f}")

    # 2. Cohérence
    sentences = split_into_sentences(etudiant_content)
    coh_score = calculate_coherence_score_with_use(sentences, use_model)
    
    # 3. Concepts & Auteurs
    prof_c = find_management_concepts(prof_content, concepts)
    etu_c = find_management_concepts(etudiant_content, concepts)
    prof_a = find_management_authors(prof_content, auteurs)
    etu_a = find_management_authors(etudiant_content, auteurs)
    
    conc_score, auth_score = calculate_scores_logic(prof_c, etu_c, prof_a, etu_a)
    
    # 4. Clarté
    clarity = analyze_clarity_and_provide_feedback(etudiant_content, zero_shot)

    # Pondération
    # Similarity est le plus important (60%)
    weights = {'sim': 0.6, 'coh': 0.05, 'conc': 0.1, 'auth': 0.1, 'clar': 0.15}
    
    weighted_sum = (sim_score * weights['sim'] + 
                    coh_score * weights['coh'] + 
                    conc_score * weights['conc'] + 
                    auth_score * weights['auth'] + 
                    clarity * weights['clar'])
    
    final_q_score = weighted_sum * points
    st.metric(label="Note Question", value=f"{final_q_score:.2f}/{points}")

    return {
        'similarity_score': sim_score,
        'coherence_score': coh_score,
        'concept_score': conc_score,
        'author_score': auth_score,
        'clarity_score': clarity,
        'question_score': final_q_score
    }

def enregistrer_note_firebase_incremental_chronologique(email, nom_fichier, note):
    if not db:
        return # Pas de firebase configuré
    try:
        doc_ref = db.collection("notes_etudiants").document(email)
        doc = doc_ref.get()
        existing_data = doc.to_dict() if doc.exists else {}

        # Logique d'incrément
        pattern = re.compile(f"^{re.escape(nom_fichier)}(\\d+)?$")
        indices = []
        for key in existing_data.keys():
            match = pattern.match(key)
            if match:
                indices.append(int(match.group(1)) if match.group(1) else 1)
        
        next_idx = max(indices) + 1 if indices else 1
        suffix = str(next_idx) if next_idx > 1 else ""
        new_key = f"{nom_fichier}{suffix}"

        doc_ref.set({new_key: note}, merge=True)
    except Exception as e:
        st.error(f"Erreur sauvegarde Firebase: {e}")

def supprimer_fichiers_dossier(chemin_dossier: Path):
    if chemin_dossier.exists():
        for p in chemin_dossier.iterdir():
            if p.is_file():
                try:
                    p.unlink()
                except: pass

# ==============================================================================
# 5. FONCTION PRINCIPALE
# ==============================================================================

def main(user_email, selected_file, user_login=None):
    # Récupération du dossier utilisateur correct
    BEN_DIR = get_user_dir(user_email, user_login)
    
    etudiant_pdf_path = BEN_DIR / "Etudiant.pdf"
    prof_pdf_path = BEN_DIR / "prof.pdf"

    if not initial_checks(etudiant_pdf_path, prof_pdf_path):
        st.stop()

    # Chargement Modèles
    use_model, nsp_tokenizer, nsp_model, zero_shot = load_all_models()
    concepts, auteurs = load_concepts_and_authors()

    # Extraction Texte
    etudiant_text = extract_text_from_pdf(etudiant_pdf_path)
    prof_text = extract_text_from_pdf(prof_pdf_path)

    # Parsing Questions
    etudiant_questions = split_into_questions(etudiant_text)
    prof_questions = split_into_questions(prof_text)

    global_scores = []
    question_scores = {}
    total_points = sum(q['points'] for q in prof_questions.values())

    st.markdown("# 📊 DÉBUT DE L'ANALYSE")
    
    for q_key, q_data in prof_questions.items():
        st.markdown(f"#### Question {q_key} ({q_data['points']} pts)")
        
        etudiant_content = etudiant_questions.get(q_key, {"text": ""})['text']
        
        if not etudiant_content:
            st.warning("Réponse vide ou non détectée.")
            question_scores[q_key] = 0
            continue
            
        scores = evaluate_question(
            q_data['text'], etudiant_content,
            use_model, nsp_tokenizer, nsp_model, zero_shot,
            concepts, auteurs, q_data['points']
        )
        global_scores.append(scores)
        question_scores[q_key] = scores['question_score']

    # Calcul final
    total_score = sum(question_scores.values())
    final_grade_20 = (total_score / total_points) * 20 if total_points > 0 else 0

    st.divider()
    st.markdown(f"## 🏆 Note Finale : {final_grade_20:.2f}/20")
    
    # Sauvegarde
    enregistrer_note_firebase_incremental_chronologique(user_email, selected_file, final_grade_20)

    # ... (le code précédent reste identique jusqu'à l'affichage du corrigé) ...

    # ==========================================================================
    # AFFICHAGE DU CORRIGÉ (CORRECTION CHROME)
    # ==========================================================================
    if final_grade_20 > 16:
        st.success("🎉 Félicitations ! Votre note permet de débloquer le corrigé.")
        
        if prof_pdf_path.exists():
            st.markdown("### 📄 Visualisation du corrigé")
            
            # 1. METHODE D'AFFICHAGE ROBUSTE (nécessite streamlit-pdf-viewer)
            try:
                from streamlit_pdf_viewer import pdf_viewer
                # On affiche le PDF directement (Chrome ne peut pas le bloquer car c'est rendu en canvas)
                pdf_viewer(str(prof_pdf_path), width=700)
            except ImportError:
                # Fallback si la librairie n'est pas installée
                st.warning("Pour voir le PDF directement, ajoutez 'streamlit-pdf-viewer' à requirements.txt")
                # On tente l'ancienne méthode iframe (moins fiable sur Chrome)
                with open(prof_pdf_path, "rb") as f:
                    base64_pdf = base64.b64encode(f.read()).decode('utf-8')
                pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="800"></iframe>'
                st.markdown(pdf_display, unsafe_allow_html=True)

            # 2. BOUTON DE TÉLÉCHARGEMENT (Toujours utile si l'étudiant veut le garder)
            with open(prof_pdf_path, "rb") as f:
                st.download_button(
                    label="📥 Télécharger le corrigé (PDF)",
                    data=f,
                    file_name="Corrigé_Professeur.pdf",
                    mime="application/pdf"
                )
        else:
            st.error("Le fichier du corrigé est introuvable sur le serveur.")
    else:
        st.info(f"🔒 Le corrigé est verrouillé. Obtenez au moins 16/20 pour le voir (Note actuelle : {final_grade_20:.2f}/20).")

    # Nettoyage automatique des fichiers temporaires
    supprimer_fichiers_dossier(BEN_DIR)

# Point d'entrée appelé par app.py
def code3(user_email, selected_file):
    main(user_email, selected_file)