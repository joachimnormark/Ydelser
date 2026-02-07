import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO
from fpdf import FPDF
import calendar

st.set_page_config(page_title="Ydelsesanalyse", layout="wide")

# ---------------------------------------------------------
# Robust dato-konvertering
# ---------------------------------------------------------

def konverter_excel_datoer(series):
    """
    Konverterer en kolonne med Excel-seriedatoer til datetime.
    Håndterer:
    - ints
    - floats
    - tekst der ligner tal
    - NaN
    """

    # Tving til numerisk
    s = pd.to_numeric(series, errors="coerce")

    # Fjern NaN
    s = s.dropna()

    # Hvis alt er NaN → returnér tom serie
    if s.empty:
        return pd.Series([pd.NaT] * len(series))

    # Windows Excel-datoer (1900-systemet)
    return pd.to_datetime(s, unit="d", origin="1899-12-30")


# ---------------------------------------------------------
# Dataindlæsning
# ---------------------------------------------------------

def load_data(uploaded_file):
    df = pd.read_excel(uploaded_file)

    # Standardiser kolonnenavne
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # Find kolonner
    kol_dato = [c for c in df.columns if "dato" in c][0]
    kol_kode = [c for c in df.columns if "ydelseskode" in c][0]
    kol_antal = [c for c in df.columns if "antal" in c][0]

    # Konverter datoer
    df["dato"] = konverter_excel_datoer(df[kol_dato])

    # Fjern rækker uden gyldig dato
    df = df.dropna(subset=["dato"])

    # Ekstra kolonner
    df["år"] = df["dato"].dt.year
    df["måned"] = df["dato"].dt.month

    # Ugedage på dansk
    df["ugedag"] = df["dato"].dt.day_name()
    oversæt = {
        "Monday": "Mandag",
        "Tuesday": "Tirsdag",
        "Wednesday": "Onsdag",
        "Thursday": "Torsdag",
        "Friday": "Fredag",
        "Saturday": "Lørdag",
        "Sunday": "Søndag",
    }
    df["ugedag"] = df["ugedag"].map(oversæt)

    # Antal
    df["antal"] = pd.to_numeric(df[kol_antal], errors="coerce").fillna(0)

    # Ydelseskode
    df["ydelseskode"] = df[kol_kode].astype(str)

    return df


# ---------------------------------------------------------
# Periodefiltrering
# ---------------------------------------------------------

def filtrer_perioder(df, start_month, start_year, months):
    p1_start = pd.Timestamp(start_year, start_month, 1)
    p1_slut = p1_start + pd.DateOffset(months=months) - pd.DateOffset(days=1)

    p2_start = pd.Timestamp(start_year + 1, start_month, 1)
    p2_slut = p2_start + pd.DateOffset(months=months) - pd.DateOffset(days=1)

    df_p1 = df[(df["dato"] >= p1_start) & (df["dato"] <= p1_slut)].copy()
    df_p1["periode"] = "P1"

    df_p2 = df[(df["dato"] >= p2_start) & (df["dato"] <= p2_slut)].copy()
    df_p2["periode"] = "P2"

    return pd.concat([df_p1, df_p2], ignore_index=True), p1_start, p1_slut, p2_start, p2_slut


# ---------------------------------------------------------
# Grafer
# ---------------------------------------------------------

def graf_stacked(df_all):
    df = df_all.copy()
    df["gruppe"] = None
    df.loc[df["ydelseskode"] == "0120", "gruppe"] = "0120"
    df.loc[df["ydelseskode"].isin(["0101", "0125"]), "gruppe"] = "0101+0125"
    df = df[df["gruppe"].notna()]

    grp = df.groupby(["periode", "dato", "gruppe"])["antal"].sum().reset_index()

    pivot = grp.pivot_table(
        index=["periode", "dato"],
        columns="gruppe",
        values="antal",
        fill_value=0
    ).reset_index()

    for col in ["0120", "0101+0125"]:
        if col not in pivot.columns:
            pivot[col] = 0

    pivot = pivot.sort_values("dato")

    fig = px.bar(
        pivot,
        x="dato",
        y=["0120", "0101+0125"],
        title="0101 + 0120 + 0125 (stacked)",
        color_discrete_map={"0120": "red", "0101+0125": "blue"},
    )

    fig.update_xaxes(tickformat="%b %y")
    return fig


def graf_ydelser(df_all, koder, title):
    df = df_all[df_all["ydelseskode"].isin(koder)].copy()

    grp = df.groupby(["periode", "dato"])["antal"].sum().reset_index()
    grp = grp.sort_values("dato")

    fig = px.bar(
        grp,
        x="dato",
        y="antal",
        color="periode",
        title=title,
        barmode="group"
    )

    fig.update_xaxes(tickformat="%b %y")
    return fig


def graf_ugedage(df_all):
    df = df_all[df_all["ydelseskode"].isin(["0101", "0120", "0125"])].copy()
    df = df[df["ugedag"].isin(["Mandag", "Tirsdag", "Onsdag", "Torsdag", "Fredag"])]

    grp = df.groupby(["periode", "ugedag"])["antal"].sum().reset_index()

    order = ["Mandag", "Tirsdag", "Onsdag", "Torsdag", "Fredag"]
    grp["ugedag"] = pd.Categorical(grp["ugedag"], order)

    fig = px.bar(
        grp,
        x="ugedag",
        y="antal",
        color="periode",
        title="Fordeling på ugedage"
    )
    return fig


# ---------------------------------------------------------
# PDF uden Chrome/Kaleido
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

    df_all, p1s, p1e, p2s, p2e = filtrer_perioder(df, start_month, start_year, months)

    st.write(f"**Periode 1:** {p1s.date()} → {p1e.date()}")
    st.write(f"**Periode 2:** {p2s.date()} → {p2e.date()}")

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
