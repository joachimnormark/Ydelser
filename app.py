import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from fpdf import FPDF
import io

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

    df["ydelseskode"] = (
        df[kol_kode]
        .astype(str)
        .str.replace(r"\D", "", regex=True)
        .str.zfill(4)
    )

    return df


# ---------------------------------------------------------
# PERIODEFILTRERING
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
# HJÆLPEFUNKTION: Numerisk x-akse + labels
# ---------------------------------------------------------

def lav_x_akse(grp, start_month):
    grp["relativ_måned"] = (grp["måned"] - start_month) % 12
    grp["x"] = grp["relativ_måned"] * 2 + grp["periode"].map({"P1": -0.2, "P2": 0.2})
    grp["labelpos"] = grp["relativ_måned"] * 2
    return grp


# ---------------------------------------------------------
# GRAF: 0101 + 0120 + 0125 (stacked)
# ---------------------------------------------------------

def graf_stacked(df_all, start_month):
    df = df_all.copy()

    df["gruppe"] = None
    df.loc[df["ydelseskode"] == "0120", "gruppe"] = "0120"
    df.loc[df["ydelseskode"].isin(["0101", "0125"]), "gruppe"] = "0101+0125"
    df = df[df["gruppe"].notna()]

    if df.empty:
        return None

    grp = df.groupby(["periode", "år", "måned", "gruppe"])["antal"].sum().reset_index()

    grp = lav_x_akse(grp, start_month)

    # Beregn procentandel for 0120
    total = grp.groupby(["periode", "år", "måned"])["antal"].sum().reset_index()
    total = total.rename(columns={"antal": "total"})

    df0120 = grp[grp["gruppe"] == "0120"][["periode", "år", "måned", "antal"]]
    df0120 = df0120.rename(columns={"antal": "antal_0120"})

    pct = pd.merge(total, df0120, on=["periode", "år", "måned"], how="left")
    pct["pct_0120"] = (pct["antal_0120"] / pct["total"] * 100).round(1).fillna(0)

    grp = pd.merge(grp, pct[["periode", "år", "måned", "pct_0120"]], on=["periode", "år", "måned"], how="left")

    # 0120 nederst
    grp["gruppe"] = pd.Categorical(grp["gruppe"], categories=["0120", "0101+0125"], ordered=True)

    fig = go.Figure()

    # 0120 nederst (rød)
    df_red = grp[grp["gruppe"] == "0120"]
    fig.add_bar(
        x=df_red["x"],
        y=df_red["antal"],
        name="0120",
        marker_color="red",
    )

    # 0101+0125 øverst (blå)
    df_blue = grp[grp["gruppe"] == "0101+0125"]
    fig.add_bar(
        x=df_blue["x"],
        y=df_blue["antal"],
        name="0101+0125",
        marker_color="steelblue",
    )

    # Procenttal
    for _, row in df_red.iterrows():
        fig.add_annotation(
            x=row["x"],
            y=0,
            text=f"{row['pct_0120']}%",
            showarrow=False,
            yshift=-20,
            font=dict(size=10, color="red"),
        )

    # Labels
    labels = grp.groupby("labelpos").first().reset_index()
    fig.update_xaxes(
        tickmode="array",
        tickvals=labels["labelpos"],
        ticktext=[måned_label(r["år"], r["måned"]) for _, r in labels.iterrows()],
    )

    fig.update_layout(
        title="0101 + 0120 + 0125 (stacked)",
        barmode="stack",
        bargap=0.05,
        height=500,
    )

    return fig


# ---------------------------------------------------------
# GRAF: Øvrige ydelser (parvis tætstående)
# ---------------------------------------------------------

def graf_ydelser(df_all, koder, title, start_month):
    df = df_all[df_all["ydelseskode"].isin(koder)].copy()
    if df.empty:
        return None

    grp = df.groupby(["periode", "år", "måned"])["antal"].sum().reset_index()

    grp = lav_x_akse(grp, start_month)

    fig = go.Figure()

    # P1 = blå
    df_p1 = grp[grp["periode"] == "P1"]
    fig.add_bar(
        x=df_p1["x"],
        y=df_p1["antal"],
        name="P1",
        marker_color="blue",
    )

    # P2 = orange
    df_p2 = grp[grp["periode"] == "P2"]
    fig.add_bar(
        x=df_p2["x"],
        y=df_p2["antal"],
        name="P2",
        marker_color="orange",
    )

    labels = grp.groupby("labelpos").first().reset_index()
    fig.update_xaxes(
        tickmode="array",
        tickvals=labels["labelpos"],
        ticktext=[måned_label(r["år"], r["måned"]) for _, r in labels.iterrows()],
    )

    fig.update_layout(
        title=title,
        barmode="group",
        bargap=0.05,
        height=500,
    )

    return fig


# ---------------------------------------------------------
# PDF (virker i Streamlit Cloud)
# ---------------------------------------------------------

def lav_pdf(figures):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    for fig in figures:
        if fig is None:
            continue

        buf = io.BytesIO()
        fig.write_image(buf, format="png")
        buf.seek(0)

        pdf.add_page()
        pdf.image(buf, x=10, y=10, w=180)

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
        graf_stacked(df_all, start_month),
        graf_ydelser(df_all, ["2101"], "2101 pr. måned", start_month),
        graf_ydelser(df_all, ["7156"], "7156 pr. måned", start_month),
        graf_ydelser(df_all, ["2149"], "2149 pr. måned", start_month),
        graf_ydelser(df_all, ["0411", "0421", "0431", "0491"], "0411+0421+0431+0491 pr. måned", start_month),
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
# DEBUG (kommenteret ud)
# ---------------------------------------------------------

# st.write("DEBUG – rå data (df):", len(df))
# st.write(df.head(20))
# st.write("DEBUG – filtreret data (df_all):", len(df_all))
# st.write(df_all.head(20))
# st.write("DEBUG – unikke ydelseskoder:", sorted(df_all["ydelseskode"].unique()))
