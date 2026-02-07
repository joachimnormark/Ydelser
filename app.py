import streamlit as st
import pandas as pd
import plotly.express as px
from fpdf import FPDF

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
# DATAINDLÆSNING
# ---------------------------------------------------------

def load_data(uploaded_file):
    df = pd.read_excel(uploaded_file)

    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    kol_dato = [c for c in df.columns if "dato" in c][0]
    kol_kode = [c for c in df.columns if "ydelseskode" in c][0]
    kol_antal = [c for c in df.columns if "antal" in c][0]

    if not pd.api.types.is_datetime64_any_dtype(df[kol_dato]):
        df[kol_dato] = pd.to_datetime(df[kol_dato], errors="coerce")

    df = df.dropna(subset=[kol_dato])

    df["dato"] = df[kol_dato]
    df["år"] = df["dato"].dt.year
    df["måned"] = df["dato"].dt.month

    df["antal"] = pd.to_numeric(df[kol_antal], errors="coerce").fillna(0)

    # Paddede ydelseskoder (meget vigtigt)
    df["ydelseskode"] = (
        df[kol_kode]
        .astype(str)
        .str.replace(r"\D", "", regex=True)
        .str.zfill(4)
    )

    return df


# ---------------------------------------------------------
# PERIODEFILTRERING (PERIODE-NØGLE)
# ---------------------------------------------------------

def filtrer_perioder(df, start_month, start_year, months):
    df["periode_key"] = df["år"] * 12 + df["måned"]

    start_key = start_year * 12 + start_month
    slut_key = start_key + months - 1

    p1 = df[(df["periode_key"] >= start_key) & (df["periode_key"] <= slut_key)].copy()
    p1["periode"] = "P1"

    p2_start_key = start_key + 12
    p2_slut_key = slut_key + 12

    p2 = df[(df["periode_key"] >= p2_start_key) & (df["periode_key"] <= p2_slut_key)].copy()
    p2["periode"] = "P2"

    return pd.concat([p1, p2], ignore_index=True)


# ---------------------------------------------------------
# GRAFER (med korrekt rækkefølge)
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

    # Sortering: M1-P1, M1-P2, M2-P1, M2-P2 ...
    grp["sort_key"] = grp["måned"] * 10 + grp["periode"].map({"P1": 1, "P2": 2})
    grp = grp.sort_values("sort_key")

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

    grp["sort_key"] = grp["måned"] * 10 + grp["periode"].map({"P1": 1, "P2": 2})
    grp = grp.sort_values("sort_key")

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


# ---------------------------------------------------------
# DEBUG (kommenteret ud – kan aktiveres ved behov)
# ---------------------------------------------------------

# st.write("DEBUG – rå data (df):", len(df))
# st.write(df.head(20))
# st.write("DEBUG – filtreret data (df_all):", len(df_all))
# st.write(df_all.head(20))
# st.write("DEBUG – unikke ydelseskoder:", sorted(df_all["ydelseskode"].unique()))
