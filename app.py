import io
import time
import socket
import smtplib
from email.message import EmailMessage
from typing import List, Tuple, Optional

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Bulk Email Sender", page_icon="✉️", layout="wide")

st.title("✉️ Bulk Email Sender")
st.markdown(f"**SMTP Server:** `smtp.intellinksea.com`")

# ================== SIDEBAR ==================
with st.sidebar:
    st.header("SMTP Configuration")
    
    smtp_server = st.text_input("SMTP Server", value="smtp.intellinksea.com", key="smtp_server")
    smtp_port = st.number_input("SMTP Port", value=587, min_value=1, max_value=65535, key="smtp_port")
    
    smtp_user = st.text_input("Email Address / Username", placeholder="yourname@intellinksea.com", key="smtp_user")
    smtp_password = st.text_input("Password", type="password", key="smtp_password")

    st.info("""
    **Important for intellinksea.com**
    - Use your full email address as username
    - Make sure your password is correct
    - Port 587 (TLS) is recommended
    """)

# ================== FILE UPLOAD ==================
uploaded_file = st.file_uploader("Upload recipients file (CSV or Excel)", type=["csv", "txt", "xls", "xlsx"], key="file")

recipients_df: Optional[pd.DataFrame] = None

if uploaded_file:
    try:
        if uploaded_file.name.lower().endswith(('.csv', '.txt')):
            recipients_df = pd.read_csv(uploaded_file)
        else:
            recipients_df = pd.read_excel(uploaded_file)

        # Normalize columns
        recipients_df.columns = [str(col).strip().lower() for col in recipients_df.columns]

        # Smart email column detection
        email_col = next((col for col in recipients_df.columns 
                         if any(x in col for x in ["email", "mail", "to", "recipient"])), None)
        
        if not email_col and len(recipients_df) > 0:
            for col in recipients_df.columns:
                if recipients_df[col].astype(str).str.contains("@").any():
                    email_col = col
                    break

        if email_col:
            recipients_df = recipients_df.rename(columns={email_col: "email"})
            st.success(f"✅ Email column detected: **{email_col}**")
        else:
            st.warning("Could not auto-detect email column.")
            selected = st.selectbox("Select the email column:", recipients_df.columns, key="select_col")
            if st.button("✅ Confirm Email Column"):
                recipients_df = recipients_df.rename(columns={selected: "email"})
                st.success(f"Using **{selected}** as email column")
                st.rerun()

        st.success(f"✅ Loaded **{len(recipients_df)}** recipients")
        st.dataframe(recipients_df.head(6), use_container_width=True)

    except Exception as e:
        st.error(f"File error: {e}")

# ================== MAIN AREA ==================
col1, col2 = st.columns([3, 1])

with col1:
    subject = st.text_input("📧 Email Subject", placeholder="Important Update", key="subject")

    if "body" not in st.session_state:
        st.session_state.body = "Hello {name},\n\nThis is a test email from Intellinksea.\n\nBest regards,"

    body = st.text_area("📝 Email Body (use {name} for personalization)", 
                       value=st.session_state.body, height=280, key="body")

    c1, c2, _ = st.columns(3)
    with c1:
        dry_run = st.checkbox("🔍 Dry Run (Test Mode)", value=True, key="dry_run")
    with c2:
        delay = st.slider("Delay between emails (sec)", 0, 5, 1, key="delay")

    if st.button("🚀 Send Emails", type="primary", use_container_width=True):
        user = st.session_state.get("smtp_user", "").strip()
        password = st.session_state.get("smtp_password", "").strip()

        if not user or not password:
            st.error("❌ Please enter your Email Address and Password in the sidebar.")
        elif recipients_df is None or "email" not in recipients_df.columns:
            st.error("❌ Please upload file and confirm email column.")
        elif not subject.strip() or not body.strip():
            st.error("❌ Subject and Body are required.")
        else:
            # DNS Check
            try:
                socket.gethostbyname(smtp_server)
            except Exception:
                st.error(f"❌ Cannot resolve server: {smtp_server}")
                st.stop()

            valid_df = recipients_df[recipients_df["email"].astype(str).str.contains("@", na=False)].copy()

            progress_bar = st.progress(0)
            status_text = st.empty()

            sent_count = 0
            failed = []

            try:
                with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as smtp:
                    smtp.ehlo()
                    if smtp_port in (587, 25):
                        smtp.starttls()
                        smtp.ehlo()
                    smtp.login(user, password)

                    for idx, row in valid_df.iterrows():
                        recipient = str(row["email"]).strip()
                        name = str(row.get("name", "")).strip() or "there"

                        personalized = body.replace("{name}", name)

                        msg = EmailMessage()
                        msg["From"] = user
                        msg["To"] = recipient
                        msg["Subject"] = subject
                        msg.set_content(personalized)

                        try:
                            if not dry_run:
                                smtp.send_message(msg)
                            sent_count += 1
                        except Exception as e:
                            failed.append((recipient, str(e)))

                        progress_bar.progress((idx + 1) / len(valid_df))
                        status_text.text(f"→ {recipient}")

                        if delay > 0:
                            time.sleep(delay)

            except Exception as e:
                st.error(f"SMTP Error: {e}")

            st.success(f"✅ Sent **{sent_count}** emails successfully!")
            if failed:
                st.warning(f"⚠️ {len(failed)} emails failed")
                with st.expander("Show Failures"):
                    for email, err in failed:
                        st.write(f"{email} → {err}")

with col2:
    st.info("**Recommendation**: Keep Dry Run ON until you confirm everything works.")
