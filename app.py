import io
import time
import socket
import smtplib
from email.message import EmailMessage
from typing import Optional, List, Tuple

import pandas as pd
import streamlit as st

st.set_page_config(page_title="Bulk Email Sender", page_icon="✉️", layout="wide")

# ====================== HEADER ======================
st.title("✉️ Bulk Email Sender")
st.markdown("**Professional • Reliable • Simple**")

# ====================== SIDEBAR ======================
with st.sidebar:
    st.header("SMTP Configuration")
    
    smtp_server = st.text_input("SMTP Server", value="smtp.intellinksea.com", key="smtp_server")
    smtp_port = st.number_input("Port", value=587, min_value=1, max_value=65535, key="smtp_port")
    
    smtp_user = st.text_input("Email Address", placeholder="you@intellinksea.com", key="smtp_user")
    smtp_password = st.text_input("Password", type="password", key="smtp_password")

    st.markdown("---")
    st.info("**Tip**: Start with **Dry Run** enabled")

# ====================== MAIN LAYOUT ======================
col_left, col_right = st.columns([2, 1])

# ====================== LEFT COLUMN - MAIN WORK AREA ======================
with col_left:
    # Recipients Section
    st.subheader("📤 1. Upload Recipients")
    uploaded_file = st.file_uploader("CSV or Excel file", type=["csv", "xlsx", "xls"], key="file_upload")

    recipients_df: Optional[pd.DataFrame] = None

    if uploaded_file:
        try:
            if uploaded_file.name.lower().endswith('.csv'):
                recipients_df = pd.read_csv(uploaded_file)
            else:
                recipients_df = pd.read_excel(uploaded_file)

            recipients_df.columns = [str(col).strip().lower() for col in recipients_df.columns]

            st.success(f"✅ Loaded **{len(recipients_df)}** records")

            # Email Column Selection
            email_col = st.selectbox("Select Email Column", recipients_df.columns)
            if st.button("✅ Confirm Email Column", type="primary", use_container_width=True):
                recipients_df = recipients_df.rename(columns={email_col: "email"})
                st.success(f"Email column set to: **{email_col}**")
                st.dataframe(recipients_df.head(6), use_container_width=True)

        except Exception as e:
            st.error(f"File Error: {e}")

    # Email Content Section
    st.markdown("---")
    st.subheader("✉️ 2. Email Content")

    subject = st.text_input("Subject", placeholder="Quarterly Business Update - Q2 2026", key="subject")

    body = st.text_area(
        "Email Body — Use {name} for personalization", 
        value=st.session_state.get("body", "Hello {name},\n\nPlease find the latest update attached.\n\nBest regards,\nTeam Intellinksea"),
        height=280,
        key="body"
    )

    # Send Section
    st.markdown("---")
    st.subheader("🚀 3. Send Campaign")

    c1, c2 = st.columns(2)
    with c1:
        dry_run = st.checkbox("Dry Run (Preview Only)", value=True)
    with c2:
        delay = st.slider("Delay between emails (seconds)", 0, 3, 1)

    if st.button("🚀 SEND EMAILS NOW", type="primary", use_container_width=True):
        if not smtp_user or not smtp_password:
            st.error("❌ Please enter SMTP credentials in the sidebar.")
        elif recipients_df is None or "email" not in recipients_df.columns:
            st.error("❌ Please upload file and confirm email column.")
        elif not subject or not body:
            st.error("❌ Subject and Body are required.")
        else:
            valid_df = recipients_df[recipients_df["email"].astype(str).str.contains("@", na=False)].copy()

            if len(valid_df) == 0:
                st.error("No valid email addresses found.")
                st.stop()

            # Progress
            progress_bar = st.progress(0)
            status_text = st.empty()

            sent_count = 0
            failed: List[Tuple[str, str]] = []

            try:
                with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as smtp:
                    smtp.ehlo()
                    if smtp_port in (587, 25):
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
                        except Exception as e:
                            failed.append((recipient, str(e)))

                        progress_bar.progress((idx + 1) / len(valid_df))
                        status_text.text(f"Sending {idx+1}/{len(valid_df)} → {recipient}")

                        if delay > 0:
                            time.sleep(delay)

            except Exception as e:
                st.error(f"SMTP Error: {e}")

            # ====================== FINAL NOTIFICATION ======================
            st.success(f"""
            🎉 **Campaign Completed Successfully!**

            **Sent**: {sent_count} emails  
            **Total Recipients**: {len(valid_df)}  
            **Failed**: {len(failed)} emails
            """)

            if failed:
                st.warning("Some emails failed to send.")
                with st.expander("📋 View Failed Emails"):
                    failed_df = pd.DataFrame(failed, columns=["Email", "Error"])
                    st.dataframe(failed_df, use_container_width=True)
                    st.download_button(
                        "Download Failed Emails as CSV",
                        failed_df.to_csv(index=False),
                        file_name="failed_emails.csv",
                        mime="text/csv"
                    )

            st.balloons()

# ====================== RIGHT COLUMN - SUMMARY ======================
with col_right:
    st.subheader("Campaign Summary")
    
    if recipients_df is not None and "email" in recipients_df.columns:
        total = len(recipients_df)
        valid = len(recipients_df[recipients_df["email"].astype(str).str.contains("@", na=False)])
        
        st.metric("Total Records", total)
        st.metric("Valid Emails", valid, delta=valid - total)
        
        st.markdown("### Preview")
        st.dataframe(recipients_df[["email"]].head(8), use_container_width=True)
    else:
        st.info("Upload recipient file to see summary")

    st.markdown("---")
    st.markdown("### Instructions")
    st.markdown("""
    1. Upload your recipient list  
    2. Confirm the email column  
    3. Write your message  
    4. Click **Send Emails**
    """)

    st.caption("Built for Intellinksea")
