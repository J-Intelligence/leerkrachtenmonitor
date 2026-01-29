import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta
import os, glob, hashlib
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from wordcloud import WordCloud
import matplotlib.pyplot as plt
from streamlit_gsheets import GSheetsConnection

# -------------------------------------------------
# CONFIG
# -------------------------------------------------
st.set_page_config(
    page_title="Leerkrachtenmonitor",
    page_icon="❤️",
    layout="centered"
)

DATA_DIR = "data"
USERS_FILE = f"{DATA_DIR}/users.csv"
os.makedirs(DATA_DIR, exist_ok=True)

# Google Sheets URL voor Daggevoel
SHEET_URL = "https://docs.google.com/spreadsheets/d/1pz_9hhCSaTEkRs71nrTJiayfXksHJJMvSc08rYmxeu0/edit?usp=sharing"

# -------------------------------------------------
# HELPERS
# -------------------------------------------------
def normalize_email(email):
    return email.strip().lower()

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def day_file(email):
    return f"{DATA_DIR}/{email.split('@')[0]}_day.csv"

def lesson_file(email):
    return f"{DATA_DIR}/{email.split('@')[0]}_lessons.csv"

# -------------------------------------------------
# USERS
# -------------------------------------------------
def load_users():
    if not os.path.exists(USERS_FILE):
        pd.DataFrame(columns=["email", "password", "role"]).to_csv(USERS_FILE, index=False)
    return pd.read_csv(USERS_FILE)

def save_users(df):
    df.to_csv(USERS_FILE, index=False)

# -------------------------------------------------
# AUTO LOGIN
# -------------------------------------------------
params = st.query_params
if "user" in params and "user" not in st.session_state:
    users = load_users()
    email = normalize_email(params["user"])
    u = users[users.email == email]
    if not u.empty:
        st.session_state.user = u.iloc[0].to_dict()

# -------------------------------------------------
# AUTH
# -------------------------------------------------
st.title("❤️ Leerkrachtenmonitor")
users = load_users()

if "user" not in st.session_state:
    tab_login, tab_reg = st.tabs(["🔐 Inloggen", "🆕 Registreren"])

    with tab_login:
        email = normalize_email(st.text_input("E-mail"))
        pw = st.text_input("Wachtwoord", type="password", key="login_password")
        remember = st.checkbox("Onthoud mij")

        if st.button("Inloggen"):
            u = users[users.email == email]
            if not u.empty and hash_pw(pw) == u.iloc[0].password:
                st.session_state.user = u.iloc[0].to_dict()
                if remember:
                    st.query_params["user"] = email
                st.rerun()
            else:
                st.error("Ongeldige login")

    with tab_reg:
        r_email = normalize_email(st.text_input("School-e-mail"))
        r_pw = st.text_input("Wachtwoord", type="password", key="reg_password")
        if st.button("Account aanmaken"):
            if r_email in users.email.values:
                st.error("Account bestaat al")
            else:
                role = "director" if r_email.startswith("directie") else "teacher"
                users.loc[len(users)] = [r_email, hash_pw(r_pw), role]
                save_users(users)
                st.success("Account aangemaakt")

    st.stop()

# -------------------------------------------------
# LOGOUT
# -------------------------------------------------
user = st.session_state.user
st.sidebar.success(f"Ingelogd als {user['email']}")

if st.sidebar.button("Uitloggen"):
    st.query_params.clear()
    st.session_state.clear()
    st.rerun()

# -------------------------------------------------
# CONSTANTEN
# -------------------------------------------------
POS_MOODS = ["Inspirerend","Motiverend","Actief","Verbonden","Respectvol","Gefocust","Veilig","Energiek"]
NEG_MOODS = ["Demotiverend","Passief","Onrespectvol","Chaotisch","Afgeleid","Rumoerig","Onveilig"]
KLASSEN = [
    "5ECWI/WEWI/WEWIC","5HW","5ECMT/5MT/5WEMTC","5MT",
    "3HW/3MT","6ECWI-HW","6MT","6WEWI","6ECMT/6WEMT"
]

