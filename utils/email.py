import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import streamlit as st

def send_email(to_email, subject, message_html):
    """
    Envoie un email via les serveurs SMTP de Gmail.
    """
    
    # 1. Récupération des secrets depuis le fichier secrets.toml
    try:
        sender_email = st.secrets["gmail"]["user"]
        sender_password = st.secrets["gmail"]["password"]
    except Exception:
        st.error("❌ Erreur de configuration : Vérifiez votre fichier secrets.toml (section [gmail]).")
        return False

    # 2. Préparation du message
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = sender_email
    message["To"] = to_email

    # Ajout du contenu HTML
    part = MIMEText(message_html, "html")
    message.attach(part)

    # 3. Connexion sécurisée à Gmail et envoi
    try:
        # Création du contexte de sécurité SSL
        context = ssl.create_default_context()
        
        # Connexion au serveur SMTP de Gmail (Port 465)
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(sender_email, sender_password)
            server.sendmail(
                sender_email, to_email, message.as_string()
            )
            
        print(f"✅ Email envoyé avec succès à {to_email}")
        return True

    except smtplib.SMTPAuthenticationError:
        st.error("❌ Erreur d'authentification Gmail. Vérifiez que le 'Mot de passe d'application' est correct.")
        return False
    except Exception as e:
        st.error(f"❌ Erreur technique lors de l'envoi : {e}")
        return False