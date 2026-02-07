import streamlit as st
import pandas as pd
import plotly.express as px
from fpdf import FPDF
import calendar

st.set_page_config(page_title="Ydelsesanalyse", layout="wide")

# ---------------------------------------------------------
# Hjælpere
# ---------------------------------------------------------

DANSKE_MÅNEDER_KORT = {
    1: "jan", 2: "feb", 3: "mar", 4: "apr",
    5: "maj", 6: "jun", 7: "jul", 8: "aug",
    9: "sep", 10: "okt", 11: "nov", 12: "dec",
}

DANSKE_UGEDAGE = {
    "Monday": "Mandag",
    "Tuesday": "Tirsdag",
    "Wednesday": "Onsdag",
    "Thursday": "Torsdag",
    "Friday": "Fredag",
    "Saturday": "Lørdag",
    "Sunday": "Søndag",
}

def måned_label(år, måned):
    return f"{DANSKE_MÅNEDER_KORT.get(måned, '')} {str(int(år))[-2:]}"


# ---------------------------------------------------------
# Robust dato-konvertering (Excel-serietal → datetime)
# ---------------------------------------------------------

def konverter_excel_dato(series):
    # Alt til numerisk
    s = pd.to_numeric(series, errors="coerce")

    # Filtrér til realistisk interval (2009–2070 ca.)
    mask = (s >= 40000) & (s <= 60000)
    s = s.where(mask)

    # Konverter til datetime, men uden at crashe
    datoer = pd.to_datetime(s, unit="d", origin="1899-12-30", errors="coerce")
    return datoer


# ---------------------------------------------------------
# Dataindlæsning
# ---------------------------------------------------------

def load_data(uploaded_file):
    df = pd.read_excel(uploaded_file)

    # Standardiser kolonnenavne
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # Find kolonner
    dato_cols = [c for c in df.columns if "dato" in c]
    if not dato_cols:
        st.error("Kunne ikke finde en kolonne med 'dato' i navnet.")
        st.stop()
    kol_dato = dato_cols[0]

    kode_cols = [c for c in df.columns if "ydelseskode" in c]
    if not kode_cols:
        st.error("Kunne ikke finde en kolonne med 'ydelseskode' i navnet.")
        st.stop()
    kol_kode = kode_cols[0]

    antal_cols = [c for c in df.columns if "antal" in c]
    if not antal_cols:
        st.error("Kunne ikke finde en kolonne med 'antal' i navnet.")
        st.stop()
    kol_antal = antal_cols[0]

    # Dato
    df["dato"] = konverter_excel_dato(df[kol_dato])
    df = df.dropna(subset=["dato"])

    if df.empty:
        st.error("Ingen gyldige datoer kunne konverteres fra filen.")
        st.stop()

    df["år"] = df["dato"].dt.year.astype(int)
    df["måned"] = df["dato"].dt.month.astype(int)

    # Ugedage (hvis du får brug for det senere)
    df["ugedag"] = df["dato"].dt.day_name().map(DANSKE_UGEDAGE)

    # Antal
    df["antal"] = pd.to_numeric(df[kol_antal], errors="coerce").fillna(0)

    # Ydelseskode
    df["ydelseskode"] = df[kol_kode].astype(str)

    return df


# ---------------------------------------------------------
# Periodefiltrering (år/måned)
# ---------------------------------------------------------

def filtrer_perioder(df, start_month, start_year, months):
    slut_month = start_month + months - 1

    # P1
    p1 = df[
        (df["år"] == start_year) &
        (df["måned"].between(start_month, slut_month))
    ].copy()
    p1["periode"] = "P1"

    # P2
    p2 = df[
        (df["år"] == start_year + 1) &
        (df["måned"].between(start_month, slut_month))
    ].copy()
    p2["periode"] = "P2"

    df_all = pd.concat([p1, p2], ignore_index=True)

    if df_all.empty:
        st.warning("Ingen data i de valgte perioder.")
    return df_all


# ---------------------------------------------------------
# Grafer (x-akse = måned/år-label)
# ---------------------------------------------------------

