import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import io
from PIL import Image
import base64

# Konfiguration af siden 
st.set_page_config(page_title="Ydelsesanalyse", layout="wide")

st.title("📊 Ydelsesanalyse - Periodesammenligning")

# File upload
uploaded_file = st.file_uploader("Upload dit datasæt (Excel-fil)", type=['xlsx', 'xls'])

if uploaded_file is not None:
    # Indlæs data
    df = pd.read_excel(uploaded_file)
    
    # Filtrer kun data hvor Antal >= 1
    df = df[df['Antal'] >= 1].copy()
    
    # Konverter dato til datetime hvis ikke allerede
    df['Ydelses dato'] = pd.to_datetime(df['Ydelses dato'])
    
    st.success(f"✅ Data indlæst: {len(df)} rækker (efter filtrering af Antal >= 1)")
    
    # Sidebar til periode-valg
    st.sidebar.header("Vælg Periode 1")
    
    # Find tilgængelige år og måneder
    min_date = df['Ydelses dato'].min()
    max_date = df['Ydelses dato'].max()
    
    # Lav liste af tilgængelige år
    available_years = sorted(df['Ydelses dato'].dt.year.unique())
    
    # Valg af år
    selected_year = st.sidebar.selectbox("Vælg år", available_years)
    
    # Valg af måned
    month_names = {
        1: "Januar", 2: "Februar", 3: "Marts", 4: "April",
        5: "Maj", 6: "Juni", 7: "Juli", 8: "August",
        9: "September", 10: "Oktober", 11: "November", 12: "December"
    }
    
    selected_month = st.sidebar.selectbox(
        "Vælg måned",
        options=list(range(1, 13)),
        format_func=lambda x: month_names[x]
    )
    
    # Valg af antal måneder
    duration_months = st.sidebar.selectbox(
        "Vælg antal måneder",
        options=[3, 6, 9, 12]
    )
    
    # Beregn periode 1
    start_date_p1 = datetime(selected_year, selected_month, 1)
    end_date_p1 = start_date_p1 + relativedelta(months=duration_months) - timedelta(days=1)
    
    # Beregn periode 2 (et år senere)
    start_date_p2 = start_date_p1 + relativedelta(years=1)
    end_date_p2 = start_date_p2 + relativedelta(months=duration_months) - timedelta(days=1)
    
    # Vis valgte perioder
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Periode 1:**")
    st.sidebar.info(f"{start_date_p1.strftime('%b %Y')} - {end_date_p1.strftime('%b %Y')}")
    
    st.sidebar.markdown("**Periode 2:**")
    st.sidebar.info(f"{start_date_p2.strftime('%b %Y')} - {end_date_p2.strftime('%b %Y')}")
    
    # Filtrer data for begge perioder
    df_p1 = df[(df['Ydelses dato'] >= start_date_p1) & (df['Ydelses dato'] <= end_date_p1)].copy()
    df_p2 = df[(df['Ydelses dato'] >= start_date_p2) & (df['Ydelses dato'] <= end_date_p2)].copy()
    
    # Tilføj måned-kolonne (1, 2, 3, etc.)
    df_p1['Måned_nr'] = ((df_p1['Ydelses dato'].dt.year - start_date_p1.year) * 12 + 
                          df_p1['Ydelses dato'].dt.month - start_date_p1.month + 1)
    df_p2['Måned_nr'] = ((df_p2['Ydelses dato'].dt.year - start_date_p2.year) * 12 + 
                          df_p2['Ydelses dato'].dt.month - start_date_p2.month + 1)
    
    # Check om der er data
    if len(df_p1) == 0 and len(df_p2) == 0:
        st.warning("⚠️ Ingen data fundet for de valgte perioder.")
    else:
        # Funktion til at lave graf 1: Grundydelser
        def create_grundydelser_chart():
            grundydelser_koder = [101, 125, 120]
            
            data_p1 = df_p1[df_p1['Ydelseskode'].isin(grundydelser_koder)].groupby('Måned_nr').size()
            data_p2 = df_p2[df_p2['Ydelseskode'].isin(grundydelser_koder)].groupby('Måned_nr').size()
            
            # Beregn 120-procent for hver måned
            kode_120_p1 = df_p1[df_p1['Ydelseskode'] == 120].groupby('Måned_nr').size()
            kode_120_p2 = df_p2[df_p2['Ydelseskode'] == 120].groupby('Måned_nr').size()
            
            fig = go.Figure()
            
            # Lav data for alle måneder
            x_labels = []
            y_values = []
            colors = []
            annotations = []
            
            for month in range(1, duration_months + 1):
                # Periode 1
                count_p1 = data_p1.get(month, 0)
                count_120_p1 = kode_120_p1.get(month, 0)
                pct_p1 = (count_120_p1 / count_p1 * 100) if count_p1 > 0 else 0
                
                x_labels.append(f"M{month} P1")
                y_values.append(count_p1)
                colors.append('blue')
                annotations.append(dict(
                    x=len(x_labels) - 1,
                    y=count_p1,
                    text=f"{pct_p1:.0f}%",
                    showarrow=False,
                    yshift=-15,
                    font=dict(color='red', size=10)
                ))
                
                # Periode 2
                count_p2 = data_p2.get(month, 0)
                count_120_p2 = kode_120_p2.get(month, 0)
                pct_p2 = (count_120_p2 / count_p2 * 100) if count_p2 > 0 else 0
                
                x_labels.append(f"M{month} P2")
                y_values.append(count_p2)
                colors.append('lightblue')
                annotations.append(dict(
                    x=len(x_labels) - 1,
                    y=count_p2,
                    text=f"{pct_p2:.0f}%",
                    showarrow=False,
                    yshift=-15,
                    font=dict(color='red', size=10)
                ))
            
            fig.add_trace(go.Bar(
                x=x_labels,
                y=y_values,
                marker_color=colors,
                text=y_values,
                textposition='outside'
            ))
            
            fig.update_layout(
                title="Graf 1: Grundydelser (101, 125, 120) - Røde tal viser 120-procent",
                xaxis_title="Måned",
                yaxis_title="Antal",
                showlegend=False,
                height=500,
                annotations=annotations
            )
            
            return fig
        
        # Funktion til at lave graf 2: Besøg
        def create_besøg_chart():
            besøg_koder = [411, 421, 431, 441, 491]
            
            data_p1 = df_p1[df_p1['Ydelseskode'].isin(besøg_koder)].groupby('Måned_nr').size()
            data_p2 = df_p2[df_p2['Ydelseskode'].isin(besøg_koder)].groupby('Måned_nr').size()
            
            fig = go.Figure()
            
            x_labels = []
            y_values = []
            colors = []
            
            for month in range(1, duration_months + 1):
                # Periode 1
                count_p1 = data_p1.get(month, 0)
                x_labels.append(f"M{month} P1")
                y_values.append(count_p1)
                colors.append('green')
                
                # Periode 2
                count_p2 = data_p2.get(month, 0)
                x_labels.append(f"M{month} P2")
                y_values.append(count_p2)
                colors.append('lightgreen')
            
            fig.add_trace(go.Bar(
                x=x_labels,
                y=y_values,
                marker_color=colors,
                text=y_values,
                textposition='outside'
            ))
            
            fig.update_layout(
                title="Graf 2: Besøg (411, 421, 431, 441, 491)",
                xaxis_title="Måned",
                yaxis_title="Antal",
                showlegend=False,
                height=500
            )
            
            return fig
        
        # Funktion til at lave graf 3: Uddannelseslæger
        def create_uddannelseslæger_chart():
            grundydelser_koder = [101, 125, 120]
            erfarne_læger = ['mp', 'jn', 'jes', 'ah', 'cj', 'in']
            
            # Periode 1
            data_p1_alle = df_p1[df_p1['Ydelseskode'].isin(grundydelser_koder)].groupby('Måned_nr').size()
            data_p1_uddannelse = df_p1[
                (df_p1['Ydelseskode'].isin(grundydelser_koder)) & 
                (~df_p1['Bruger'].isin(erfarne_læger))
            ].groupby('Måned_nr').size()
            
            # Periode 2
            data_p2_alle = df_p2[df_p2['Ydelseskode'].isin(grundydelser_koder)].groupby('Måned_nr').size()
            data_p2_uddannelse = df_p2[
                (df_p2['Ydelseskode'].isin(grundydelser_koder)) & 
                (~df_p2['Bruger'].isin(erfarne_læger))
            ].groupby('Måned_nr').size()
            
            fig = go.Figure()
            
            x_labels = []
            y_values = []
            colors = []
            annotations = []
            
            for month in range(1, duration_months + 1):
                # Periode 1
                alle_p1 = data_p1_alle.get(month, 0)
                uddannelse_p1 = data_p1_uddannelse.get(month, 0)
                pct_p1 = (uddannelse_p1 / alle_p1 * 100) if alle_p1 > 0 else 0
                
                x_labels.append(f"M{month} P1")
                y_values.append(alle_p1)
                colors.append('purple')
                annotations.append(dict(
                    x=len(x_labels) - 1,
                    y=alle_p1,
                    text=f"{pct_p1:.0f}%",
                    showarrow=False,
                    yshift=-15,
                    font=dict(color='orange', size=10, weight='bold')
                ))
                
                # Periode 2
                alle_p2 = data_p2_alle.get(month, 0)
                uddannelse_p2 = data_p2_uddannelse.get(month, 0)
                pct_p2 = (uddannelse_p2 / alle_p2 * 100) if alle_p2 > 0 else 0
                
                x_labels.append(f"M{month} P2")
                y_values.append(alle_p2)
                colors.append('lavender')
                annotations.append(dict(
                    x=len(x_labels) - 1,
                    y=alle_p2,
                    text=f"{pct_p2:.0f}%",
                    showarrow=False,
                    yshift=-15,
                    font=dict(color='orange', size=10, weight='bold')
                ))
            
            fig.add_trace(go.Bar(
                x=x_labels,
                y=y_values,
                marker_color=colors,
                text=y_values,
                textposition='outside'
            ))
            
            fig.update_layout(
                title="Graf 3: Uddannelseslæger i procent af grundydelser (Orange tal = procent fra andre end mp, jn, jes, ah, cj, in)",
                xaxis_title="Måned",
                yaxis_title="Antal grundydelser",
                showlegend=False,
                height=500,
                annotations=annotations
            )
            
            return fig
        
        # Vis graferne
        st.header("Visualiseringer")
        
        chart1 = create_grundydelser_chart()
        st.plotly_chart(chart1, use_container_width=True)
        
        chart2 = create_besøg_chart()
        st.plotly_chart(chart2, use_container_width=True)
        
        chart3 = create_uddannelseslæger_chart()
        st.plotly_chart(chart3, use_container_width=True)
        
        # PDF Download funktionalitet
        st.markdown("---")
        st.header("📥 Download rapport")
        
        if st.button("Generer PDF-rapport", type="primary"):
            with st.spinner("Genererer PDF..."):
                # Gem graferne som billeder
                img1 = chart1.to_image(format="png", width=1200, height=500)
                img2 = chart2.to_image(format="png", width=1200, height=500)
                img3 = chart3.to_image(format="png", width=1200, height=500)
                
                # Opret en simpel PDF med reportlab
                from reportlab.lib.pagesizes import A4, landscape
                from reportlab.pdfgen import canvas
                from reportlab.lib.units import inch
                
                buffer = io.BytesIO()
                c = canvas.Canvas(buffer, pagesize=landscape(A4))
                width, height = landscape(A4)
                
                # Side 1
                c.setFont("Helvetica-Bold", 16)
                c.drawString(50, height - 50, "Ydelsesanalyse - Periodesammenligning")
                c.setFont("Helvetica", 12)
                c.drawString(50, height - 80, f"Periode 1: {start_date_p1.strftime('%b %Y')} - {end_date_p1.strftime('%b %Y')}")
                c.drawString(50, height - 100, f"Periode 2: {start_date_p2.strftime('%b %Y')} - {end_date_p2.strftime('%b %Y')}")
                
                # Graf 1
                c.drawImage(io.BytesIO(img1), 50, height - 400, width=700, height=250, preserveAspectRatio=True)
                
                c.showPage()
                
                # Side 2
                c.drawImage(io.BytesIO(img2), 50, height - 350, width=700, height=250, preserveAspectRatio=True)
                
                c.showPage()
                
                # Side 3
                c.drawImage(io.BytesIO(img3), 50, height - 350, width=700, height=250, preserveAspectRatio=True)
                
                c.save()
                
                buffer.seek(0)
                
                st.download_button(
                    label="⬇️ Download PDF",
                    data=buffer,
                    file_name=f"ydelsesanalyse_{start_date_p1.strftime('%Y%m')}_rapport.pdf",
                    mime="application/pdf"
                )
                
                st.success("✅ PDF klar til download!")

else:
    st.info("👆 Upload venligst dit datasæt for at komme i gang")
    st.markdown("""
    ### Sådan bruges appen:
    1. Upload dit Excel-datasæt
    2. Vælg startmåned og -år for Periode 1
    3. Vælg antal måneder (3, 6, 9 eller 12)
    4. Se graferne opdateres automatisk
    5. Download rapport som PDF
    
    **Dataformat:**
    - Kolonner: Køn, Alder, Ydelseskode, Antal, Beløb, Ydelses dato, Bruger
    - Kun data med Antal >= 1 medtages i analysen
    """)
