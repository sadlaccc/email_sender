import io
import time
import os
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
st.markdown("Upload your recipient list and send personalized bulk emails.")

# ------------------- Sidebar -------------------
with st.sidebar:
    st.header("SMTP Settings")
    smtp_server = st.text_input("SMTP Server", value="smtp.gmail.com", help="Example: smtp.gmail.com, smtp.office365.com")
    smtp_port = st.number_input("SMTP Port", value=587, min_value=1, max_value=65535)
    smtp_user = st.text_input("SMTP Username / Email")
    smtp_password = st.text_input("SMTP Password / App Password", type="password")

    st.markdown("---")
    st.header("AI Assistance")
    openai_api_key = st.text_input("OpenAI API Key", type="password")

# ------------------- File Upload & Smart Detection -------------------
uploaded_file = st.file_uploader("Upload recipients file (CSV or Excel)", type=["csv", "txt", "xls", "xlsx"])

recipients_df: Optional[pd.DataFrame] = None

if uploaded_file:
    try:
        file_ext = uploaded_file.name.lower().split(".")[-1]
        raw_data = uploaded_file.read()

        if file_ext in ["csv", "txt"]:
            try:
                recipients_df = pd.read_csv(io.StringIO(raw_data.decode("utf-8")))
            except UnicodeDecodeError:
                recipients_df = pd.read_csv(io.StringIO(raw_data.decode("latin-1")))
        else:
            try:
                recipients_df = pd.read_excel(io.BytesIO(raw_data))
            except ImportError:
                st.error("❌ Missing openpyxl. Run: `pip install openpyxl`")
                st.stop()

        # Normalize & detect email column
        original_cols = recipients_df.columns.tolist()
        recipients_df.columns = [str(col).strip().lower() for col in original_cols]

        email_candidates = ["email", "emails", "email address", "email_address", "mail", "to", "recipient"]
        email_col = next((col for col in recipients_df.columns if any(c in col for c in email_candidates)), None)

        if not email_col and len(recipients_df) > 0:
            for col in recipients_df.columns:
                if recipients_df[col].astype(str).str.contains("@").any():
                    email_col = col
                    break

        if email_col:
            recipients_df = recipients_df.rename(columns={email_col: "email"})
            st.success(f"✅ Using **{email_col}** as email column")
        else:
            st.warning("Could not detect email column.")
            selected = st.selectbox("Select email column:", original_cols)
            if st.button("Confirm"):
                recipients_df = recipients_df.rename(columns={str(selected).lower(): "email"})
                st.rerun()

        st.success(f"✅ Loaded **{len(recipients_df)}** recipients")

    except Exception as e:
        st.error(f"Failed to read file: {e}")

# ------------------- Main UI -------------------
col1, col2 = st.columns([3, 1])

with col1:
    subject = st.text_input("📧 Email Subject", placeholder="Special Offer for You!")

    use_ai = st.checkbox("✨ Use AI to generate email body", value=False)

    if use_ai and openai_available:
        ai_prompt = st.text_area("AI Instructions", height=100, 
            value="Write a friendly professional email with clear call to action.")
        if st.button("Generate Draft with AI"):
            # AI logic here (same as before)
            pass

    if "body" not in st.session_state:
        st.session_state.body = "Hello {name},\n\nThis is a test email.\n\nBest regards,"

    body = st.text_area("📝 Email Body (use {name} for personalization)", 
                       value=st.session_state.body, height=280, key="body")

    c1, c2, c3 = st.columns(3)
    with c1:
        dry_run = st.checkbox("Dry Run (Preview Only)", value=True)
    with c2:
        delay = st.slider("Delay between emails (sec)", 0, 5, 1)

    if st.button("🚀 Send Emails", type="primary", use_container_width=True):
        if recipients_df is None or "email" not in recipients_df.columns:
            st.error("Please upload file and ensure email column is selected.")
        elif not smtp_user or not smtp_password:
            st.error("SMTP credentials required.")
        elif not subject.strip() or not body.strip():
            st.error("Subject and body required.")
        else:
            valid_df = recipients_df[recipients_df["email"].astype(str).str.contains("@", na=False)].copy()

            progress_bar = st.progress(0)
            status_text = st.empty()

            sent_count = 0
            failed: List[Tuple[str, str]] = []

            try:
                with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as smtp:
                    smtp.ehlo()
                    if smtp_port == 587:
                        smtp.starttls()
                        smtp.ehlo()
                    smtp.login(smtp_user, smtp_password)

                    for idx, row in valid_df.iterrows():
                        recipient = str(row["email"]).strip()
                        name = str(row.get("name", "")).strip() or "there"

                        personalized = body.replace("{name}", name)

                        msg = EmailMessage()
                        msg["From"] = smtp_user
                        msg["To"] = recipient
                        msg["Subject"] = subject
                        msg.set_content(personalized)

                        try:
                            if not dry_run:
                                smtp.send_message(msg)
                            sent_count += 1
                        except Exception as send_err:
                            failed.append((recipient, str(send_err)))

                        progress_bar.progress((idx + 1) / len(valid_df))
                        status_text.text(f"Processing {idx+1}/{len(valid_df)} → {recipient}")

                        if delay > 0:
                            time.sleep(delay)

            except Exception as conn_err:
                st.error(f"**SMTP Connection Failed**: {conn_err}")
                st.info("""
                **Troubleshooting tips:**
                - Check that the **SMTP Server** is correct (e.g. `smtp.gmail.com`)
                - Make sure you have internet connection
                - For Gmail: Use App Password (not your normal password)
                - Try port 587 (TLS) or 465 (SSL)
                """)
                st.stop()

            # Final results
            st.success(f"✅ Successfully sent: **{sent_count}** emails")
            if failed:
                st.warning(f"⚠️ Failed: {len(failed)} emails")
                with st.expander("View Failures"):
                    for email, err in failed[:20]:
                        st.write(f"{email} → {err}")

with col2:
    if recipients_df is not None:
        st.metric("Total Recipients", len(recipients_df))
        st.dataframe(recipients_df.head(6), use_container_width=True)

    st.markdown("### Common SMTP Servers")
    st.markdown("""
    - **Gmail**: `smtp.gmail.com` (Port 587)
    - **Outlook / Office365**: `smtp.office365.com` (Port 587)
    - **Yahoo**: `smtp.mail.yahoo.com`
    """)
