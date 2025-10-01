import streamlit as st
import pandas as pd
from datetime import datetime, date
import re, os, io
from ftplib import FTP, error_perm

st.set_page_config(page_title="Iscrizione Percorsi Formativi", page_icon="📚", layout="centered")

# ---------------------- Utility ----------------------
def valida_cf(cf: str) -> bool:
    cf = cf.strip().upper()
    return bool(re.fullmatch(r"[A-Z0-9]{16}", cf))

def ftp_connect():
    host = st.secrets["FTP_HOST"]
    user = st.secrets["FTP_USER"]
    pwd  = st.secrets["FTP_PASS"]
    ftp = FTP(host, timeout=25)
    ftp.login(user=user, passwd=pwd)
    return ftp

def ftp_cd_mkdirs(ftp: FTP, remote_dir: str):
    # Cambia directory creando quelle mancanti (best effort)
    remote_dir = remote_dir.strip("/")
    if not remote_dir:
        return
    parts = remote_dir.split("/")
    path_so_far = ""
    for p in parts:
        path_so_far = f"{path_so_far}/{p}" if path_so_far else p
        try:
            ftp.cwd(path_so_far)
        except error_perm:
            try:
                ftp.mkd(path_so_far)
            except Exception:
                pass
            ftp.cwd(path_so_far)

def ftp_download_file(ftp: FTP, remote_path: str) -> bytes | None:
    # Restituisce i bytes del file remoto, oppure None se non esiste
    bio = io.BytesIO()
    try:
        ftp.retrbinary(f"RETR {remote_path}", bio.write)
        return bio.getvalue()
    except error_perm as e:
        if "550" in str(e):
            return None
        raise

def ftp_upload_file(ftp: FTP, remote_path: str, data_bytes: bytes):
    bio = io.BytesIO(data_bytes)
    ftp.storbinary(f"STOR {remote_path}", bio)

def append_row_to_csv_bytes(existing_bytes: bytes | None, row: dict) -> bytes:
    new_df = pd.DataFrame([row])
    if existing_bytes:
        try:
            old_df = pd.read_csv(io.BytesIO(existing_bytes))
            df = pd.concat([old_df, new_df], ignore_index=True)
        except Exception:
            # Se il file remoto è corrotto o vuoto, riparti dal nuovo
            df = new_df
    else:
        df = new_df
    out = io.BytesIO()
    df.to_csv(out, index=False)
    return out.getvalue()

def standardizza_scela(x: str) -> str:
    # rimuove doppie spaziature, uniforma
    return " ".join(x.strip().split())

# ---------------------- UI ----------------------
st.title("📚 Iscrizione ai Corsi di Formazione For.Te.")
st.write("Compila il form per iscriverti ai moduli formativi. I moduli devono essere completati **entro il 30/11/2025**.")

with st.sidebar:
    st.header("ℹ️ Info rapide")
    st.markdown("""
- Modalità: **Aula** e **FAD (videoconferenza)**
- Scadenza: **30/11/2025**
- Dopo l'invio, i dati sono archiviati **in modo centralizzato** sul nostro server.
""")

st.subheader("👤 Dati del partecipante")
c1, c2 = st.columns(2)
with c1:
    nome = st.text_input("Nome", max_chars=60)
    data_nascita = st.date_input("Data di nascita", value=date(1990,1,1), format="DD/MM/YYYY")
    codice_fiscale = st.text_input("Codice Fiscale (16 caratteri)", max_chars=16).upper()
with c2:
    cognome = st.text_input("Cognome", max_chars=60)
    luogo_nascita = st.text_input("Luogo di nascita", max_chars=80)
    azienda = st.text_input("Farmacia/Azienda", max_chars=120)

email = st.text_input("Email", max_chars=120, placeholder="nome@dominio.it")

st.markdown("---")
st.subheader("🗓️ Selezione date dei moduli")

mod1 = st.radio("**Modulo 1 – Giuridico Normativo**",
                ["16 Ottobre (16:00-18:00)",
                 "17 Ottobre (16:00-18:00)",
                 "23 Ottobre (16:00-18:00)"],
                index=0)

mod2a = st.radio("**Modulo 2 – Rischi Specifici DVR (Parte 1)**",
                 ["24 Ottobre (16:00-18:00)",
                  "30 Ottobre (16:00-18:00)",
                  "6 Novembre (16:00-18:00)"],
                 index=0)

