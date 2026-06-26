import io
import time
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

st.title("✉️ Bulk Email Sender")
st.markdown("Send personalized bulk emails using **any SMTP provider**")

# ================== SIDEBAR ==================
with st.sidebar:
    st.header("SMTP Configuration")
    
    # Provider presets
    provider = st.selectbox(
        "Email Provider",
        options=["Custom", "Gmail", "Outlook / Office365", "Yahoo", "Zoho"],
        index=0
    )
    
    if provider == "Gmail":
        default_server = "smtp.gmail.com"
        default_port = 587
    elif provider == "Outlook / Office365":
        default_server = "smtp.office365.com"
        default_port = 587
    elif provider == "Yahoo":
        default_server = "smtp.mail.yahoo.com"
        default_port = 587
    elif provider == "Zoho":
        default_server = "smtp.zoho.com"
        default_port = 587
    else:
        default_server = "smtp.yourdomain.com"
        default_port = 587

    smtp_server = st.text_input("SMTP Server", value=default_server)
    smtp_port = st.number_input("SMTP Port", value=default_port, min_value=1, max_value=65535)
    
    smtp_user = st.text_input("SMTP Username / Email Address")
    smtp_password = st.text_input("SMTP Password / App Password", type="password")

    st.markdown("---")
    if provider == "Gmail":
        st.info("**Gmail users**: Use an **App Password** (not your regular password)")
    elif provider == "Outlook / Office365":
        st.info("**Outlook users**: Use your normal password or app password if enabled")
    else:
        st.info("Check your email provider's documentation for correct SMTP settings")

# ================== FILE UPLOAD ==================
uploaded_file = st.file_uploader("Upload recipients file", type=["csv", "txt", "xls", "xlsx"])

recipients_df: Optional[pd.DataFrame] = None

if uploaded_file:
    try:
        if uploaded_file.name.lower().endswith(('.csv', '.txt')):
            recipients_df = pd.read_csv(uploaded_file)
        else:
            recipients_df = pd.read_excel(uploaded_file)

        # Smart column detection
        recipients_df.columns = [str(col).strip().lower() for col in recipients_df.columns]
        
        email_col = None
        for col in recipients_df.columns:
            if any(word in col for word in ["email", "mail", "to", "recipient"]):
                email_col = col
                break
        if not email_col and len(recipients_df) > 0:
            for col in recipients_df.columns:
                if recipients_df[col].astype(str).str.contains("@").any():
                    email_col = col
                    break

        if email_col:
            recipients_df = recipients_df.rename(columns={email_col: "email"})
            st.success(f"✅ Email column: **{email_col}**")
        else:
            st.error("Could not detect email column.")
            selected = st.selectbox("Select email column:", recipients_df.columns)
            if st.button("Confirm Column"):
                recipients_df = recipients_df.rename(columns={selected: "email"})
                st.rerun()

        st.success(f"✅ Loaded **{len(recipients_df)}** recipients")
        st.dataframe(recipients_df.head(5), use_container_width=True)

    except Exception as e:
        st.error(f"File reading error: {e}")

# ================== MAIN AREA ==================
col1, col2 = st.columns([3, 1])

with col1:
    subject = st.text_input("📧 Email Subject", placeholder="Special Offer for You!")

    use_ai = st.checkbox("✨ Use AI to generate email body", value=False)
    # (AI code can be added here if needed)

    if "body" not in st.session_state:
        st.session_state.body = "Hello {name},\n\nThis is a personalized email.\n\nBest regards,"

    body = st.text_area("📝 Email Body - Use {name} for personalization", 
                       value=st.session_state.body, height=280, key="body")

    c1, c2, c3 = st.columns(3)
    with c1:
        dry_run = st.checkbox("Dry Run (Test Mode)", value=True)
    with c2:
        delay = st.slider("Delay between emails (seconds)", 0, 5, 1)

    if st.button("🚀 Send Emails", type="primary", use_container_width=True):
        if recipients_df is None or "email" not in recipients_df.columns:
            st.error("Please upload file and configure email column.")
        elif not smtp_user or not smtp_password:
            st.error("SMTP Username and Password are required.")
        elif not subject.strip() or not body.strip():
            st.error("Subject and Body are required.")
        else:
            valid_df = recipients_df[recipients_df["email"].astype(str).str.contains("@", na=False)].copy()

            progress_bar = st.progress(0)
            status_text = st.empty()

            sent_count = 0
            failed = []

            try:
                with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as smtp:
                    smtp.ehlo()
                    if smtp_port in [587, 25]:
                        smtp.starttls()
                        smtp.ehlo()
                    smtp.login(smtp_user, smtp_password)

                    for idx, row in valid_df.iterrows():
                        recipient = str(row["email"]).strip()
                        name = str(row.get("name", "")).strip() or "there"

                        personalized_body = body.replace("{name}", name)

                        msg = EmailMessage()
                        msg["From"] = smtp_user
                        msg["To"] = recipient
                        msg["Subject"] = subject
                        msg.set_content(personalized_body)

                        try:
                            if not dry_run:
                                smtp.send_message(msg)
                            sent_count += 1
                        except Exception as e:
                            failed.append((recipient, str(e)))

                        progress_bar.progress((idx + 1) / len(valid_df))
                        status_text.text(f"Sending {idx+1}/{len(valid_df)} → {recipient}")

                        if delay > 0:
                            time.sleep(delay)

            except Exception as e:
                st.error(f"SMTP Connection Error: {e}")

            st.success(f"✅ Successfully sent: **{sent_count}** emails")
            if failed:
                st.warning(f"⚠️ Failed: {len(failed)} emails")
                with st.expander("View Failures"):
                    for email, err in failed[:15]:
                        st.write(f"• {email}: {err}")

with col2:
    st.markdown("### Supported Providers")
    st.markdown("""
    - **Gmail**
    - **Outlook / Office365**
    - **Yahoo Mail**
    - **Zoho Mail**
    - **Custom Domain** (any SMTP)
    """)
    
    st.info("**Tip**: Start with **Dry Run** enabled to test your settings safely.")
