import streamlit as st
import pandas as pd
import plotly.express as px
from fpdf import FPDF
import calendar
import re

st.set_page_config(page_title="Ydelsesanalyse", layout="wide")

# ---------------------------------------------------------
# DANSKE MÅNEDER
# ---------------------------------------------------------

DANSKE_MÅNEDER_KORT = {
    1: "jan", 2: "feb", 3: "mar", 4: "apr",
    5: "maj", 6: "jun", 7: "jul", 8: "aug",
    9: "sep", 10: "okt", 11: "nov", 12: "dec",
}

def måned_label(år, måned):
    return f"{DANSKE_MÅNEDER_KORT[måned]} {str(int(år))[-2:]}"


# ---------------------------------------------------------
# ROBUST PARSER FOR dd.mm.yy OG ddmmyy
# ---------------------------------------------------------

def parse_dato(series):
    cleaned = series.astype(str).str.strip()

    # Fjern alt undtagen tal og punktummer
    cleaned = cleaned.str.replace(r"[^0-9\.]", "", regex=True)

    parsed_dates = []

    for value in cleaned:
        if value == "":
            parsed_dates.append(pd.NaT)
            continue

        # CASE 1: ddmmyy (fx 020124)
        if re.fullmatch(r"\d{6}", value):
            try:
                d = value[:2]
                m = value[2:4]
                y = value[4:]
                y = "20" + y  # 24 → 2024
                parsed_dates.append(pd.to_datetime(f"{d}.{m}.{y}", format="%d.%m.%Y"))
                continue
            except:
                parsed_dates.append(pd.NaT)
                continue

        # CASE 2: dd.mm.yy eller d.m.yy
        try:
            parsed_dates.append(pd.to_datetime(value, format="%d.%m.%y"))
            continue
        except:
            pass

        # CASE 3: dd.mm.yyyy
        try:
            parsed_dates.append(pd.to_datetime(value, format="%d.%m.%Y"))
            continue
        except:
            parsed_dates.append(pd.NaT)

    return pd.to_datetime(parsed_dates, errors="coerce")


# ---------------------------------------------------------
# DATAINDLÆSNING
# ---------------------------------------------------------

def load_data(uploaded_file):
    df = pd.read_excel(uploaded_file)

    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    kol_dato = [c for c in df.columns if "dato" in c][0]
    kol_kode = [c for c in df.columns if "ydelseskode" in c][0]
    kol_antal = [c for c in df.columns if "antal" in c][0]

    df["dato"] = parse_dato(df[kol_dato])
    df = df.dropna(subset=["dato"])

    if df.empty:
        st.error("Ingen gyldige datoer kunne konverteres fra filen.")
        st.stop()

    df["år"] = df["dato"].dt.year
    df["måned"] = df["dato"].dt.month

    df["antal"] = pd.to_numeric(df[kol_antal], errors="coerce").fillna(0)
    df["ydelseskode"] = df[kol_kode].astype(str)

    return df


# ---------------------------------------------------------
# PERIODEFILTRERING
# ---------------------------------------------------------

def filtrer_perioder(df, start_month, start_year, months):
    slut_month = start_month + months - 1

    p1 = df[
        (df["år"] == start_year) &
        (df["måned"].between(start_month, slut_month))
    ].copy()
    p1["periode"] = "P1"

    p2 = df[
        (df["år"] == start_year + 1) &
        (df["måned"].between(start_month, slut_month))
    ].copy()
    p2["periode"] = "P2"

    return pd.concat([p1, p2], ignore_index=True)


# ---------------------------------------------------------
# GRAFER
# ---------------------------------------------------------

def graf_stacked(df_all):
    df = df_all.copy()
    df["gruppe"] = None
    df.loc[df["ydelseskode"] == "0120", "gruppe"] = "0120"
    df.loc[df["ydelseskode"].isin(["0101", "0125"]), "gruppe"] = "0101+0125"
    df = df[df["gruppe"].notna()]

    if df.empty:
        return None

    grp = df.groupby(["periode", "år", "måned", "gruppe"])["antal"].sum().reset_index()
    grp["label"] = grp.apply(lambda r: måned_label(r["år"], r["måned"]), axis=1)

    return px.bar(
        grp,
        x="label",
        y="antal",
        color="gruppe",
        barmode="stack",
        title="0101 + 0120 + 0125 (stacked)",
    )


def graf_ydelser(df_all, koder, title):
    df = df_all[df_all["ydelseskode"].isin(koder)].copy()
    if df.empty:
        return None

    grp = df.groupby(["periode", "år", "måned"])["antal"].sum().reset_index()
    grp["label"] = grp.apply(lambda r: måned_label(r["år"], r["måned"]), axis=1)

    return px.bar(
        grp,
        x="label",
        y="antal",
        color="periode",
        barmode="group",
        title=title,
    )


# ---------------------------------------------------------
# PDF
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
        start_year = st.selectbox("Startår", sorted(df["år"].unique()))

    with col3:
        months = st.selectbox("Antal måneder", [3, 6, 9, 12])

    df_all = filtrer_perioder(df, start_month, start_year, months)

    figs = []

    for fig in [
        graf_stacked(df_all),
        graf_ydelser(df_all, ["2101"], "2101 pr. måned"),
        graf_ydelser(df_all, ["7156"], "7156 pr. måned"),
        graf_ydelser(df_all, ["2149"], "2149 pr. måned"),
        graf_ydelser(df_all, ["0411", "0421", "0431", "0491"], "0411+0421+0431+0491 pr. måned"),
    ]:
        if fig:
            st.plotly_chart(fig, use_container_width=True)
            figs.append(fig)

    try:
        pdf_bytes = lav_pdf(figs)
        st.download_button("Download PDF", data=pdf_bytes, file_name="ydelser.pdf", mime="application/pdf")
    except:
        st.info("PDF kunne ikke genereres i dette miljø.")