def graf_stacked_0101_0120_0125(df_all):
    df = df_all.copy()
    df["gruppe"] = None
    df.loc[df["ydelseskode"] == "0120", "gruppe"] = "0120"
    df.loc[df["ydelseskode"].isin(["0101", "0125"]), "gruppe"] = "0101+0125"
    df = df[df["gruppe"].notna()]

    if df.empty:
        return None

    grp = (
        df.groupby(["periode", "år", "måned", "gruppe"])["antal"]
        .sum()
        .reset_index()
    )
    grp["label"] = grp.apply(lambda r: måned_label(r["år"], r["måned"]), axis=1)

    fig = px.bar(
        grp,
        x="label",
        y="antal",
        color="gruppe",
        barmode="stack",
        title="0101 + 0120 + 0125 (stacked)",
    )
    return fig


def graf_ydelser_pr_måned(df_all, koder, title):
    df = df_all[df_all["ydelseskode"].isin(koder)].copy()
    if df.empty:
        return None

    grp = (
        df.groupby(["periode", "år", "måned"])["antal"]
        .sum()
        .reset_index()
    )
    grp["label"] = grp.apply(lambda r: måned_label(r["år"], r["måned"]), axis=1)

    fig = px.bar(
        grp,
        x="label",
        y="antal",
        color="periode",
        barmode="group",
        title=title,
    )
    return fig


def graf_ugedage(df_all):
    df = df_all[df_all["ydelseskode"].isin(["0101", "0120", "0125"])].copy()
    if df.empty:
        return None

    grp = (
        df.groupby(["periode", "år", "måned"])["antal"]
        .sum()
        .reset_index()
    )
    grp["label"] = grp.apply(lambda r: måned_label(r["år"], r["måned"]), axis=1)

    fig = px.bar(
        grp,
        x="label",
        y="antal",
        color="periode",
        barmode="group",
        title="Fordeling på ugedage (månedssummer)",
    )
    return fig


# ---------------------------------------------------------
# PDF (simpel, tekstbaseret)
# ---------------------------------------------------------

def lav_pdf(figures):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    for fig in figures:
        if fig is None:
            continue
        html = fig.to_html()
        pdf.add_page()
        pdf.set_font("Arial", size=8)
        pdf.multi_cell(0, 4, html)

    return pdf.output(dest="S").encode("latin1")


# ---------------------------------------------------------
# UI
# ---------------------------------------------------------

st.title("Analyse af ydelser")

uploaded_file = st.file_uploader("Upload Excel-fil", type=["xlsx"])

if uploaded_file:
    df = load_data(uploaded_file)

    col1, col2, col3 = st.columns(3)

    with col1:
        start_month = st.selectbox(
            "Startmåned",
            list(range(1, 13)),
            format_func=lambda m: DANSKE_MÅNEDER_KORT[m],
        )

    with col2:
        år_values = sorted(df["år"].unique())
        if not år_values:
            st.error("Ingen gyldige år fundet i data.")
            st.stop()
        start_year = st.selectbox("Startår", år_values)

    with col3:
        months = st.selectbox("Antal måneder", [3, 6, 9, 12])

    df_all = filtrer_perioder(df, start_month, start_year, months)

    if df_all.empty:
        st.stop()

    figs = []

    fig1 = graf_stacked_0101_0120_0125(df_all)
    if fig1:
        st.plotly_chart(fig1, use_container_width=True)
        figs.append(fig1)

    fig2 = graf_ydelser_pr_måned(df_all, ["2101"], "2101 pr. måned")
    if fig2:
        st.plotly_chart(fig2, use_container_width=True)
        figs.append(fig2)

    fig3 = graf_ydelser_pr_måned(df_all, ["7156"], "7156 pr. måned")
    if fig3:
        st.plotly_chart(fig3, use_container_width=True)
        figs.append(fig3)

    fig4 = graf_ydelser_pr_måned(df_all, ["2149"], "2149 pr. måned")
    if fig4:
        st.plotly_chart(fig4, use_container_width=True)
        figs.append(fig4)

    fig5 = graf_ydelser_pr_måned(
        df_all,
        ["0411", "0421", "0431", "0491"],
        "0411+0421+0431+0491 pr. måned",
    )
    if fig5:
        st.plotly_chart(fig5, use_container_width=True)
        figs.append(fig5)

    fig6 = graf_ugedage(df_all)
    if fig6:
        st.plotly_chart(fig6, use_container_width=True)
        figs.append(fig6)

    try:
        pdf_bytes = lav_pdf(figs)
        st.download_button(
            "Download PDF",
            data=pdf_bytes,
            file_name="ydelser.pdf",
            mime="application/pdf",
        )
    except Exception:
        st.info("PDF kunne ikke genereres i dette miljø.")
