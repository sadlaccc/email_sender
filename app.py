import io
import time
import socket
import smtplib
from email.message import EmailMessage
from typing import Optional

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Bulk Email Sender", page_icon="✉️", layout="wide")

st.title("✉️ Smart Bulk Email Sender")
st.caption("AI Templates • Any SMTP Provider")

# ====================== SIDEBAR ======================
with st.sidebar:
    st.header("🔧 SMTP Configuration")
    
    smtp_server = st.text_input(
        "SMTP Server", 
        value="smtp.intellinksea.com",
        help="Common alternatives: mail.intellinksea.com, smtp.intellinksea.co.ke"
    )
    smtp_port = st.number_input("Port", value=587, min_value=1, max_value=65535)
    
    smtp_user = st.text_input("Email Address", placeholder="yourname@intellinksea.com")
    smtp_password = st.text_input("Password", type="password")

    st.markdown("---")
    if st.button("🔍 Test Server Connection"):
        try:
            ip = socket.gethostbyname(smtp_server)
            st.success(f"✅ Server resolved: {ip}")
        except Exception as e:
            st.error(f"❌ Cannot resolve: {smtp_server}")
            st.info("Try these alternatives:\n• `mail.intellinksea.com`\n• `smtp.intellinksea.co.ke`")

# ====================== TABS ======================
tab1, tab2, tab3 = st.tabs(["📋 Templates & AI", "📤 Recipients", "🚀 Send"])

recipients_df: Optional[pd.DataFrame] = None

# ====================== TAB 1: TEMPLATES + AI ======================
with tab1:
    st.subheader("Templates & AI Generator")

    # Template Management
    if "templates" not in st.session_state:
        st.session_state.templates = {
            "Welcome": "Hello {name},\n\nWelcome aboard! We're excited to work with you.",
            "Follow-up": "Hello {name},\n\nJust following up on my previous email.",
            "Promotion": "Hello {name},\n\nSpecial offer for you this month."
        }

    template_choice = st.selectbox("Load Template", options=list(st.session_state.templates.keys()))
    if st.button("Load"):
        st.session_state.body = st.session_state.templates[template_choice]

    # AI Section
    st.markdown("---")
    st.subheader("✨ Generate with AI")
    ai_prompt = st.text_area("What should the email say?", height=100)
    
    if st.button("Generate Email with AI"):
        st.info("AI feature coming soon — OpenAI key needed in sidebar (optional)")

    st.subheader("Email Content")
    subject = st.text_input("Subject", "Important Update from Intellinksea")
    body = st.text_area("Body (use {name} for personalization)", 
                       value=st.session_state.get("body", "Hello {name},\n\n..."), height=250)

# ====================== TAB 2: RECIPIENTS ======================
with tab2:
    uploaded_file = st.file_uploader("Upload CSV or Excel", type=["csv", "xlsx", "xls"])

    if uploaded_file:
        try:
            if uploaded_file.name.endswith('.csv'):
                recipients_df = pd.read_csv(uploaded_file)
            else:
                recipients_df = pd.read_excel(uploaded_file)

            recipients_df.columns = [str(c).strip().lower() for c in recipients_df.columns]

            st.success(f"Loaded {len(recipients_df)} rows")

            email_col = st.selectbox("Select Email Column", recipients_df.columns)
            if st.button("Confirm Email Column"):
                recipients_df = recipients_df.rename(columns={email_col: "email"})
                st.success("Email column confirmed!")
                st.dataframe(recipients_df.head(6))

        except Exception as e:
            st.error(f"File error: {e}")

# ====================== TAB 3: SEND ======================
with tab3:
    st.subheader("Send Campaign")
    dry_run = st.checkbox("Dry Run (Don't send real emails)", value=True)

    if st.button("🚀 Start Sending", type="primary", use_container_width=True):
        if not smtp_user or not smtp_password:
            st.error("Please enter email and password in sidebar")
        elif recipients_df is None or "email" not in recipients_df.columns:
            st.error("Please upload recipients and confirm email column")
        else:
            server_host = smtp_server.strip()

            # DNS Test
            try:
                socket.gethostbyname(server_host)
                st.success(f"✅ Server {server_host} is reachable")
            except Exception:
                st.error(f"❌ Cannot resolve **{server_host}**")
                st.warning("This is likely an internal server. You may need to:")
                st.markdown("""
                1. Connect to company **VPN**
                2. Use the correct internal hostname
                3. Ask your IT team for the exact SMTP settings
                """)
                st.stop()

            # Sending Logic
            valid_df = recipients_df[recipients_df["email"].astype(str).str.contains("@")].copy()
            progress_bar = st.progress(0)
            status = st.empty()

            sent = 0
            failed = []

            try:
                with smtplib.SMTP(server_host, smtp_port, timeout=30) as smtp:
                    smtp.ehlo()
                    if smtp_port == 587:
                        smtp.starttls()
                        smtp.ehlo()
                    smtp.login(smtp_user, smtp_password)

                    for i, row in valid_df.iterrows():
                        recipient = str(row["email"]).strip()
                        name = str(row.get("name", "")).strip() or "there"

                        text = body.replace("{name}", name)

                        msg = EmailMessage()
                        msg["From"] = smtp_user
                        msg["To"] = recipient
                        msg["Subject"] = subject
                        msg.set_content(text)

                        try:
                            if not dry_run:
                                smtp.send_message(msg)
                            sent += 1
                        except Exception as err:
                            failed.append((recipient, str(err)))

                        progress_bar.progress((i + 1) / len(valid_df))
                        status.text(f"Sending {i+1}/{len(valid_df)} → {recipient}")

            except Exception as e:
                st.error(f"SMTP Error: {e}")

            st.success(f"Done! Sent: {sent} emails")
            if failed:
                st.warning(f"Failed: {len(failed)}")
