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

# --- NIEUWE FUNCTIES VOOR DE DIRECTIE (ANONIEM) ---
def load_all_school_data():
    """Laadt alle CSV's uit de map, voegt ze samen en verwijdert namen."""
    all_lessons = []
    all_days = []
    
    # 1. Alle lesbestanden samenvoegen
    lesson_files = glob.glob(f"{DATA_DIR}/*_lessons.csv")
    for f in lesson_files:
        try:
            df = pd.read_csv(f)
            all_lessons.append(df)
        except:
            pass
            
    # 2. Alle dagbestanden samenvoegen
    day_files = glob.glob(f"{DATA_DIR}/*_day.csv")
    for f in day_files:
        try:
            df = pd.read_csv(f)
            all_days.append(df)
        except:
            pass

    # Samenvoegen (indien data aanwezig)
    df_lessons_total = pd.concat(all_lessons, ignore_index=True) if all_lessons else pd.DataFrame()
    df_days_total = pd.concat(all_days, ignore_index=True) if all_days else pd.DataFrame()
    
    return df_days_total, df_lessons_total

import plotly.colors as pc

def draw_ridgeline_artistic(df, kolom, titel, basis_kleur_naam="Teal"):
    """
    Maakt een 'Joyplot' met overlappende 'bergen' en een gradiënt.
    """
    if df.empty: return None
    
    klassen = sorted(df["Klas"].unique(), reverse=True)
    fig = go.Figure()

    # Genereer een kleurenpalet op basis van het aantal klassen
    # We pakken een spectrum (bijv. Teal of Sunset)
    colors = px.colors.sample_colorscale(basis_kleur_naam, [n/(len(klassen)) for n in range(len(klassen))])

    for i, klas in enumerate(klassen):
        df_k = df[df["Klas"] == klas]
        
        fig.add_trace(go.Violin(
            x=df_k[kolom],
            y=[klas] * len(df_k),
            name=klas,
            side='positive', 
            orientation='h', 
            width=2.5,  # Breder = meer overlap = mooier effect
            line_color='white', # Witte rand maakt het 'clean'
            line_width=1,
            fillcolor=colors[i], # Gradiënt kleur
            opacity=0.8,
            points=False,
            meanline_visible=False # Geen harde lijnen
        ))

    fig.update_layout(
        title=dict(text=titel, font=dict(size=20, family="Arial", color="#333")),
        xaxis_title=None,
        yaxis_title=None,
        showlegend=False,
        height=120 + (len(klassen) * 40),
        margin=dict(l=0, r=0, t=50, b=20),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(range=[0.5, 5.5], showgrid=False, zeroline=False, visible=True),
        yaxis=dict(showgrid=False, showline=False, showticklabels=True)
    )
    return fig

