import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO
from fpdf import FPDF
import calendar

st.set_page_config(page_title="Ydelsesanalyse", layout="wide")

# ---------------------------------------------------------
# SUPER-ROBUST DATO → ÅR/MÅNED (uden datetime)
# ---------------------------------------------------------

def excel_seriedato_til_aar_maaned(series):
    """
    Konverterer Excel-seriedatoer til år og måned uden at bruge datetime.
    Håndterer:
    - ints
    - floats
    - tekst
    - whitespace
    - kommaer
    - punktummer
    - NaN
    """

    # Alt til tekst
    s = series.astype(str)

    # Fjern whitespace
    s = s.str.strip()

    # Fjern tusindtals-separatorer
    s = s.str.replace(".", "", regex=False)
    s = s.str.replace(",", "", regex=False)

    # Fjern alt der ikke er tal
    s = s.str.replace(r"[^0-9]", "", regex=True)

    # Tving til numerisk
    s = pd.to_numeric(s, errors="coerce")

    # Excel 1900-systemet: dag 1 = 1899-12-31
    base = pd.Timestamp("1899-12-30")
    datoer = base + pd.to_timedelta(s, unit="D")

    # Udtræk år og måned
    aar = datoer.dt.year
    maaned = datoer.dt.month

    return aar, maaned


# ---------------------------------------------------------
# DATAINDLÆSNING
# ---------------------------------------------------------

def load_data(uploaded_file):
    df = pd.read_excel(uploaded_file)

    # Standardiser kolonnenavne
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # Find kolonner
    kol_dato = [c for c in df.columns if "dato" in c][0]
    kol_kode = [c for c in df.columns if "ydelseskode" in c][0]
    kol_antal = [c for c in df.columns if "antal" in c][0]

    # Udtræk år og måned
    df["år"], df["måned"] = excel_seriedato_til_aar_maaned(df[kol_dato])

    # Fjern rækker uden gyldig dato
    df = df.dropna(subset=["år", "måned"])

    # Antal
    df["antal"] = pd.to_numeric(df[kol_antal], errors="coerce").fillna(0)

    # Ydelseskode
    df["ydelseskode"] = df[kol_kode].astype(str)

    return df


# ---------------------------------------------------------
# PERIODEFILTRERING
# ---------------------------------------------------------

def filtrer_perioder(df, start_month, start_year, months):
    # Periode 1
    p1 = df[
        (df["år"] == start_year) &
        (df["måned"].between(start_month, start_month + months - 1))
    ].copy()
    p1["periode"] = "P1"

    # Periode 2
    p2 = df[
        (df["år"] == start_year + 1) &
        (df["måned"].between(start_month, start_month + months - 1))
    ].copy()
    p2["periode"] = "P2"

    return pd.concat([p1, p2], ignore_index=True)


# ---------------------------------------------------------
# GRAFER
# ---------------------------------------------------------

def måned_label(år, måned):
    return f"{calendar.month_abbr[måned]} {str(år)[-2:]}"


def graf_stacked(df_all):
    df = df_all.copy()
    df["gruppe"] = None
    df.loc[df["ydelseskode"] == "0120", "gruppe"] = "0120"
    df.loc[df["ydelseskode"].isin(["0101", "0125"]), "gruppe"] = "0101+0125"
    df = df[df["gruppe"].notna()]

    grp = df.groupby(["periode", "år", "måned", "gruppe"])["antal"].sum().reset_index()
    grp["label"] = grp.apply(lambda r: måned_label(r["år"], r["måned"]), axis=1)

    fig = px.bar(
        grp,
        x="label",
        y="antal",
        color="gruppe",
        barmode="stack",
        title="0101 + 0120 + 0125 (stacked)"
    )
    return fig


def graf_ydelser(df_all, koder, title):
    df = df_all[df_all["ydelseskode"].isin(koder)].copy()

    grp = df.groupby(["periode", "år", "måned"])["antal"].sum().reset_index()
    grp["label"] = grp.apply(lambda r: måned_label(r["år"], r["måned"]), axis=1)

    fig = px.bar(
        grp,
        x="label",
        y="antal",
        color="periode",
        barmode="group",
        title=title
    )
    return fig


def graf_ugedage(df_all):
    df = df_all[df_all["ydelseskode"].isin(["0101", "0120", "0125"])].copy()

    grp = df.groupby(["periode", "år", "måned"])["antal"].sum().reset_index()
    grp["label"] = grp.apply(lambda r: måned_label(r["år"], r["måned"]), axis=1)

    fig = px.bar(
        grp,
        x="label",
        y="antal",
        color="periode",
        barmode="group",
        title="Fordeling på ugedage"
    )
    return fig


# ---------------------------------------------------------
# PDF (uden Chrome/Kaleido)
# ---------------------------------------------------------

def lav_pdf(figures):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    for fig in figures:
        html = fig.to_html()
        pdf.add_page()
        pdf.set_font("Arial", size=10)
        pdf.multi_cell(0, 5, html)

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
        start_month = st.selectbox("Startmåned", list(range(1, 13)), format_func=lambda m: calendar.month_name[m])

    with col2:
        start_year = st.selectbox("Startår", sorted(df["år"].unique()))

    with col3:
        months = st.selectbox("Antal måneder", [3, 6, 9, 12])

    df_all = filtrer_perioder(df, start_month, start_year, months)

    figs = []

    fig1 = graf_stacked(df_all)
    st.plotly_chart(fig1, use_container_width=True)
    figs.append(fig1)

    fig2 = graf_ydelser(df_all, ["2101"], "2101 pr. måned")
    st.plotly_chart(fig2, use_container_width=True)
    figs.append(fig2)

    fig3 = graf_ydelser(df_all, ["7156"], "7156 pr. måned")
    st.plotly_chart(fig3, use_container_width=True)
    figs.append(fig3)

    fig4 = graf_ydelser(df_all, ["2149"], "2149 pr. måned")
    st.plotly_chart(fig4, use_container_width=True)
    figs.append(fig4)

    fig5 = graf_ydelser(df_all, ["0411", "0421", "0431", "0491"], "0411+0421+0431+0491 pr. måned")
    st.plotly_chart(fig5, use_container_width=True)
    figs.append(fig5)

    fig6 = graf_ugedage(df_all)
    st.plotly_chart(fig6, use_container_width=True)
    figs.append(fig6)

    try:
        pdf_bytes = lav_pdf(figs)
        st.download_button("Download PDF", data=pdf_bytes, file_name="ydelser.pdf", mime="application/pdf")
    except Exception:
        st.info("PDF kunne ikke genereres i dette miljø.")
