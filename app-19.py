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
    
    month_names_short = {
        1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr",
        5: "Maj", 6: "Jun", 7: "Jul", 8: "Aug",
        9: "Sep", 10: "Okt", 11: "Nov", 12: "Dec"
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
    
    # Dropdown til valg af diagram-type
    st.sidebar.markdown("---")
    chart_type = st.sidebar.selectbox(
        "Vælg diagram-type",
        options=["Søjlediagram", "Kurvediagram"]
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
    
    # Funktion til at generere måned-labels
    def get_month_label(base_date, month_offset):
        target_date = base_date + relativedelta(months=month_offset)
        return f"{month_names_short[target_date.month]} {str(target_date.year)[2:]}"
    
    # Check om der er data
    if len(df_p1) == 0 and len(df_p2) == 0:
        st.warning("⚠️ Ingen data fundet for de valgte perioder.")
    else:
        # Funktion til at lave graf 1: Grundydelser - SØJLER
        def create_grundydelser_bar_chart():
            grundydelser_koder = [101, 125, 120]
            
            data_p1_total = df_p1[df_p1['Ydelseskode'].isin(grundydelser_koder)].groupby('Måned_nr').size()
            data_p2_total = df_p2[df_p2['Ydelseskode'].isin(grundydelser_koder)].groupby('Måned_nr').size()
            
            # Beregn 120 for hver måned
            kode_120_p1 = df_p1[df_p1['Ydelseskode'] == 120].groupby('Måned_nr').size()
            kode_120_p2 = df_p2[df_p2['Ydelseskode'] == 120].groupby('Måned_nr').size()
            
            fig = go.Figure()
            
            # Data for stacked bars
            x_labels = []
            y_red_p1 = []
            y_blue_p1 = []
            y_red_p2 = []
            y_blue_p2 = []
            annotations = []
            
            for month in range(1, duration_months + 1):
                # Labels
                label_p1 = get_month_label(start_date_p1, month - 1)
                label_p2 = get_month_label(start_date_p2, month - 1)
                
                # Periode 1
                total_p1 = data_p1_total.get(month, 0)
                count_120_p1 = kode_120_p1.get(month, 0)
                other_p1 = total_p1 - count_120_p1
                pct_p1 = (count_120_p1 / total_p1 * 100) if total_p1 > 0 else 0
                
                x_labels.append(label_p1)
                y_red_p1.append(count_120_p1)
                y_blue_p1.append(other_p1)
                
                # Annotation for P1
                annotations.append(dict(
                    x=len(x_labels) - 1,
                    y=total_p1,
                    text=f"{pct_p1:.0f}%",
                    showarrow=False,
                    yshift=10,
                    font=dict(color='red', size=11, weight='bold')
                ))
                
                # Periode 2
                total_p2 = data_p2_total.get(month, 0)
                count_120_p2 = kode_120_p2.get(month, 0)
                other_p2 = total_p2 - count_120_p2
                pct_p2 = (count_120_p2 / total_p2 * 100) if total_p2 > 0 else 0
                
                x_labels.append(label_p2)
                y_red_p2.append(count_120_p2)
                y_blue_p2.append(other_p2)
                
                # Annotation for P2
                annotations.append(dict(
                    x=len(x_labels) - 1,
                    y=total_p2,
                    text=f"{pct_p2:.0f}%",
                    showarrow=False,
                    yshift=10,
                    font=dict(color='red', size=11, weight='bold')
                ))
            
            # Kombiner P1 og P2 data
            y_red = []
            y_blue = []
            for i in range(duration_months):
                y_red.append(y_red_p1[i])
                y_red.append(y_red_p2[i])
                y_blue.append(y_blue_p1[i])
                y_blue.append(y_blue_p2[i])
            
            # Rød bundfarve (120-kode)
            fig.add_trace(go.Bar(
                x=x_labels,
                y=y_red,
                name='Kode 120',
                marker_color='#DC143C',
                showlegend=False
            ))
            
            # Blå topfarve (andre grundydelser)
            fig.add_trace(go.Bar(
                x=x_labels,
                y=y_blue,
                name='Kode 101 + 125',
                marker_color='#4169E1',
                showlegend=False
            ))
            
            fig.update_layout(
                title="Graf 1: Grundydelser (101, 125, 120) - Rød = 120, Procent vist øverst",
                xaxis_title="Måned",
                yaxis_title="Antal",
                barmode='stack',
                height=500,
                annotations=annotations,
                xaxis=dict(tickangle=-45)
            )
            
            return fig
        
        # Funktion til at lave graf 1: Grundydelser - KURVER
        def create_grundydelser_line_chart():
            grundydelser_koder = [101, 125, 120]
            
            # Beregn data for hver måned - fælles x-akse
            month_labels = []
            total_p1 = []
            total_p2 = []
            pct_120_p1 = []
            pct_120_p2 = []
            
            for month in range(1, duration_months + 1):
                # Fælles måned-label (kun måned-navn, ikke år/periode)
                month_name = month_names_short[(start_date_p1.month + month - 2) % 12 + 1]
                month_labels.append(month_name)
                
                # Periode 1
                df_month_p1 = df_p1[df_p1['Måned_nr'] == month]
                count_total_p1 = len(df_month_p1[df_month_p1['Ydelseskode'].isin(grundydelser_koder)])
                count_120_p1 = len(df_month_p1[df_month_p1['Ydelseskode'] == 120])
                pct_p1 = (count_120_p1 / count_total_p1 * 100) if count_total_p1 > 0 else 0
                
                total_p1.append(count_total_p1)
                pct_120_p1.append(pct_p1)
                
                # Periode 2
                df_month_p2 = df_p2[df_p2['Måned_nr'] == month]
                count_total_p2 = len(df_month_p2[df_month_p2['Ydelseskode'].isin(grundydelser_koder)])
                count_120_p2 = len(df_month_p2[df_month_p2['Ydelseskode'] == 120])
                pct_p2 = (count_120_p2 / count_total_p2 * 100) if count_total_p2 > 0 else 0
                
                total_p2.append(count_total_p2)
                pct_120_p2.append(pct_p2)
            
            # Opret figur med to y-akser
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            
            # Total antal - P1 (blå, fast linje)
            fig.add_trace(
                go.Scatter(x=month_labels, y=total_p1, name=f"Total {start_date_p1.year}/{str(start_date_p1.year+1)[2:]}", 
                          line=dict(color='#4169E1', width=3), mode='lines+markers'),
                secondary_y=False
            )
            
            # Total antal - P2 (lyseblå, stiplet)
            fig.add_trace(
                go.Scatter(x=month_labels, y=total_p2, name=f"Total {start_date_p2.year}/{str(start_date_p2.year+1)[2:]}", 
                          line=dict(color='#87CEEB', width=3, dash='dash'), mode='lines+markers'),
                secondary_y=False
            )
            
            # Procent 120 - P1 (rød, fast)
            fig.add_trace(
                go.Scatter(x=month_labels, y=pct_120_p1, name=f"120% {start_date_p1.year}/{str(start_date_p1.year+1)[2:]}", 
                          line=dict(color='#DC143C', width=2), mode='lines+markers'),
                secondary_y=True
            )
            
            # Procent 120 - P2 (orange, stiplet)
            fig.add_trace(
                go.Scatter(x=month_labels, y=pct_120_p2, name=f"120% {start_date_p2.year}/{str(start_date_p2.year+1)[2:]}", 
                          line=dict(color='#FF8C00', width=2, dash='dash'), mode='lines+markers'),
                secondary_y=True
            )
            
            # Opdater layout
            fig.update_xaxes(title_text="Måned")
            fig.update_yaxes(title_text="Antal ydelser", secondary_y=False)
            fig.update_yaxes(title_text="Procent 120", secondary_y=True)
            
            fig.update_layout(
                title="Graf 1: Grundydelser (101, 125, 120)",
                height=500,
                hovermode='x unified',
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            
            return fig
        
        # Funktion til at lave graf 2: Besøg - SØJLER
        def create_besøg_bar_chart():
            besøg_koder = [411, 421, 431, 441, 491]
            
            data_p1 = df_p1[df_p1['Ydelseskode'].isin(besøg_koder)].groupby('Måned_nr').size()
            data_p2 = df_p2[df_p2['Ydelseskode'].isin(besøg_koder)].groupby('Måned_nr').size()
            
            fig = go.Figure()
            
            x_labels = []
            y_values = []
            
            for month in range(1, duration_months + 1):
                # Labels
                label_p1 = get_month_label(start_date_p1, month - 1)
                label_p2 = get_month_label(start_date_p2, month - 1)
                
                # Periode 1
                count_p1 = data_p1.get(month, 0)
                x_labels.append(label_p1)
                y_values.append(count_p1)
                
                # Periode 2
                count_p2 = data_p2.get(month, 0)
                x_labels.append(label_p2)
                y_values.append(count_p2)
            
            fig.add_trace(go.Bar(
                x=x_labels,
                y=y_values,
                marker_color='#4169E1',
                text=y_values,
                textposition='outside',
                showlegend=False
            ))
            
            fig.update_layout(
                title="Graf 2: Besøg (411, 421, 431, 441, 491)",
                xaxis_title="Måned",
                yaxis_title="Antal",
                height=500,
                xaxis=dict(tickangle=-45)
            )
            
            return fig
        
        # Funktion til at lave graf 2: Besøg - KURVER
        def create_besøg_line_chart():
            besøg_koder = [411, 421, 431, 441, 491]
            
            # Fælles x-akse
            month_labels = []
            counts_p1 = []
            counts_p2 = []
            
            for month in range(1, duration_months + 1):
                # Fælles måned-label
                month_name = month_names_short[(start_date_p1.month + month - 2) % 12 + 1]
                month_labels.append(month_name)
                
                # Periode 1
                df_month_p1 = df_p1[df_p1['Måned_nr'] == month]
                count_p1 = len(df_month_p1[df_month_p1['Ydelseskode'].isin(besøg_koder)])
                counts_p1.append(count_p1)
                
                # Periode 2
                df_month_p2 = df_p2[df_p2['Måned_nr'] == month]
                count_p2 = len(df_month_p2[df_month_p2['Ydelseskode'].isin(besøg_koder)])
                counts_p2.append(count_p2)
            
            fig = go.Figure()
            
            # P1 (blå, fast linje)
            fig.add_trace(
                go.Scatter(x=month_labels, y=counts_p1, name=f"Besøg {start_date_p1.year}/{str(start_date_p1.year+1)[2:]}",
                          line=dict(color='#4169E1', width=3), mode='lines+markers')
            )
            
            # P2 (lyseblå, stiplet)
            fig.add_trace(
                go.Scatter(x=month_labels, y=counts_p2, name=f"Besøg {start_date_p2.year}/{str(start_date_p2.year+1)[2:]}",
                          line=dict(color='#87CEEB', width=3, dash='dash'), mode='lines+markers')
            )
            
            fig.update_layout(
                title="Graf 2: Besøg (411, 421, 431, 441, 491)",
                xaxis_title="Måned",
                yaxis_title="Antal",
                height=500,
                hovermode='x unified',
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            
            return fig
        
        # Funktion til at lave graf 3: Uddannelseslæger - SØJLER
        def create_uddannelseslæger_bar_chart():
            grundydelser_koder = [101, 125, 120]
            erfarne_læger = ['mp', 'jn', 'jes', 'ah', 'cj', 'in']
            
            # Total grundydelser pr. måned
            data_p1_total = df_p1[df_p1['Ydelseskode'].isin(grundydelser_koder)].groupby('Måned_nr').size()
            data_p2_total = df_p2[df_p2['Ydelseskode'].isin(grundydelser_koder)].groupby('Måned_nr').size()
            
            # Uddannelseslæger (ikke de 6 erfarne)
            data_p1_uddannelse = df_p1[
                (df_p1['Ydelseskode'].isin(grundydelser_koder)) & 
                (~df_p1['Bruger'].isin(erfarne_læger))
            ].groupby('Måned_nr').size()
            
            data_p2_uddannelse = df_p2[
                (df_p2['Ydelseskode'].isin(grundydelser_koder)) & 
                (~df_p2['Bruger'].isin(erfarne_læger))
            ].groupby('Måned_nr').size()
            
            fig = go.Figure()
            
            x_labels = []
            y_red_p1 = []
            y_blue_p1 = []
            y_red_p2 = []
            y_blue_p2 = []
            annotations = []
            
            for month in range(1, duration_months + 1):
                # Labels
                label_p1 = get_month_label(start_date_p1, month - 1)
                label_p2 = get_month_label(start_date_p2, month - 1)
                
                # Periode 1
                total_p1 = data_p1_total.get(month, 0)
                uddannelse_p1 = data_p1_uddannelse.get(month, 0)
                erfarne_p1 = total_p1 - uddannelse_p1
                pct_p1 = (uddannelse_p1 / total_p1 * 100) if total_p1 > 0 else 0
                
                x_labels.append(label_p1)
                y_red_p1.append(uddannelse_p1)
                y_blue_p1.append(erfarne_p1)
                
                # Annotation for P1
                annotations.append(dict(
                    x=len(x_labels) - 1,
                    y=total_p1,
                    text=f"{pct_p1:.0f}%",
                    showarrow=False,
                    yshift=10,
                    font=dict(color='red', size=11, weight='bold')
                ))
                
                # Periode 2
                total_p2 = data_p2_total.get(month, 0)
                uddannelse_p2 = data_p2_uddannelse.get(month, 0)
                erfarne_p2 = total_p2 - uddannelse_p2
                pct_p2 = (uddannelse_p2 / total_p2 * 100) if total_p2 > 0 else 0
                
                x_labels.append(label_p2)
                y_red_p2.append(uddannelse_p2)
                y_blue_p2.append(erfarne_p2)
                
                # Annotation for P2
                annotations.append(dict(
                    x=len(x_labels) - 1,
                    y=total_p2,
                    text=f"{pct_p2:.0f}%",
                    showarrow=False,
                    yshift=10,
                    font=dict(color='red', size=11, weight='bold')
                ))
            
            # Kombiner P1 og P2 data
            y_red = []
            y_blue = []
            for i in range(duration_months):
                y_red.append(y_red_p1[i])
                y_red.append(y_red_p2[i])
                y_blue.append(y_blue_p1[i])
                y_blue.append(y_blue_p2[i])
            
            # Rød bundfarve (uddannelseslæger)
            fig.add_trace(go.Bar(
                x=x_labels,
                y=y_red,
                name='Uddannelseslæger',
                marker_color='#DC143C',
                showlegend=False
            ))
            
            # Blå topfarve (erfarne læger)
            fig.add_trace(go.Bar(
                x=x_labels,
                y=y_blue,
                name='Erfarne læger',
                marker_color='#4169E1',
                showlegend=False
            ))
            
            fig.update_layout(
                title="Graf 3: Uddannelseslæger i procent af grundydelser - Rød = Uddannelseslæger, Procent vist øverst",
                xaxis_title="Måned",
                yaxis_title="Antal grundydelser",
                barmode='stack',
                height=500,
                annotations=annotations,
                xaxis=dict(tickangle=-45)
            )
            
            return fig
        
        # Funktion til at lave graf 3: Uddannelseslæger - KURVER
        def create_uddannelseslæger_line_chart():
            grundydelser_koder = [101, 125, 120]
            erfarne_læger = ['mp', 'jn', 'jes', 'ah', 'cj', 'in']
            
            # Fælles x-akse
            month_labels = []
            total_p1 = []
            total_p2 = []
            pct_udd_p1 = []
            pct_udd_p2 = []
            
            for month in range(1, duration_months + 1):
                # Fælles måned-label
                month_name = month_names_short[(start_date_p1.month + month - 2) % 12 + 1]
                month_labels.append(month_name)
                
                # Periode 1
                df_month_p1 = df_p1[df_p1['Måned_nr'] == month]
                count_total_p1 = len(df_month_p1[df_month_p1['Ydelseskode'].isin(grundydelser_koder)])
                count_udd_p1 = len(df_month_p1[
                    (df_month_p1['Ydelseskode'].isin(grundydelser_koder)) & 
                    (~df_month_p1['Bruger'].isin(erfarne_læger))
                ])
                pct_p1 = (count_udd_p1 / count_total_p1 * 100) if count_total_p1 > 0 else 0
                
                total_p1.append(count_total_p1)
                pct_udd_p1.append(pct_p1)
                
                # Periode 2
                df_month_p2 = df_p2[df_p2['Måned_nr'] == month]
                count_total_p2 = len(df_month_p2[df_month_p2['Ydelseskode'].isin(grundydelser_koder)])
                count_udd_p2 = len(df_month_p2[
                    (df_month_p2['Ydelseskode'].isin(grundydelser_koder)) & 
                    (~df_month_p2['Bruger'].isin(erfarne_læger))
                ])
                pct_p2 = (count_udd_p2 / count_total_p2 * 100) if count_total_p2 > 0 else 0
                
                total_p2.append(count_total_p2)
                pct_udd_p2.append(pct_p2)
            
            # Opret figur med to y-akser
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            
            # Total antal - P1 (blå, fast)
            fig.add_trace(
                go.Scatter(x=month_labels, y=total_p1, name=f"Total {start_date_p1.year}/{str(start_date_p1.year+1)[2:]}",
                          line=dict(color='#4169E1', width=3), mode='lines+markers'),
                secondary_y=False
            )
            
            # Total antal - P2 (lyseblå, stiplet)
            fig.add_trace(
                go.Scatter(x=month_labels, y=total_p2, name=f"Total {start_date_p2.year}/{str(start_date_p2.year+1)[2:]}",
                          line=dict(color='#87CEEB', width=3, dash='dash'), mode='lines+markers'),
                secondary_y=False
            )
            
            # Procent uddannelseslæger - P1 (rød, fast)
            fig.add_trace(
                go.Scatter(x=month_labels, y=pct_udd_p1, name=f"Udd.læger% {start_date_p1.year}/{str(start_date_p1.year+1)[2:]}",
                          line=dict(color='#DC143C', width=2), mode='lines+markers'),
                secondary_y=True
            )
            
            # Procent uddannelseslæger - P2 (orange, stiplet)
            fig.add_trace(
                go.Scatter(x=month_labels, y=pct_udd_p2, name=f"Udd.læger% {start_date_p2.year}/{str(start_date_p2.year+1)[2:]}",
                          line=dict(color='#FF8C00', width=2, dash='dash'), mode='lines+markers'),
                secondary_y=True
            )
            
            # Opdater layout
            fig.update_xaxes(title_text="Måned")
            fig.update_yaxes(title_text="Antal grundydelser", secondary_y=False)
            fig.update_yaxes(title_text="Procent uddannelseslæger", secondary_y=True)
            
            fig.update_layout(
                title="Graf 3: Uddannelseslæger i procent af grundydelser",
                height=500,
                hovermode='x unified',
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            
            return fig
        
        # Vis graferne baseret på valgt type
        st.header("Visualiseringer")
        
        if chart_type == "Søjlediagram":
            chart1 = create_grundydelser_bar_chart()
            chart2 = create_besøg_bar_chart()
            chart3 = create_uddannelseslæger_bar_chart()
        else:  # Kurvediagram
            chart1 = create_grundydelser_line_chart()
            chart2 = create_besøg_line_chart()
            chart3 = create_uddannelseslæger_line_chart()
        
        st.plotly_chart(chart1, use_container_width=True)
        st.plotly_chart(chart2, use_container_width=True)
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
                c.drawString(50, height - 50, f"Ydelsesanalyse - Periodesammenligning ({chart_type})")
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
                    file_name=f"ydelsesanalyse_{start_date_p1.strftime('%Y%m')}_{chart_type}.pdf",
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
    4. Vælg diagram-type (Søjler eller Kurver)
    5. Se graferne opdateres automatisk
    6. Download rapport som PDF
    
    **Dataformat:**
    - Kolonner: Køn, Alder, Ydelseskode, Antal, Beløb, Ydelses dato, Bruger
    - Kun data med Antal >= 1 medtages i analysen
    """)