mod2b = st.radio("**Modulo 2 – Rischi Specifici DVR (Parte 2)**",
                 ["13 Novembre (16:00-18:00)",
                  "14 Novembre (16:00-18:00)",
                  "20 Novembre (16:00-18:00)"],
                 index=0)

st.markdown("---")
st.subheader("🔐 Informativa sintetica & Consenso")
st.markdown("""
**Titolare del trattamento**: [Il tuo nome/Studio].  
**Finalità**: gestione iscrizioni, erogazione corsi, emissione attestati, adempimenti normativi (D.Lgs. 81/08, Accordi Stato-Regioni).  
**Base giuridica**: adempimenti di legge/obblighi formativi.  
**Conservazione**: per il tempo necessario a dimostrare la formazione svolta e in conformità alle norme vigenti.  
**Diritti**: accesso, rettifica, limitazione, ecc. (artt. 15-22 GDPR).  
**Contatti**: [tua email].
""")
consenso = st.checkbox("✅ Dichiaro di aver letto l'informativa e acconsento al trattamento per le finalità indicate.")

if st.button("📩 Invia Iscrizione"):
    # Validazioni
    missing = []
    if not nome: missing.append("Nome")
    if not cognome: missing.append("Cognome")
    if not luogo_nascita: missing.append("Luogo di nascita")
    if not azienda: missing.append("Farmacia/Azienda")
    if not email or "@" not in email: missing.append("Email valida")
    if not codice_fiscale or not valida_cf(codice_fiscale): missing.append("Codice Fiscale (16 caratteri)")

    if missing:
        st.error("⚠️ Compila correttamente: " + ", ".join(missing))
    elif not consenso:
        st.error("⚠️ Devi acconsentire al trattamento dei dati per procedere.")
    else:
        # Prepara record
        payload = {
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Nome": standardizza_scela(nome),
            "Cognome": standardizza_scela(cognome),
            "Data_nascita": data_nascita.strftime("%Y-%m-%d"),
            "Luogo_nascita": standardizza_scela(luogo_nascita),
            "Codice_fiscale": codice_fiscale.strip().upper(),
            "Azienda": standardizza_scela(azienda),
            "Email": email.strip(),
            "Modulo_1": mod1,
            "Modulo_2_Parte_1": mod2a,
            "Modulo_2_Parte_2": mod2b,
            "Consenso": "SI"
        }

        # Parametri remoti da st.secrets
        REMOTE_DIR  = "httpdocs/IA/Corsi/IscrizioniPercorsiFormativi"
        REMOTE_FILE = "iscrizioni.csv"
        REMOTE_PATH = f"{REMOTE_DIR}/{REMOTE_FILE}"

        try:
            ftp = ftp_connect()
            # Entra/crea directory
            ftp_cd_mkdirs(ftp, REMOTE_DIR)

            # Scarica CSV esistente (se c'è)
            existing = None
            try:
                existing = ftp_download_file(ftp, REMOTE_FILE)
            except Exception:
                # Prova con path assoluto come fallback
                existing = ftp_download_file(ftp, REMOTE_PATH)

            # Accoda riga e ottieni bytes aggiornati
            updated_bytes = append_row_to_csv_bytes(existing, payload)

            # Carica file aggiornato (preferendo nome semplice: siamo già nella dir giusta)
            try:
                ftp_upload_file(ftp, REMOTE_FILE, updated_bytes)
            except Exception:
                # Fallback con percorso completo
                ftp_upload_file(ftp, REMOTE_PATH, updated_bytes)

            ftp.quit()
            st.success("✅ Iscrizione inviata e archiviata correttamente sul server.")
            st.info("Riceverai conferma dalla segreteria con i dettagli di accesso.")
        except Exception as e:
            st.error(f"❌ Errore durante l'archiviazione su server: {e}")
            st.caption("Suggerimento: verifica host/utenza/password FTP e i permessi della cartella remota.")

st.markdown("---")

st.caption("I dati sensibili sono gestiti nel rispetto del GDPR. Archiviazione su server di proprietà (4step.it/Misterdomain) nella directory indicata. Accesso ristretto al Titolare/Responsabile.")