def draw_sankey_butterfly(df):
    """
    Creëert een Butterfly Sankey: Negatief (links) -> Klassen (midden) -> Positief (rechts).
    """
    if df.empty: return None
    
    # 1. Data Voorbereiding
    def clean_labels(df, kolom):
        temp = df.copy()
        temp[kolom] = temp[kolom].astype(str).str.split(',')
        temp = temp.explode(kolom)
        temp[kolom] = temp[kolom].str.strip()
        return temp[(temp[kolom] != 'nan') & (temp[kolom] != '')]

    df_pos = clean_labels(df, 'Positief')
    df_neg = clean_labels(df, 'Negatief')

    counts_pos = df_pos.groupby(['Klas', 'Positief']).size().reset_index(name='Aantal')
    counts_neg = df_neg.groupby(['Negatief', 'Klas']).size().reset_index(name='Aantal')

    # 2. Nodes bepalen (Negatief -> Klassen -> Positief)
    neg_uniek = sorted(list(counts_neg['Negatief'].unique()))
    klassen_uniek = sorted(list(df['Klas'].unique()))
    pos_uniek = sorted(list(counts_pos['Positief'].unique()))
    
    all_nodes = neg_uniek + klassen_uniek + pos_uniek
    node_map = {name: i for i, name in enumerate(all_nodes)}

    # 3. Kleuren voor de Nodes
    # Roodachtig voor negatief, Grijs voor klassen, Groenachtig voor positief
    node_colors = (["#ff7675"] * len(neg_uniek) + 
                   ["#636e72"] * len(klassen_uniek) + 
                   ["#55efc4"] * len(pos_uniek))

    # 4. Links opbouwen
    sources = []
    targets = []
    values = []
    link_colors = []

    # Negatief -> Klas (Links naar Midden)
    for _, row in counts_neg.iterrows():
        sources.append(node_map[row['Negatief']])
        targets.append(node_map[row['Klas']])
        values.append(row['Aantal'])
        link_colors.append("rgba(214, 48, 49, 0.3)") # Transparant rood

    # Klas -> Positief (Midden naar Rechts)
    for _, row in counts_pos.iterrows():
        sources.append(node_map[row['Klas']])
        targets.append(node_map[row['Positief']])
        values.append(row['Aantal'])
        link_colors.append("rgba(0, 184, 148, 0.3)") # Transparant groen

    # 5. Dynamische Hoogte
    dynamic_height = max(600, len(all_nodes) * 35)

    fig = go.Figure(data=[go.Sankey(
        textfont=dict(size=13, color="black", family="Arial Black"),
        node = dict(
          pad = 35, thickness = 20,
          line = dict(color = "white", width = 1),
          label = [f" {n} " for n in all_nodes],
          color = node_colors
        ),
        link = dict(
          source = sources,
          target = targets,
          value = values,
          color = link_colors
        )
    )])

    fig.update_layout(
        title=dict(text="⚖️ Balans per Klas: Negatief vs Positief", font=dict(size=22)),
        height=dynamic_height,
        font=dict(size=12),
        margin=dict(l=40, r=40, t=80, b=40),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)'
    )
    return fig
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

    # 1. Google Sheets Verbinding (Zorg dat secrets zijn ingesteld!)
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    # 2. Laden van data uit Google Sheets met TTL=0 (geen cache)
    try:
        # We halen de data op. ttl=0 zorgt dat we ALTIJD de nieuwste versie zien.
        all_day_data = conn.read(spreadsheet=SHEET_URL, ttl=0)
        
        if not all_day_data.empty and "Email" in all_day_data.columns:
            # Filter op e-mail (case-insensitive en zonder spaties)
            day_df = all_day_data[all_day_data["Email"].str.strip().str.lower() == user["email"].lower()].copy()
            
            # CRUCIAAL: Zet kolommen om naar de juiste types
            # Als dit niet gebeurt, tekent de grafiek in Tab 3 niets!
            day_df["Datum"] = pd.to_datetime(day_df["Datum"], errors="coerce")
            day_df["Energie"] = pd.to_numeric(day_df["Energie"], errors="coerce")
            day_df["Stress"] = pd.to_numeric(day_df["Stress"], errors="coerce")
            
            # Verwijder rijen waar de conversie mislukt is
            day_df = day_df.dropna(subset=["Datum", "Energie", "Stress"])
        else:
            day_df = pd.DataFrame(columns=["Email", "Datum", "Energie", "Stress"])
    except Exception as e:
        st.error(f"Fout bij verbinding met Google Sheets: {e}")
        day_df = pd.DataFrame(columns=["Email", "Datum", "Energie", "Stress"])
        all_day_data = day_df

    # 3. Lokale Lesregistratie laden
    if not os.path.exists(LES_FILE):
        pd.DataFrame(columns=["Datum","Klas","Lesaanpak","Klasmanagement","Positief","Negatief"]).to_csv(LES_FILE, index=False)

    les_df = pd.read_csv(LES_FILE)
    # Ook hier datum omzetten voor de zekerheid
    if not les_df.empty:
        les_df["Datum"] = pd.to_datetime(les_df["Datum"], errors="coerce")

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