# =================================================
# =============== LEERKRACHT VIEW =================
# =================================================
if user["role"] == "teacher":

    LES_FILE = lesson_file(user["email"])

    # Google Sheets Verbinding voor Daggevoel
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # Laden van data uit Google Sheets
    try:
        all_day_data = conn.read(spreadsheet=SHEET_URL)
        # Filteren zodat je alleen je eigen data ziet
        if "Email" in all_day_data.columns:
            day_df = all_day_data[all_day_data["Email"] == user["email"]].copy()
        else:
            day_df = pd.DataFrame(columns=["Email", "Datum", "Energie", "Stress"])
    except:
        day_df = pd.DataFrame(columns=["Email", "Datum", "Energie", "Stress"])
        all_day_data = day_df

    if not os.path.exists(LES_FILE):
        pd.DataFrame(columns=["Datum","Klas","Lesaanpak","Klasmanagement","Positief","Negatief"]).to_csv(LES_FILE, index=False)

    les_df = pd.read_csv(LES_FILE)

    tab1, tab2, tab3, tab4 = st.tabs([
        "🧠 Daggevoel",
        "📝 Lesregistratie",
        "📊 Visualisaties",
        "📄 Maandrapport"
    ])

    # -------------------------------------------------
    # TAB 1 – DAGGEVOEL
    # -------------------------------------------------
    with tab1:
        with st.form("daggevoel", clear_on_submit=True):
            d = st.date_input("Datum", date.today())
            energie = st.slider("Energie", 1, 5, 3)
            stress = st.slider("Stress", 1, 5, 3)

            if st.form_submit_button("Opslaan"):
                new_entry = pd.DataFrame({
                    "Email": [user["email"]],
                    "Datum": [str(d)],
                    "Energie": [energie],
                    "Stress": [stress]
                })
                # Voeg toe aan de totale lijst en upload naar GSheets
                updated_all_data = pd.concat([all_day_data, new_entry], ignore_index=True)
                conn.update(spreadsheet=SHEET_URL, data=updated_all_data)
                
                st.success("Succesvol geregistreerd in de cloud ✔️")
                st.rerun()

    # -------------------------------------------------
    # TAB 2 – LESREGISTRATIE
    # -------------------------------------------------
    with tab2:
        with st.form("lesregistratie", clear_on_submit=True):
            klas = st.selectbox("Klas", KLASSEN)
            lesaanpak = st.slider("Lesaanpak", 1, 5, 3)
            klasmanagement = st.slider("Klasmanagement", 1, 5, 3)

            st.write("---")
            
            # Maak twee kolommen aan
            col_pos, col_neg = st.columns(2)

            with col_pos:
                st.markdown("### ✨ Positief")
                # We maken een lijstje om de geselecteerde moods op te vangen
                positief = []
                for m in POS_MOODS:
                    if st.checkbox(m, key=f"p_{m}"):
                        positief.append(m)

            with col_neg:
                st.markdown("### ⚠️ Aandachtspunten")
                negatief = []
                for m in NEG_MOODS:
                    if st.checkbox(m, key=f"n_{m}"):
                        negatief.append(m)

            st.write("---")

            if st.form_submit_button("Les opslaan"):
                les_df.loc[len(les_df)] = [
                    pd.Timestamp.now(),
                    klas,
                    lesaanpak,
                    klasmanagement,
                    ", ".join(positief),
                    ", ".join(negatief)
                ]
                les_df.to_csv(LES_FILE, index=False)
                st.success("Les opgeslagen ✔️")
                st.rerun()

    # -------------------------------------------------
    # TAB 3 – VISUALISATIES
    # -------------------------------------------------
    with tab3:
        st.header("📊 Visualisaties")

        # Gebruik de gefilterde day_df van bovenaan
        plot_df = day_df.copy()
        plot_df["Datum"] = pd.to_datetime(plot_df["Datum"], errors="coerce")
        plot_df = plot_df.dropna(subset=["Datum"])

        if not plot_df.empty:
            fig = px.line(
                plot_df.sort_values("Datum"),
                x="Datum",
                y=["Energie","Stress"],
                markers=True,
                color_discrete_map={"Energie":"#2ecc71","Stress":"#e74c3c"}
            )
            fig.update_layout(yaxis_range=[0.5,5.5])
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Nog geen daggevoel geregistreerd.")

        st.subheader("🌍 Totaaloverzicht (Alle lessen)")

        if not les_df.empty:
            avg_aanpak_totaal = les_df["Lesaanpak"].mean()
            avg_mgmt_totaal = les_df["Klasmanagement"].mean()

            col_m1, col_m2 = st.columns(2)
            with col_m1:
                st.metric("Gem. Lesaanpak", f"{avg_aanpak_totaal:.2f} / 5")
            with col_m2:
                st.metric("Gem. Klasmanagement", f"{avg_mgmt_totaal:.2f} / 5")

            st.write("---")

            pos_series = les_df["Positief"].dropna().astype(str).str.split(",").explode().str.strip()
            neg_series = les_df["Negatief"].dropna().astype(str).str.split(",").explode().str.strip()

            all_labels = pd.concat([
                pd.DataFrame({"Label": pos_series, "Type": "Positief"}),
                pd.DataFrame({"Label": neg_series, "Type": "Negatief"}),
            ], ignore_index=True)
            all_labels = all_labels[all_labels["Label"].str.len() > 0]

            if not all_labels.empty:
                counts = all_labels.groupby(["Label", "Type"]).size().reset_index(name="Aantal")
                words_freq = dict(zip(counts["Label"], counts["Aantal"]))
                label_color_map = {row["Label"]: ("green" if row["Type"] == "Positief" else "red") for _, row in counts.iterrows()}

                wc = WordCloud(width=800, height=400, background_color="white", random_state=42).generate_from_frequencies(words_freq)
                fig_wc, ax = plt.subplots(figsize=(10, 5))
                ax.imshow(wc.recolor(color_func=lambda word, **kwargs: label_color_map.get(word, "black")), interpolation="bilinear")
                ax.axis("off")
                st.pyplot(fig_wc)
            else:
                st.info("Geen labels beschikbaar.")
        else:
            st.info("Nog geen lesdata beschikbaar.")

        st.divider()
        st.subheader("🔎 Vergelijk 2 klassen")

        if not les_df.empty:
            beschikbare_klassen = sorted(les_df["Klas"].unique())
            selected_klassen = st.multiselect("Selecteer exact 2 klassen:", beschikbare_klassen, max_selections=2)

            if len(selected_klassen) == 2:
                k1, k2 = selected_klassen
                col1, col2 = st.columns(2)
                for current_klas, current_col in zip([k1, k2], [col1, col2]):
                    with current_col:
                        st.markdown(f"### Klas: {current_klas}")
                        df_k = les_df[les_df["Klas"] == current_klas]
                        st.metric("Gem. Lesaanpak", f"{df_k['Lesaanpak'].mean():.1f} / 5")
                        st.metric("Gem. Management", f"{df_k['Klasmanagement'].mean():.1f} / 5")
            else:
                st.info("Kies twee klassen.")

    # -------------------------------------------------
    # TAB 4 – MAANDRAPPORT
    # -------------------------------------------------
    with tab4:
        today = date.today()
        last_month = (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
        
        # Gebruik gefilterde data van Sheets
        report_df = day_df.copy()
        report_df["Datum"] = pd.to_datetime(report_df["Datum"], errors="coerce")
        report_df = report_df.dropna(subset=["Datum"])
        
        subset = report_df[report_df["Datum"].dt.strftime("%Y-%m") == last_month]

        if subset.empty:
            st.info("Nog geen gegevens voor vorige maand.")
        else:
            if st.button("Genereer maandrapport"):
                path = f"{DATA_DIR}/{user['email'].split('@')[0]}_{last_month}.pdf"
                doc = SimpleDocTemplate(path)
                styles = getSampleStyleSheet()
                story = [
                    Paragraph(f"<b>Maandrapport {last_month}</b>", styles["Title"]),
                    Spacer(1,12),
                    Paragraph(f"Gem. energie: {subset['Energie'].mean():.2f}", styles["Normal"]),
                    Paragraph(f"Gem. stress: {subset['Stress'].mean():.2f}", styles["Normal"]),
                ]
                doc.build(story)
                with open(path, "rb") as f:
                    st.download_button("Download PDF", f, file_name=f"Maandrapport_{last_month}.pdf")
