import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO
from fpdf import FPDF
import calendar

st.set_page_config(page_title="Ydelsesanalyse", layout="wide")

# ---------------------------------------------------------
# Hjælpefunktioner
# ---------------------------------------------------------

def load_data(uploaded_file):
    df = pd.read_excel(uploaded_file)

    # Standardiser kolonnenavne
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # Find dato-kolonnen
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
        # Forsøg Excel-serienumre
        df["dato"] = pd.to_datetime(df[date_col], unit="d", origin="1899-12-30")
    except Exception:
        # Hvis det fejler → prøv almindelig dato
        df["dato"] = pd.to_datetime(df[date_col], errors="coerce")

    # Fjern ugyldige datoer
    df = df.dropna(subset=["dato"])

    # Ekstra kolonner
    df["år"] = df["dato"].dt.year
    df["måned"] = df["dato"].dt.month
    df["ugedag"] = df["dato"].dt.day_name(locale="da_DK")

    # Sikr at antal findes og er numerisk
    if "antal" not in df.columns:
        st.error("Kolonnen 'antal' mangler i datasættet.")
        st.stop()

    df["antal"] = pd.to_numeric(df["antal"], errors="coerce").fillna(0)

    return df


def filtrer_periode(df, start_month, start_year, months):
    p1_start = pd.Timestamp(start_year, start_month, 1)
    p1_slut = p1_start + pd.DateOffset(months=months) - pd.DateOffset(days=1)

    p2_start = pd.Timestamp(start_year + 1, start_month, 1)
    p2_slut = p2_start + pd.DateOffset(months=months) - pd.DateOffset(days=1)

    df1 = df[(df["dato"] >= p1_start) & (df["dato"] <= p1_slut)].copy()
    df2 = df[(df["dato"] >= p2_start) & (df["dato"] <= p2_slut)].copy()

    return df1, df2, p1_start, p1_slut, p2_start, p2_slut


def måned_label(m, y):
    return f"{calendar.month_abbr[m]} {str(y)[-2:]}"


def lav_månedsserie(df, koder, label):
    d = df[df["ydelseskode"].isin(koder)]
    d = d.groupby(["år", "måned"])["antal"].sum().reset_index(name=label)
    return d


def stacked_ydelser(df1, df2, months, start_month, start_year):
    def prep(df, year):
        d120 = lav_månedsserie(df, ["0120"], "0120")
        d101_125 = lav_månedsserie(df, ["0101", "0125"], "0101_0125")
        merged = pd.merge(d120, d101_125, on=["år", "måned"], how="outer").fillna(0)
        merged["periode"] = year
        return merged

    p1 = prep(df1, "P1")
    p2 = prep(df2, "P2")
    data = pd.concat([p1, p2])

    # Rækkefølge: M1-P1, M1-P2, M2-P1, M2-P2 ...
    rows = []
    for i in range(months):
        m = (start_month - 1 + i) % 12 + 1
        rows.append((start_year, m, "P1"))
        rows.append((start_year + 1, m, "P2"))

    data["sort"] = data.apply(lambda r: rows.index((r["år"], r["måned"], r["periode"])), axis=1)
    data = data.sort_values("sort")

    data["label"] = data.apply(lambda r: måned_label(r["måned"], r["år"]), axis=1)

    fig = px.bar(
        data,
        x="label",
        y=["0120", "0101_0125"],
        title="0101 + 0120 + 0125 (stacked, 0120 nederst)",
        color_discrete_map={"0120": "red", "0101_0125": "blue"},
    )

    return fig


def lav_søjlediagram(df1, df2, koder, title, months, start_month, start_year):
    def prep(df, year):
        d = lav_månedsserie(df, koder, "antal")
        d["periode"] = year
        return d

    p1 = prep(df1, "P1")
    p2 = prep(df2, "P2")
    data = pd.concat([p1, p2])

    rows = []
    for i in range(months):
        m = (start_month - 1 + i) % 12 + 1
        rows.append((start_year, m, "P1"))
        rows.append((start_year + 1, m, "P2"))

    data["sort"] = data.apply(lambda r: rows.index((r["år"], r["måned"], r["periode"])), axis=1)
    data = data.sort_values("sort")

    data["label"] = data.apply(lambda r: måned_label(r["måned"], r["år"]), axis=1)

    fig = px.bar(data, x="label", y="antal", title=title, color="periode")
    return fig


def ugedagsgraf(df1, df2):
    koder = ["0101", "0120", "0125"]

    def prep(df, year):
        d = df[df["ydelseskode"].isin(koder)]
        d = d[d["ugedag"].isin(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"])]
        d = d.groupby("ugedag")["antal"].sum().reset_index(name="antal")
        d["periode"] = year
        return d

    p1 = prep(df1, "P1")
    p2 = prep(df2, "P2")
    data = pd.concat([p1, p2])

    order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    data["ugedag"] = pd.Categorical(data["ugedag"], order)

    fig = px.bar(data, x="ugedag", y="antal", color="periode", title="Fordeling på ugedage (0101+0120+0125)")
    return fig


def lav_pdf(figures):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    for fig in figures:
        pdf.add_page()
        img = BytesIO()
        fig.write_image(img, format="png")
        img.seek(0)
        pdf.image(img, x=10, y=10, w=180)

    return pdf.output(dest="S").encode("latin1")


# ---------------------------------------------------------
# Streamlit UI
# ---------------------------------------------------------

st.title("Analyse af ydelser")

uploaded_file = st.file_uploader("Upload Excel-fil", type=["xlsx"])

if uploaded_file:
    df = load_data(uploaded_file)

    st.success("Fil indlæst!")

    col1, col2, col3 = st.columns(3)

    with col1:
        start_month = st.selectbox("Startmåned", list(range(1, 13)), format_func=lambda m: calendar.month_name[m])

    with col2:
        start_year = st.selectbox("Startår", sorted(df["år"].unique()))

    with col3:
        months = st.selectbox("Antal måneder", [3, 6, 9, 12])

    df1, df2, p1s, p1e, p2s, p2e = filtrer_periode(df, start_month, start_year, months)

    st.write(f"**Periode 1:** {p1s.date()} → {p1e.date()}")
    st.write(f"**Periode 2:** {p2s.date()} → {p2e.date()}")

    st.header("Grafer")

    figs = []

    fig1 = stacked_ydelser(df1, df2, months, start_month, start_year)
    st.plotly_chart(fig1, use_container_width=True)
    figs.append(fig1)

    fig2 = lav_søjlediagram(df1, df2, ["2101"], "2101 pr. måned", months, start_month, start_year)
    st.plotly_chart(fig2, use_container_width=True)
    figs.append(fig2)

    fig3 = lav_søjlediagram(df1, df2, ["7156"], "7156 pr. måned", months, start_month, start_year)
    st.plotly_chart(fig3, use_container_width=True)
    figs.append(fig3)

    fig4 = lav_søjlediagram(df1, df2, ["2149"], "2149 pr. måned", months, start_month, start_year)
    st.plotly_chart(fig4, use_container_width=True)
    figs.append(fig4)

    fig5 = lav_søjlediagram(df1, df2, ["0411", "0421", "0431", "0491"], "0411+0421+0431+0491 pr. måned", months, start_month, start_year)
    st.plotly_chart(fig5, use_container_width=True)
    figs.append(fig5)

    fig6 = ugedagsgraf(df1, df2)
    st.plotly_chart(fig6, use_container_width=True)
    figs.append(fig6)

    pdf_bytes = lav_pdf(figs)
    st.download_button("Download PDF med alle grafer", data=pdf_bytes, file_name="ydelser.pdf", mime="application/pdf")