# =================================================
# =============== DIRECTIE VIEW ===================
# =================================================
elif user["role"] == "director":
    st.header("🎓 Directie Dashboard")

    # ---------------------------------------------------------
    # STAP 1: DATA LADEN
    # ---------------------------------------------------------
    _, df_lessons_raw = load_all_school_data()
    
    if not df_lessons_raw.empty:
        df_lessons_raw["Datum"] = pd.to_datetime(df_lessons_raw["Datum"], errors='coerce')
        df_lessons_raw = df_lessons_raw.dropna(subset=["Datum"])
        all_classes = sorted(df_lessons_raw["Klas"].unique())
    else:
        all_classes = []

    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        df_sheet = conn.read(spreadsheet=SHEET_URL, ttl=0)
        if not df_sheet.empty and "Datum" in df_sheet.columns:
            df_sheet["Datum"] = pd.to_datetime(df_sheet["Datum"], errors='coerce')
            df_sheet["Energie"] = pd.to_numeric(df_sheet["Energie"], errors='coerce')
            df_sheet["Stress"] = pd.to_numeric(df_sheet["Stress"], errors='coerce')
            df_wellbeing_raw = df_sheet.dropna(subset=["Datum", "Energie", "Stress"])
        else:
            df_wellbeing_raw = pd.DataFrame(columns=["Datum", "Energie", "Stress"])
    except:
        df_wellbeing_raw = pd.DataFrame(columns=["Datum", "Energie", "Stress"])

    # ---------------------------------------------------------
    # STAP 2: KPI's
    # ---------------------------------------------------------
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("📝 Registraties", len(df_lessons_raw))
    k2.metric("🏫 Klassen", len(all_classes))
    
    avg_en = df_wellbeing_raw['Energie'].mean() if not df_wellbeing_raw.empty else 0
    k3.metric("🔋 Energie", f"{avg_en:.1f}")
    
    avg_str = df_wellbeing_raw['Stress'].mean() if not df_wellbeing_raw.empty else 0
    k4.metric("🤯 Stress", f"{avg_str:.1f}")
    
    st.markdown("---")

    # ---------------------------------------------------------
    # STAP 3: TABS
    # ---------------------------------------------------------
    tab_stats, tab_wellbeing, tab_culture = st.tabs([
        "📊 Klas Statistieken", 
        "🧘 Welzijn Trend", 
        "🦋 Oorzaak & Gevolg"
    ])

    # ==========================================
    # TAB 1: HEATMAPS & MIRROR DENSITY
    # ==========================================
    with tab_stats:
        st.subheader("🗓️ Evolutie & Verdeling")
        
        col_content, col_filter = st.columns([3, 1])

        # --- FILTERS (RECHTS) ---
        with col_filter:
            st.markdown("**📅 Periode**")
            p_choice = st.radio("Kies:", ["Volledig schooljaar", "Afgelopen maand", "Afgelopen 2 weken"], label_visibility="collapsed", key="t1_per")
            
            st.markdown("---")
            st.markdown("**🏫 Klassen**")
            with st.container(height=450, border=True):
                sel_classes_t1 = []
                for k in all_classes:
                    if st.checkbox(f"{k}", value=True, key=f"t1_chk_{k}"):
                        sel_classes_t1.append(k)

        # --- LOGICA ---
        today = pd.Timestamp.today()
        if p_choice == "Afgelopen maand":
            start_d = today - pd.Timedelta(days=30)
        elif p_choice == "Afgelopen 2 weken":
            start_d = today - pd.Timedelta(days=14)
        else:
            start_d = pd.Timestamp(year=today.year if today.month >= 9 else today.year - 1, month=9, day=1)

        df_t1 = df_lessons_raw[
            (df_lessons_raw["Datum"] >= start_d) & 
            (df_lessons_raw["Klas"].isin(sel_classes_t1))
        ].copy()

        # --- VISUALISATIES (LINKS) ---
        with col_content:
            if not df_t1.empty:
                
                # -----------------------------------------------------
                # 1. HEATMAPS (Subplots voor perfecte uitlijning)
                # -----------------------------------------------------
                st.caption("🔥 **Evolutie per Maand** (Links: Management | Rechts: Aanpak)")
                
                df_t1['Maand'] = df_t1['Datum'].dt.strftime('%Y-%m')
                hm_mgmt = df_t1.pivot_table(index="Klas", columns="Maand", values="Klasmanagement", aggfunc="mean")
                hm_didac = df_t1.pivot_table(index="Klas", columns="Maand", values="Lesaanpak", aggfunc="mean")
                hm_count = df_t1.pivot_table(index="Klas", columns="Maand", values="Klasmanagement", aggfunc="count") # Voor hover

                if not hm_mgmt.empty:
                    # We gebruiken make_subplots om ze in 1 figuur te dwingen -> altijd even groot
                    from plotly.subplots import make_subplots
                    
                    fig_heat = make_subplots(
                        rows=1, cols=2, 
                        shared_yaxes=True, # Deel de Y-as (Klaasnamen)
                        subplot_titles=("Klasmanagement", "Didactische Aanpak"),
                        horizontal_spacing=0.05
                    )

                    # Heatmap 1: Management
                    fig_heat.add_trace(go.Heatmap(
                        z=hm_mgmt.values, x=hm_mgmt.columns, y=hm_mgmt.index,
                        colorscale="RdBu", zmin=1, zmax=5, showscale=False,
                        customdata=hm_count.values,
                        hovertemplate="<b>Management: %{z:.1f}</b><br>Regs: %{customdata}<extra></extra>"
                    ), row=1, col=1)

                    # Heatmap 2: Aanpak
                    fig_heat.add_trace(go.Heatmap(
                        z=hm_didac.values, x=hm_didac.columns, y=hm_didac.index,
                        colorscale="RdBu", zmin=1, zmax=5, showscale=False,
                        customdata=hm_count.values,
                        hovertemplate="<b>Aanpak: %{z:.1f}</b><br>Regs: %{customdata}<extra></extra>"
                    ), row=1, col=2)

                    fig_heat.update_layout(
                        height=150 + (len(hm_mgmt)*30),
                        margin=dict(l=0, r=0, t=30, b=0),
                        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
                    )
                    # X-assen opschonen (geen titels, wel labels)
                    fig_heat.update_xaxes(showticklabels=False) 
                    st.plotly_chart(fig_heat, use_container_width=True)

                # -----------------------------------------------------
                # 2. MIRROR DENSITY CHART (Split Violin)
                # -----------------------------------------------------
                st.markdown("---")
                st.caption("🎻 **Score Verdeling** (Groen = Aanpak ⬆️ | Paars = Management ⬇️)")
                
                # We bouwen één grote figuur
                fig_mirror = go.Figure()

                # Sorteer klassen omgekeerd zodat A bovenaan staat in de grafiek
                sorted_classes = sorted(sel_classes_t1, reverse=True) 

                for k in sorted_classes:
                    subset = df_t1[df_t1['Klas'] == k]
                    if subset.empty: continue

                    # Deel 1: Aanpak (Positieve kant)
                    fig_mirror.add_trace(go.Violin(
                        x=subset['Lesaanpak'],
                        y=[k] * len(subset),
                        legendgroup='Aanpak', scalegroup='Aanpak', name='Aanpak',
                        side='positive',
                        orientation='h',
                        line_color='#00CC96', # Helder Groen/Teal
                        fillcolor='#00CC96',
                        opacity=0.6,
                        meanline_visible=True, # Toont het gemiddelde als streepje
                        hoverinfo='y+x', # Toont klas + score
                        points=False, # Geen puntjes voor rustig beeld
                        width=1.5 # Maak ze wat breder/hoger
                    ))

                    # Deel 2: Management (Negatieve kant)
                    fig_mirror.add_trace(go.Violin(
                        x=subset['Klasmanagement'],
                        y=[k] * len(subset),
                        legendgroup='Management', scalegroup='Management', name='Management',
                        side='negative',
                        orientation='h',
                        line_color='#AB63FA', # Helder Paars
                        fillcolor='#AB63FA',
                        opacity=0.6,
                        meanline_visible=True,
                        hoverinfo='y+x',
                        points=False,
                        width=1.5
                    ))

                # Opmaak van de Mirror Chart
                fig_mirror.update_layout(
                    violinmode='overlay', # Cruciaal: zorgt dat ze tegen elkaar plakken
                    gap=0,
                    height=200 + (len(sorted_classes) * 50), # Rek de hoogte uit per klas
                    showlegend=False, # Legenda is niet nodig door de caption en kleuren
                    xaxis=dict(
                        range=[0.5, 5.5], # Vaste schaal 1-5
                        tickvals=[1, 2, 3, 4, 5],
                        ticktext=["1 (Laag)", "2", "3", "4", "5 (Hoog)"],
                        showgrid=True,
                        gridcolor='#eee',
                        title=None
                    ),
                    yaxis=dict(
                        showgrid=False,
                        title=None
                    ),
                    margin=dict(l=0, r=0, t=10, b=0),
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)'
                )
                
                st.plotly_chart(fig_mirror, use_container_width=True)

            else:
                st.info("Geen data gevonden voor deze selectie.")

    # ==========================================
    # TAB 2: WELZIJN
    # ==========================================
    with tab_wellbeing:
        w_col1, w_col2 = st.columns([4, 1])
        with w_col1: st.subheader("De Menselijke Maat")
        with w_col2: 
            w_choice = st.selectbox("Periode", ["Volledig schooljaar", "Afgelopen maand"], label_visibility="collapsed", key="w_filt")

        if w_choice == "Afgelopen maand":
            start_w = today - pd.Timedelta(days=30)
        else:
            start_w = pd.Timestamp(year=today.year if today.month >= 9 else today.year - 1, month=9, day=1)
        
        df_w = df_wellbeing_raw[df_wellbeing_raw["Datum"] >= start_w].copy()

        if not df_w.empty:
            daily_avg = df_w.groupby("Datum")[["Energie", "Stress"]].mean().reset_index().sort_values("Datum")
            
            fig_trend = go.Figure()
            # Energie
            fig_trend.add_trace(go.Scatter(
                x=daily_avg['Datum'], y=daily_avg['Energie'], mode='lines', 
                line=dict(color='#2ecc71', width=3), showlegend=False
            ))
            # Stress
            fig_trend.add_trace(go.Scatter(
                x=daily_avg['Datum'], y=daily_avg['Stress'], mode='lines', 
                line=dict(color='#e74c3c', width=3), showlegend=False
            ))
            
            # Annotaties
            last_pt = daily_avg.iloc[-1]
            fig_trend.add_annotation(x=last_pt['Datum'], y=last_pt['Energie'], text="Energie", showarrow=False, xanchor="left", xshift=10, font=dict(color="#2ecc71", size=14))
            fig_trend.add_annotation(x=last_pt['Datum'], y=last_pt['Stress'], text="Stress", showarrow=False, xanchor="left", xshift=10, font=dict(color="#e74c3c", size=14))

            fig_trend.update_layout(
                height=450,
                xaxis=dict(showgrid=False, showline=False, tickformat="%d %b"),
                yaxis=dict(showgrid=False, showline=False, showticklabels=False, range=[0.5, 5.5]),
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                margin=dict(r=80)
            )
            fig_trend.add_hrect(y0=4, y1=5.5, fillcolor="#e74c3c", opacity=0.03, line_width=0)
            st.plotly_chart(fig_trend, use_container_width=True)
        else:
            st.info("Geen data.")

    # ==========================================
    # TAB 3: SANKEY
    # ==========================================
    with tab_culture:
        st.subheader("🦋 Oorzaak & Gevolg")
        col_sankey, col_filter_s = st.columns([3, 1])

        with col_filter_s:
            st.markdown("**📅 Periode**")
            s_period = st.radio("Kies:", ["Volledig schooljaar", "Afgelopen maand"], label_visibility="collapsed", key="s_p_rad")
            st.markdown("---")
            st.markdown("**🏫 Klassen**")
            with st.container(height=450, border=True):
                sel_classes_sankey = []
                for k in all_classes:
                    if st.checkbox(f"{k}", value=True, key=f"s_chk_{k}"):
                        sel_classes_sankey.append(k)

        if s_period == "Afgelopen maand":
            start_s = today - pd.Timedelta(days=30)
        else:
            start_s = pd.Timestamp(year=today.year if today.month >= 9 else today.year - 1, month=9, day=1)

        mask_s = (df_lessons_raw["Datum"] >= start_s) & (df_lessons_raw["Klas"].isin(sel_classes_sankey))
        df_sankey_filtered = df_lessons_raw.loc[mask_s].copy()

        with col_sankey:
            if not df_sankey_filtered.empty and len(sel_classes_sankey) > 0:
                fig_s = draw_sankey_butterfly(df_sankey_filtered)
                if fig_s:
                    fig_s.update_layout(height=600, margin=dict(t=20, b=20))
                    st.plotly_chart(fig_s, use_container_width=True)
                else:
                    st.warning("Te weinig flows.")
            else:
                st.warning("Selecteer minstens één klas.")
