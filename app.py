import io
import time
import socket
import smtplib
from email.message import EmailMessage
from typing import List, Tuple, Optional

import pandas as pd
import streamlit as st

try:
    from openai import OpenAI
    openai_available = True
except ImportError:
    openai_available = False

st.set_page_config(page_title="Bulk Email Sender", page_icon="✉️", layout="wide")

st.title("✉️ Bulk Email Sender - Any SMTP Provider")

# ================== SIDEBAR ==================
with st.sidebar:
    st.header("SMTP Configuration")
    
    provider = st.selectbox(
        "Select Provider", 
        ["Custom", "Gmail", "Outlook", "Yahoo", "Zoho"],
        index=0
    )
    
    presets = {
        "Gmail": ("smtp.gmail.com", 587),
        "Outlook": ("smtp.office365.com", 587),
        "Yahoo": ("smtp.mail.yahoo.com", 587),
        "Zoho": ("smtp.zoho.com", 587),
    }
    
    default_server, default_port = presets.get(provider, ("smtp.yourdomain.com", 587))

    smtp_server = st.text_input("SMTP Server", value=default_server, key="smtp_server")
    smtp_port = st.number_input("Port", value=default_port, min_value=1, max_value=65535, key="smtp_port")
    
    smtp_user = st.text_input("Email Address", placeholder="you@yourdomain.com", key="smtp_user")
    smtp_password = st.text_input("Password / App Password", type="password", key="smtp_password")

    st.markdown("---")
    st.info("**Tip**: Use App Password for Gmail")

# ================== FILE UPLOAD ==================
uploaded_file = st.file_uploader("Upload recipients file (CSV or Excel)", type=["csv", "txt", "xls", "xlsx"], key="file_uploader")

recipients_df: Optional[pd.DataFrame] = None

if uploaded_file:
    try:
        if uploaded_file.name.lower().endswith(('.csv', '.txt')):
            recipients_df = pd.read_csv(uploaded_file)
        else:
            recipients_df = pd.read_excel(uploaded_file)

        recipients_df.columns = [str(col).strip().lower() for col in recipients_df.columns]

        # Smart email column detection
        email_col = next((col for col in recipients_df.columns if any(x in col for x in ["email", "mail", "to", "recipient"])), None)
        
        if not email_col and len(recipients_df) > 0:
            for col in recipients_df.columns:
                if recipients_df[col].astype(str).str.contains("@").any():
                    email_col = col
                    break

        if email_col:
            recipients_df = recipients_df.rename(columns={email_col: "email"})
            st.success(f"✅ Email column detected: **{email_col}**")
        else:
            selected = st.selectbox("Select email column:", recipients_df.columns, key="col_select")
            if st.button("Confirm Email Column"):
                recipients_df = recipients_df.rename(columns={selected: "email"})
                st.success(f"✅ Using **{selected}** as email column")
                st.rerun()

        st.success(f"✅ Loaded **{len(recipients_df)}** recipients")
        st.dataframe(recipients_df.head(5), use_container_width=True)

    except Exception as e:
        st.error(f"File error: {e}")

# ================== MAIN AREA ==================
col1, col2 = st.columns([3, 1])

with col1:
    subject = st.text_input("📧 Email Subject", placeholder="Special Offer Just for You!", key="subject")

    if "body" not in st.session_state:
        st.session_state.body = "Hello {name},\n\nThis is a personalized message.\n\nBest regards,"

    body = st.text_area("📝 Email Body (use {name} for personalization)", 
                       value=st.session_state.body, height=280, key="body")

    c1, c2, c3 = st.columns(3)
    with c1:
        dry_run = st.checkbox("🔍 Dry Run (Test Mode - No emails sent)", value=True, key="dry_run")
    with c2:
        delay = st.slider("Delay between emails (seconds)", 0, 5, 1, key="delay")

    if st.button("🚀 Send Emails", type="primary", use_container_width=True):
        # Improved validation
        user_email = st.session_state.get("smtp_user", "").strip()
        user_pass = st.session_state.get("smtp_password", "").strip()

        if not user_email or not user_pass:
            st.error("❌ Email address and password are required.")
            st.info("Make sure you filled both fields in the sidebar.")
        elif recipients_df is None or "email" not in recipients_df.columns:
            st.error("❌ Please upload a file and configure the email column.")
        elif not subject.strip() or not body.strip():
            st.error("❌ Subject and email body are required.")
        else:
            # DNS check
            try:
                socket.gethostbyname(smtp_server)
            except Exception:
                st.error(f"❌ Cannot find server: **{smtp_server}**")
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
                    smtp.login(user_email, user_pass)

                    for idx, row in valid_df.iterrows():
                        recipient = str(row["email"]).strip()
                        name = str(row.get("name", "")).strip() or "there"

                        personalized = body.replace("{name}", name)

                        msg = EmailMessage()
                        msg["From"] = user_email
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
                        status_text.text(f"Processing {idx+1}/{len(valid_df)} → {recipient}")

                        if delay > 0:
                            time.sleep(delay)

            except Exception as e:
                st.error(f"SMTP Error: {e}")

            st.success(f"✅ Successfully sent: **{sent_count}** emails")
            if failed:
                st.warning(f"⚠️ Failed: {len(failed)} emails")
                with st.expander("View Failures"):
                    for email, err in failed[:20]:
                        st.write(f"{email}: {err}")

with col2:
    st.info("**Always start with Dry Run enabled**")
    if smtp_user:
        st.success("✅ Credentials detected")
