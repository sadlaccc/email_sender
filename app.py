import io
import time
import socket
import smtplib
from email.message import EmailMessage
from typing import Optional, List, Tuple

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Bulk Email Sender", page_icon="✉️", layout="wide")

st.title("✉️ Bulk Email Sender")
st.markdown("**Professional Bulk Email Tool** — Now with better delivery diagnostics")

# ====================== SIDEBAR ======================
with st.sidebar:
    st.header("SMTP Configuration")
    smtp_server = st.text_input("SMTP Server", value="smtp.intellinksea.com", key="smtp_server")
    smtp_port = st.number_input("Port", value=587, min_value=1, max_value=65535, key="smtp_port")
    
    smtp_user = st.text_input("Email Address", placeholder="you@intellinksea.com", key="smtp_user")
    smtp_password = st.text_input("Password", type="password", key="smtp_password")

    st.markdown("---")
    test_email = st.text_input("Test Email Address (optional)", placeholder="yourpersonal@gmail.com")

# ====================== MAIN LAYOUT ======================
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📤 1. Recipients")
    uploaded_file = st.file_uploader("Upload CSV or Excel", type=["csv", "xlsx", "xls"])

    recipients_df: Optional[pd.DataFrame] = None

    if uploaded_file:
        try:
            if uploaded_file.name.lower().endswith('.csv'):
                recipients_df = pd.read_csv(uploaded_file)
            else:
                recipients_df = pd.read_excel(uploaded_file)

            recipients_df.columns = [str(col).strip().lower() for col in recipients_df.columns]

            email_col = st.selectbox("Select Email Column", recipients_df.columns)
            if st.button("✅ Confirm Email Column", type="primary"):
                recipients_df = recipients_df.rename(columns={email_col: "email"})
                st.success("Email column confirmed")
                st.dataframe(recipients_df.head(6), use_container_width=True)
        except Exception as e:
            st.error(f"File Error: {e}")

    st.markdown("---")
    st.subheader("✉️ 2. Email Content")
    subject = st.text_input("Subject", "Important Update from Intellinksea")
    
    body = st.text_area(
        "Email Body (use {name} for personalization)", 
        height=250,
        value="Hello {name},\n\nThis is a test message.\n\nBest regards,\nTeam"
    )

    st.markdown("---")
    st.subheader("🚀 3. Send Settings")
    
    col_a, col_b = st.columns(2)
    with col_a:
        dry_run = st.checkbox("🔍 Dry Run (Don't actually send)", value=True)
    with col_b:
        delay = st.slider("Delay (seconds)", 0, 3, 1)

    if st.button("🚀 SEND EMAILS", type="primary", use_container_width=True):
        if not smtp_user or not smtp_password:
            st.error("Please fill SMTP credentials in sidebar")
        elif recipients_df is None or "email" not in recipients_df.columns:
            st.error("Please upload recipients and confirm email column")
        elif not subject or not body:
            st.error("Subject and body required")
        else:
            valid_df = recipients_df[recipients_df["email"].astype(str).str.contains("@", na=False)].copy()

            progress_bar = st.progress(0)
            status_text = st.empty()
            
            sent_count = 0
            failed = []

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

                        personalized_body = body.replace("{name}", name)

                        msg = EmailMessage()
                        msg["From"] = f"Intellinksea Team <{smtp_user}>"
                        msg["To"] = recipient
                        msg["Subject"] = subject
                        msg.set_content(personalized_body)

                        try:
                            if not dry_run:
                                smtp.send_message(msg)
                            sent_count += 1
                            status = "✅ Sent"
                        except Exception as e:
                            failed.append((recipient, str(e)))
                            status = "❌ Failed"

                        progress_bar.progress((idx + 1) / len(valid_df))
                        status_text.text(f"{status} → {recipient}")

                        if delay > 0:
                            time.sleep(delay)

            except Exception as e:
                st.error(f"Connection Error: {e}")

            # ====================== FINAL RESULT ======================
            st.success(f"""
            **Campaign Finished!**

            ✅ Successfully Sent: **{sent_count}** emails  
            ⚠️ Failed: **{len(failed)}** emails
            """)

            if dry_run:
                st.warning("🔍 **Dry Run Mode** was enabled — No emails were actually sent.")

            if failed:
                st.error("Some emails failed")
                failed_df = pd.DataFrame(failed, columns=["Email", "Reason"])
                st.dataframe(failed_df, use_container_width=True)

            # Test Email Option
            if st.button("📧 Send Test Email to Yourself"):
                if test_email:
                    try:
                        with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as smtp:
                            smtp.ehlo()
                            if smtp_port == 587:
                                smtp.starttls()
                                smtp.ehlo()
                            smtp.login(smtp_user, smtp_password)

                            msg = EmailMessage()
                            msg["From"] = f"Intellinksea Team <{smtp_user}>"
                            msg["To"] = test_email
                            msg["Subject"] = "Test Email - Bulk Sender"
                            msg.set_content("This is a test email from the Bulk Email Sender app.")
                            smtp.send_message(msg)
                        st.success(f"Test email sent to {test_email}")
                    except Exception as e:
                        st.error(f"Test email failed: {e}")
                else:
                    st.warning("Enter a test email in the sidebar")

with col2:
    st.subheader("Campaign Summary")
    if recipients_df is not None and "email" in recipients_df.columns:
        st.metric("Total Recipients", len(recipients_df))
        st.metric("Valid Emails", len(recipients_df[recipients_df["email"].astype(str).str.contains("@")]))
    
    st.info("""
    **Why emails may not be delivered:**
    - Dry Run enabled
    - Emails going to Spam folder
    - Sender reputation issues
    - Check your inbox / spam folder
    """)
