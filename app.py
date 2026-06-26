import io
import os
import smtplib
from email.message import EmailMessage

import pandas as pd
import streamlit as st

try:
    import openai
    openai_available = True
except ImportError:
    openai_available = False

st.set_page_config(page_title="Bulk Email Sender", page_icon="✉️", layout="centered")
stitle = "Bulk Email Sender"

st.title(stitle)
st.write(
    "Upload a list of recipient emails, compose your message, and send personalized emails in bulk. "
    "The CSV must contain an `email` column and may optionally include a `name` column for template personalization."
)

with st.sidebar:
    st.header("SMTP Settings")
    smtp_server = st.text_input("SMTP Server", value="smtp.gmail.com")
    smtp_port = st.number_input("SMTP Port", value=587, min_value=1, max_value=65535)
    smtp_user = st.text_input("SMTP Username / Email")
    smtp_password = st.text_input("SMTP Password", type="password")
    openai_api_key = st.text_input("OpenAI API Key", type="password")
    st.markdown(
        "---\n"
        "**Note:** For Gmail, use an App Password or allow SMTP access for your account. "
        "Never share credentials publicly."
    )

uploaded_file = st.file_uploader("Upload recipients CSV or Excel", type=["csv", "txt", "xls", "xlsx"])

st.markdown(
    """
    <style>
    .stApp {
        background: linear-gradient(180deg, #eff6ff 0%, #f8fafc 100%);
        color: #1f2937;
    }
    .stButton>button {
        background: linear-gradient(90deg, #2563eb 0%, #0ea5e9 100%);
        color: white;
        border: none;
        border-radius: 1.25rem;
        height: 3.2rem;
        font-weight: 700;
        box-shadow: 0 14px 34px rgba(14, 165, 233, 0.18);
        transition: transform 0.2s ease, box-shadow 0.2s ease, filter 0.2s ease;
        width: 100%;
        letter-spacing: 0.02em;
        text-transform: uppercase;
    }
    .stButton>button:hover {
        transform: translateY(-1px);
        box-shadow: 0 18px 42px rgba(14, 165, 233, 0.22);
        filter: brightness(1.08);
    }
    .stButton>button:focus {
        outline: none;
        box-shadow: 0 0 0 4px rgba(56, 189, 248, 0.24);
    }
    .stTextInput>div>div>input,
    .stTextArea>div>div>textarea,
    .stNumberInput>div>div>input,
    .stFileUploader>div {
        border-radius: 1rem;
        border: 1px solid #dbeafe;
        background: #f8fafc;
        box-shadow: inset 0 1px 4px rgba(15, 23, 42, 0.05);
    }
    .stFileUploader>div,
    .stSidebar>div,
    .stMarkdown,
    .stExpander,
    .stTextInput,
    .stTextArea,
    .stNumberInput {
        background: #f8fafc;
        border-radius: 1rem;
        padding: 1rem;
        border: none;
    }
    .stSidebar .stMarkdown,
    .stSidebar .stTextInput,
    .stSidebar .stTextArea,
    .stSidebar .stNumberInput {
        background: #eef2ff;
    }
    .stAlert,
    .stMarkdown p,
    label {
        font-size: 0.97rem;
        color: #334155;
    }
    .stMarkdown h1,
    .stMarkdown h2,
    .stMarkdown h3,
    .stMarkdown h4 {
        color: #0f172a;
    }
    .stMetric {
        background: linear-gradient(180deg, #dbeafe 0%, #eff6ff 100%);
        border-radius: 1rem;
        padding: 1.1rem;
        border: 1px solid #bfdbfe;
    }
    .stColumn>div {
        padding-bottom: 1.15rem;
    }
    .reportview-container .main .block-container {
        padding-top: 1.4rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

recipients_df = None
if uploaded_file is not None:
    try:
        file_ext = uploaded_file.name.lower().split(".")[-1]
        raw_data = uploaded_file.read()

        if file_ext in ["csv", "txt"]:
            try:
                recipients_df = pd.read_csv(io.StringIO(raw_data.decode("utf-8")))
            except UnicodeDecodeError:
                recipients_df = pd.read_csv(io.StringIO(raw_data.decode("latin-1")))
        elif file_ext in ["xls", "xlsx"]:
            recipients_df = pd.read_excel(io.BytesIO(raw_data))
        else:
            st.error("Unsupported file type. Upload a CSV or Excel file.")
    except Exception as exc:
        st.error(f"Could not read the uploaded file: {exc}")

main_col, sidebar_col = st.columns([3, 1])
with main_col:
    if "body" not in st.session_state:
        st.session_state.body = (
            "Hello {name},\n\nThis is a bulk email sent via Streamlit.\n\nBest regards,\n[Your Name]"
        )

    subject = st.text_input("Email Subject")
    use_ai = st.checkbox("Use AI to design the email copy", value=False)
    if use_ai:
        st.markdown("### AI Email Drafting")
        ai_prompt = st.text_area(
            "AI Prompt",
            value=(
                "Write a friendly, personalized bulk email message for {name} introducing our offering. "
                "Keep it concise and professional with a clear call to action."
            ),
            height=150,
        )
        if not openai_available:
            st.warning("Install the `openai` package to enable AI email generation.")
        else:
            ai_action_col1, ai_action_col2 = st.columns([1, 1])
            with ai_action_col1:
                generate_draft = st.button("Generate Draft")
            with ai_action_col2:
                clear_ai = st.button("Reset Draft")

            if generate_draft:
                if not (openai_api_key or os.getenv("OPENAI_API_KEY")):
                    st.error("Enter your OpenAI API key in the sidebar or set OPENAI_API_KEY.")
                elif not subject.strip():
                    st.error("Provide an email subject before generating an AI draft.")
                else:
                    try:
                        openai.api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
                        prompt_text = (
                            "You are a professional email copywriter. "
                            "Use the placeholder {name} for personalization and produce a clean, friendly email body. "
                            f"Subject: {subject}\n"
                            f"Instructions: {ai_prompt}\n"
                            "Output only the email body without the subject."
                        )
                        response = openai.ChatCompletion.create(
                            model="gpt-3.5-turbo",
                            messages=[
                                {"role": "system", "content": "You write professional bulk email copy."},
                                {"role": "user", "content": prompt_text},
                            ],
                            temperature=0.7,
                            max_tokens=400,
                        )
                        generated_body = response.choices[0].message["content"].strip()
                        if "{name}" not in generated_body:
                            generated_body = "Hello {name},\n\n" + generated_body
                        st.session_state.body = generated_body
                        st.success("AI-generated email draft inserted into the body field.")
                    except Exception as ai_error:
                        st.error(f"AI generation failed: {ai_error}")
            elif clear_ai:
                st.session_state.body = ""

    st.markdown("### Email Content")
    body = st.text_area("Email Body", value=st.session_state.body, key="body", height=250)
    st.markdown("---")
    action_col1, action_col2 = st.columns([1, 1])
    with action_col1:
        submit_pressed = st.button("Send Emails")
    with action_col2:
        clear_pressed = st.button("Clear Body")

    if clear_pressed:
        st.session_state.body = ""
        st.experimental_rerun()

    if submit_pressed:
        if recipients_df is None:
            st.error("Please upload a recipients CSV before submitting.")
        elif "email" not in recipients_df.columns:
            st.error("The uploaded file must contain an `email` column.")
        elif not smtp_user or not smtp_password:
            st.error("Please enter SMTP username and password.")
        elif not subject.strip():
            st.error("Please enter an email subject.")
        elif not body.strip():
            st.error("Please enter an email body.")
        else:
            total = len(recipients_df)
            sent_count = 0
            failed = []

            with st.spinner("Sending emails..."):
                try:
                    with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as smtp:
                        smtp.ehlo()
                        if smtp_port == 587:
                            smtp.starttls()
                            smtp.ehlo()
                        smtp.login(smtp_user, smtp_password)

                        for _, row in recipients_df.iterrows():
                            recipient = str(row.get("email", "")).strip()
                            if not recipient:
                                failed.append((recipient, "Missing email address"))
                                continue

                            recipient_name = str(row.get("name", "")).strip() if "name" in recipients_df.columns else ""
                            personalized_body = body.format(name=recipient_name or "there")

                            message = EmailMessage()
                            message["From"] = smtp_user
                            message["To"] = recipient
                            message["Subject"] = subject
                            message.set_content(personalized_body)

                            try:
                                smtp.send_message(message)
                                sent_count += 1
                            except Exception as exc:
                                failed.append((recipient, str(exc)))

                except Exception as connection_error:
                    st.error(f"SMTP connection failed: {connection_error}")
                    st.stop()

            st.success(f"Emails sent: {sent_count} / {total}")
            if failed:
                st.warning(f"Failed to send {len(failed)} emails.")
                st.write("### Failures")
                for recipient, error in failed:
                    st.write(f"- {recipient or '[missing email]'}: {error}")

with sidebar_col:
    st.markdown("### Quick Tips")
    st.write(
        "- Use `{name}` to personalize the body.\n"
        "- Keep your subject short and action-oriented.\n"
        "- Use AI only when you want a fast draft."
    )
    if recipients_df is not None and "email" in recipients_df.columns:
        st.markdown("### Recipients Preview")
        st.metric("Loaded recipients", len(recipients_df))
        st.dataframe(recipients_df.head(8))

if uploaded_file is None:
    st.info("Upload a CSV file to begin.")
