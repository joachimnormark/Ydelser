import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO
from fpdf import FPDF
import calendar

st.set_page_config(page_title="Ydelsesanalyse", layout="wide")

# ---------------------------------------------------------
# Dataindlæsning
# ---------------------------------------------------------

def load_data(uploaded_file):
    df = pd.read_excel(uploaded_file)

    # Standardiser kolonnenavne
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # Find dato-kolonne
    date_col = None
    for col in df.columns:
        if "dato" in col:
            date_col = col
            break

    if date_col is None:
        st.error("Kunne ikke finde en kolonne med dato i filen.")
        st.stop()

    # Robust dato-konvertering
    try:
        df["dato"] = pd.to_datetime(df[date_col], unit="d", origin="1899-12-30")
    except Exception:
        df["dato"] = pd.to_datetime(df[date_col], errors="coerce")

    df = df.dropna(subset=["dato"])

    # Ekstra kolonner
    df["år"] = df["dato"].dt.year.astype(int)
    df["måned"] = df["dato"].dt.month.astype(int)
    df["label"] = df["dato"].dt.strftime("%b %y")

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

    # Antal skal være numerisk
    if "antal" not in df.columns:
        st.error("Kolonnen 'antal' mangler i datasættet.")
        st.stop()

    df["antal"] = pd.to_numeric(df["antal"], errors="coerce").fillna(0)

    # Ydelseskode skal findes
    if "ydelseskode" not in df.columns:
        st.error("Kolonnen 'ydelseskode' mangler i datasættet.")
        st.stop()

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

    df_all = pd.concat([df_p1, df_p2], ignore_index=True)

    return df_all, p1_start, p1_slut, p2_start, p2_slut

# ---------------------------------------------------------
# Grafer
# ---------------------------------------------------------

def graf_stacked_0101_0120_0125(df_all):
    df = df_all.copy()
    df["gruppe"] = None
    df.loc[df["ydelseskode"] == "0120", "gruppe"] = "0120"
    df.loc[df["ydelseskode"].isin(["0101", "0125"]), "gruppe"] = "0101+0125"
    df = df[df["gruppe"].notna()]

    grp = (
        df.groupby(["periode", "år", "måned", "label", "gruppe"])["antal"]
        .sum()
        .reset_index()
    )

    pivot = grp.pivot_table(
        index=["periode", "år", "måned", "label"],
        columns="gruppe",
        values="antal",
        fill_value=0,
    ).reset_index()

    for col in ["0120", "0101+0125"]:
        if col not in pivot.columns:
            pivot[col] = 0

    pivot = pivot.sort_values(["år", "måned", "periode"])

    fig = px.bar(
        pivot,
        x="label",
        y=["0120", "0101+0125"],
        title="0101 + 0120 + 0125 (stacked, 0120 nederst)",
        color_discrete_map={"0120": "red", "0101+0125": "blue"},
    )
    return fig


def graf_ydelser_pr_måned(df_all, koder, title):
    df = df_all[df_all["ydelseskode"].isin(koder)].copy()

    grp = (
        df.groupby(["periode", "år", "måned", "label"])["antal"]
        .sum()
        .reset_index()
    )

    grp = grp.sort_values(["år", "måned", "periode"])

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
    koder = ["0101", "0120", "0125"]
    df = df_all[df_all["ydelseskode"].isin(koder)].copy()
    df = df[df["ugedag"].isin(["Mandag", "Tirsdag", "Onsdag", "Torsdag", "Fredag"])]

    grp = (
        df.groupby(["periode", "ugedag"])["antal"]
        .sum()
        .reset_index()
    )

    order = ["Mandag", "Tirsdag", "Onsdag", "Torsdag", "Fredag"]
    grp["ugedag"] = pd.Categorical(grp["ugedag"], order)

    fig = px.bar(
        grp,
        x="ugedag",
        y="antal",
        color="periode",
        barmode="group",
        title="Fordeling på ugedage (0101+0120+0125)",
    )
    return fig

# ---------------------------------------------------------
# PDF – failsafe (ingen crash hvis Plotly/Kaleido mangler)
# ---------------------------------------------------------

def lav_pdf(figures):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    for fig in figures:
        pdf.add_page()
        img = BytesIO()
        # Denne del kan fejle hvis Plotly/Kaleido ikke har en engine
        fig.write_image(img, format="png")
        img.seek(0)
        pdf.image(img, x=10, y=10, w=180)

    return pdf.output(dest="S").encode("latin1")

# ---------------------------------------------------------
# UI
# ---------------------------------------------------------

st.title("Analyse af ydelser")

uploaded_file = st.file_uploader("Upload Excel-fil", type=["xlsx"])

if uploaded_file:
    df = load_data(uploaded_file)
    st.success("Fil indlæst!")

    col1, col2, col3 = st.columns(3)

    with col1:
        start_month = st.selectbox(
            "Startmåned",
            list(range(1, 13)),
            format_func=lambda m: calendar.month_name[m],
        )

    with col2:
        start_year = st.selectbox("Startår", sorted(df["år"].unique()))

    with col3:
        months = st.selectbox("Antal måneder", [3, 6, 9, 12])

    df_all, p1s, p1e, p2s, p2e = filtrer_perioder(df, start_month, start_year, months)

    st.write(f"**Periode 1:** {p1s.date()} → {p1e.date()}")
    st.write(f"**Periode 2:** {p2s.date()} → {p2e.date()}")

    st.header("Grafer")

    figs = []

    fig1 = graf_stacked_0101_0120_0125(df_all)
    st.plotly_chart(fig1, use_container_width=True)
    figs.append(fig1)

    fig2 = graf_ydelser_pr_måned(df_all, ["2101"], "2101 pr. måned")
    st.plotly_chart(fig2, use_container_width=True)
    figs.append(fig2)

    fig3 = graf_ydelser_pr_måned(df_all, ["7156"], "7156 pr. måned")
    st.plotly_chart(fig3, use_container_width=True)
    figs.append(fig3)

    fig4 = graf_ydelser_pr_måned(df_all, ["2149"], "2149 pr. måned")
    st.plotly_chart(fig4, use_container_width=True)
    figs.append(fig4)

    fig5 = graf_ydelser_pr_måned(
        df_all,
        ["0411", "0421", "0431", "0491"],
        "0411+0421+0431+0491 pr. måned",
    )
    st.plotly_chart(fig5, use_container_width=True)
    figs.append(fig5)

    fig6 = graf_ugedage(df_all)
    st.plotly_chart(fig6, use_container_width=True)
    figs.append(fig6)

    # PDF – prøv, men lad ikke appen crashe
    try:
        pdf_bytes = lav_pdf(figs)
        st.download_button(
            "Download PDF med alle grafer",
            data=pdf_bytes,
            file_name="ydelser.pdf",
            mime="application/pdf",
        )
    except Exception:
        st.info(
            "PDF-generering er ikke tilgængelig i dette miljø (Plotly/Kaleido mangler en grafik‑engine). "
            "Graferne kan stadig ses og evt. gemmes manuelt."
        )
