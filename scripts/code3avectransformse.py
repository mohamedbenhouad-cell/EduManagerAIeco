import numpy as np
import torch
import tensorflow_hub as hub
from PyPDF2 import PdfReader
from transformers import pipeline
from sentence_transformers import SentenceTransformer
import pdfplumber
import re
import os
import json
import concurrent.futures
import streamlit as st

def calculate_mean_similarity(text1, text2, use_model):
    """Calcule la similarité cosinus moyenne entre deux textes à l'aide de Universal Sentence Encoder."""
    embeddings = use_model([text1, text2])
    emb1 = embeddings[0].numpy()
    emb2 = embeddings[1].numpy()
    sim = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
    return float(sim)

def _load_use():
    return hub.load("https://tfhub.dev/google/universal-sentence-encoder-large/5")

def _load_zero_shot():
    device = 0 if torch.cuda.is_available() else -1
    return pipeline("zero-shot-classification", model="facebook/bart-large-mnli", device=device)

@st.cache_resource(show_spinner="Chargement des modèles…")
def load_all_models():
    with concurrent.futures.ThreadPoolExecutor() as executor:
        fut_use = executor.submit(_load_use)
        fut_zero_shot = executor.submit(_load_zero_shot)
        fut_sbert = executor.submit(lambda: SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2'))
        use_model = fut_use.result()
        zero_shot = fut_zero_shot.result()
        sbert_model = fut_sbert.result()
        return use_model, zero_shot, sbert_model

def extract_first_line(pdf_path):
    try:
        with pdfplumber.open(pdf_path) as pdf:
            first_page_text = pdf.pages[0].extract_text()
            if first_page_text:
                return first_page_text.splitlines()[0].strip()
    except Exception as e:
        st.warning(f"Erreur lors de la lecture du fichier {pdf_path}: {e}")
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
    except FileNotFoundError:
        st.warning(f"Erreur : Le fichier '{pdf_path}' n'existe pas.")
        return -1
    except Exception as e:
        st.warning(f"Erreur lors de la lecture du fichier PDF '{pdf_path}': {str(e)}")
        return -1
    return questions_count

def initial_checks(student_pdf_path, prof_pdf_path):
    if not os.path.exists(student_pdf_path):
        st.warning(f"Erreur : Le fichier '{student_pdf_path}' est introuvable.")
        return False
    if not os.path.exists(prof_pdf_path):
        st.warning(f"Erreur : Le fichier '{prof_pdf_path}' est introuvable.")
        return False
    student_first_line = extract_first_line(student_pdf_path)
    prof_first_line = extract_first_line(prof_pdf_path)
    if student_first_line and prof_first_line:
        if student_first_line.replace(" ", "") != prof_first_line.replace(" ", ""):
            st.warning("Votre fichier semble différer du modèle du professeur. Veuillez télécharger ou sélectionner le bon fichier.")
            return False
    student_questions_count = count_questions_in_pdf(student_pdf_path)
    professor_questions_count = count_questions_in_pdf(prof_pdf_path)
    if student_questions_count == -1 or professor_questions_count == -1:
        st.warning("Erreur lors du comptage des questions dans les fichiers PDF.")
        return False
    if student_questions_count != professor_questions_count:
        st.warning(f"Votre fichier semble différer du modèle du professeur.\nNombre de questions dans le fichier étudiant : {student_questions_count}\nNombre de questions dans le fichier du professeur : {professor_questions_count}")
        return False
    st.success("Vérifications initiales passées avec succès. Veuillez patienter…")
    return True

def extract_text_from_pdf(pdf_path):
    with open(pdf_path, "rb") as file:
        pdf_reader = PdfReader(file)
        text = ""
        for page_num in range(len(pdf_reader.pages)):
            text += pdf_reader.pages[page_num].extract_text()
        return text

def split_into_questions(text):
    sections = re.split(r'(Q\d+\(\d+\))', text)
    questions = {}
    for i in range(1, len(sections), 2):
        question_key = sections[i]
        question_content = sections[i+1].strip() if i+1 < len(sections) else ""
        m = re.search(r'\((\d+)\)', question_key)
        points = int(m.group(1)) if m else 0
        questions[question_key.split('(')[0]] = {'text': question_content, 'points': points}
    return questions

def load_concepts_and_authors():
    try:
        with open('/Volumes/D/my_streamlit_app6/scripts/management_concepts.json', 'r', encoding='utf-8') as f:
            concepts = json.load(f)
        with open('/Volumes/D/my_streamlit_app6/scripts/management_authors.json', 'r', encoding='utf-8') as f:
            auteurs = json.load(f)
        return concepts, auteurs
    except Exception as e:
        st.warning(f"Erreur lors du chargement des fichiers JSON: {e}")
        return {}, {}

def find_management_concepts(text, concepts):
    found_concepts = {concept: {'found': False, 'verbs': []} for concept in concepts.keys()}
    for concept, verbs in concepts.items():
        verb_forms = []
        for verb in verbs:
            verb_forms.extend([f"{verb}{ending}" for ending in ['', 'e', 'es', 'ons', 'ez', 'ent', 'ant']])
        pattern = re.compile(fr"\b(?:{'|'.join(verb_forms)})\w*\b|\b(?:l')?{concept}\b", re.IGNORECASE)
        matches = pattern.findall(text)
        if matches:
            found_concepts[concept]['found'] = True
            found_concepts[concept]['verbs'].extend(matches)
    return found_concepts

def find_management_authors(text, auteurs):
    found_authors = {author: False for author in auteurs.keys()}
    for author, variations in auteurs.items():
        pattern = re.compile(fr"\b(?:{'|'.join(variations)})\b", re.IGNORECASE)
        if pattern.search(text):
            found_authors[author] = True
    return found_authors

def print_missing_concepts(prof_concepts, etudiant_concepts):
    missing_concepts = [concept for concept, data in prof_concepts.items() if data['found'] and not etudiant_concepts.get(concept, {'found': False})['found']]
    st.write("Concepts présents dans la réponse du professeur:")
    for concept, data in prof_concepts.items():
        if data['found']:
            st.write(f"- {concept}")
    st.write("Concepts présents dans la réponse de l'étudiant:")
    for concept, data in etudiant_concepts.items():
        if data['found']:
            st.write(f"- {concept}")
    if missing_concepts:
        st.warning("Concepts manquants dans votre réponse:")
        for concept in missing_concepts:
            st.warning(f"- {concept}")
    return missing_concepts

def print_missing_authors(prof_authors, etudiant_authors):
    missing_authors = [author for author, found in prof_authors.items() if found and not etudiant_authors[author]]
    if missing_authors:
        st.warning("Auteurs manquants dans votre réponse :")
        for author in missing_authors:
            st.warning(f"- {author}")

def coherence_sbert(sentences, sbert_model):
    """
    Calcule la cohérence locale d'un texte comme la similarité moyenne des embeddings SBERT
    entre toutes les paires de phrases consécutives.
    Le score est continu, entre 0 (aucune cohérence) et 1 (cohérence parfaite).
    """
    if len(sentences) < 2:
        return 1.0
    embeddings = sbert_model.encode(sentences)
    sims = []
    for i in range(len(sentences) - 1):
        a, b = embeddings[i], embeddings[i+1]
        sim = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
        sims.append(sim)
    return float(np.mean(sims)) if sims else 1.0

def split_into_sentences(text):
    sentences = re.split(r'(?<=[.!?])\s*(?=\S)', text)
    return [s.strip() for s in sentences if s.strip()]

def evaluate_sentence_clarity(sentence, zero_shot_pipeline):
    candidate_labels = ["claire", "confuse"]
    result = zero_shot_pipeline(sentence, candidate_labels)
    return result["scores"][result["labels"].index("claire")]

def analyze_clarity_and_provide_feedback(text, zero_shot):
    unclear_sentences = []
    clarity_scores = []
    sentences = split_into_sentences(text)
    for sentence in sentences:
        clarity_score = evaluate_sentence_clarity(sentence, zero_shot)
        clarity_scores.append(clarity_score)
        if clarity_score < 0.5:
            unclear_sentences.append((sentence, clarity_score))
    if clarity_scores:
        average_clarity_score = sum(clarity_scores) / len(clarity_scores)
        st.info(f"Score global de clarté : {average_clarity_score:.2f}")
        if unclear_sentences:
            st.warning("Certaines parties de votre texte ne sont pas assez claires. Veuillez clarifier ces phrases :")
            for sentence, score in unclear_sentences:
                st.warning(f"Phrase : {sentence} (score : {score:.2f})")
    else:
        st.info("Aucune phrase trouvée dans le texte.")
        average_clarity_score = 0
    return average_clarity_score

def calculate_concept_score(prof_concepts, etudiant_concepts):
    total_prof_concepts = sum(1 for concept in prof_concepts.values() if concept['found'])
    if total_prof_concepts == 0:
        return 1.0
    total_matched_concepts = sum(1 for concept in prof_concepts if prof_concepts[concept]['found'] and etudiant_concepts.get(concept, {'found': False})['found'])
    return total_matched_concepts / total_prof_concepts

def calculate_author_score(prof_authors, etudiant_authors):
    num_prof_authors = sum(prof_authors.values())
    if num_prof_authors == 0:
        return 1.0
    num_etudiant_authors = sum(etudiant_authors.values())
    return min(num_etudiant_authors / num_prof_authors, 1.0)

def calculate_question_score(similarity_score, coherence_score, concept_score, author_score, clarity_score, points):
    weights = {
        'similarity': 0.6,
        'coherence': 0.05,
        'concept': 0.1,
        'author': 0.1,
        'clarity': 0.15
    }
    weighted_sum = (
        similarity_score * weights['similarity'] +
        coherence_score * weights['coherence'] +
        concept_score * weights['concept'] +
        author_score * weights['author'] +
        clarity_score * weights['clarity']
    )
    return weighted_sum * points

def evaluate_question(prof_content, etudiant_content, use_model, zero_shot, sbert_model, concepts, auteurs, points):
    st.markdown("### Analyse de la question :")
    similarity_score = calculate_mean_similarity(prof_content, etudiant_content, use_model)
    st.info(f"Score de similarité avec la question du professeur : {similarity_score:.2f}")
    sentences = split_into_sentences(etudiant_content)
    coherence_score = coherence_sbert(sentences, sbert_model)
    st.info(f"Score de cohérence (SBERT) : {coherence_score:.2f}")
    prof_concepts = find_management_concepts(prof_content, concepts)
    etudiant_concepts = find_management_concepts(etudiant_content, concepts)
    print_missing_concepts(prof_concepts, etudiant_concepts)
    concept_score = calculate_concept_score(prof_concepts, etudiant_concepts)
    st.info(f"Score des concepts : {concept_score:.2f}")
    prof_authors = find_management_authors(prof_content, auteurs)
    etudiant_authors = find_management_authors(etudiant_content, auteurs)
    print_missing_authors(prof_authors, etudiant_authors)
    author_score = calculate_author_score(prof_authors, etudiant_authors)
    st.info(f"Score des auteurs : {author_score:.2f}")
    clarity_score = analyze_clarity_and_provide_feedback(etudiant_content, zero_shot)
    question_score = calculate_question_score(
        similarity_score, coherence_score, concept_score,
        author_score, clarity_score, points
    )
    st.success(f"Note pour cette question : {question_score:.2f}/{points}")
    return {
        'similarity_score': similarity_score,
        'coherence_score': coherence_score,
        'concept_score': concept_score,
        'author_score': author_score,
        'clarity_score': clarity_score,
        'question_score': question_score
    }

def calculate_mean_scores(global_scores):
    if not global_scores:
        return {key: 0 for key in global_scores[0].keys()}
    mean_scores = {}
    for key in global_scores[0].keys():
        mean_scores[key] = np.mean([score[key] for score in global_scores])
    return mean_scores

def provide_general_feedback(mean_scores):
    st.markdown("## FEEDBACK GÉNÉRAL ET RECOMMANDATIONS")
    st.markdown("#### Scores moyens par critère :")
    st.info(f"- Similarité : {mean_scores['similarity_score']:.2f}")
    st.info(f"- Cohérence : {mean_scores['coherence_score']:.2f}")
    st.info(f"- Concepts : {mean_scores['concept_score']:.2f}")
    st.info(f"- Auteurs : {mean_scores['author_score']:.2f}")
    st.info(f"- Clarté : {mean_scores['clarity_score']:.2f}")

def main(user_email, selected_file):
    etudiant_pdf_path = "ben/Etudiant.pdf"
    prof_pdf_path = "ben/prof.pdf"
    if not initial_checks(etudiant_pdf_path, prof_pdf_path):
        st.stop()
    use_model, zero_shot, sbert_model = load_all_models()
    concepts, auteurs = load_concepts_and_authors()
    etudiant_text = extract_text_from_pdf(etudiant_pdf_path)
    prof_text = extract_text_from_pdf(prof_pdf_path)
    etudiant_questions = split_into_questions(etudiant_text)
    prof_questions = split_into_questions(prof_text)
    global_scores = []
    question_scores = {}
    total_points = sum(q['points'] for q in prof_questions.values())
    st.markdown("# DÉBUT DE L'ANALYSE")
    for q_key, q_data in prof_questions.items():
        st.markdown(f"---\n#### Analyse de la question {q_key} ({q_data['points']} points)")
        etudiant_content = etudiant_questions.get(q_key, {"text": ""})['text']
        if not etudiant_content:
            st.warning("-> Réponse manquante pour cette question")
            continue
        scores = evaluate_question(
            q_data['text'], etudiant_content,
            use_model, zero_shot, sbert_model, concepts, auteurs, q_data['points']
        )
        global_scores.append(scores)
        question_scores[q_key] = scores['question_score']
    mean_scores = calculate_mean_scores(global_scores)
    total_score = sum(question_scores.values())
    final_grade = (total_score / total_points) * 20 if total_points > 0 else 0
    st.markdown("## RÉSULTATS FINAUX")
    st.success(f"Note totale : {total_score:.2f}/{total_points}")
    st.success(f"Note sur 20 : {final_grade:.2f}/20")
    provide_general_feedback(mean_scores)
    if final_grade > 16:
        st.success("Félicitations pour votre excellente note ! Vous pouvez maintenant consulter le corrigé du professeur.")
        corrige_path = 'ben/prof.pdf'
        if os.path.exists(corrige_path):
            st.markdown(f"[Télécharger le corrigé du professeur]({corrige_path})")
        else:
            st.warning("Le fichier du corrigé n'a pas été trouvé.")
    else:
        st.warning("Pour consulter le corrigé du professeur, vous devez obtenir une note supérieure à 16/20. Continuez à vous entraîner!")

def code3(user_email, selected_file):
    main(user_email, selected_file)
