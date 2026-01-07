import streamlit as st
import pandas as pd
import io
import requests
import urllib.parse
import plotly.express as px

# --- КОНФИГУРАЦИЯ ---
URL_STRUCT = "https://raw.githubusercontent.com/denmalysheff/Nuch/refs/heads/main/adm_struktur.xlsx"

st.set_page_config(page_title="Аналитика ПЧ-22", layout="wide")

@st.cache_data
def load_admin_structure(url):
    try:
        # Корректировка ссылки GitHub Raw
        url = url.replace("Nuch/raw/refs", "Nuch/refs")
        parsed_url = list(urllib.parse.urlparse(url))
        parsed_url[2] = urllib.parse.quote(parsed_url[2])
        encoded_url = urllib.parse.urlunparse(parsed_url)
        
        response = requests.get(encoded_url, timeout=15)
        response.raise_for_status() 
        
        df = pd.read_excel(io.BytesIO(response.content), engine='openpyxl')
        df.columns = [col.strip().upper() for col in df.columns]
        
        if 'КМКОН' in df.columns and 'КМНАЧ' in df.columns:
            df['ПЛАН_ДЛИНА'] = abs(df['КМКОН'] - df['КМНАЧ'])
        return df
    except Exception as e:
        st.error(f"❌ Ошибка справочника GitHub: {e}")
        return None

def calculate_metrics(group_name, group_data, level, plan_km=0):
    """Единая функция расчета Nуч и полноты"""
    fact_km = group_data["ПРОВЕРЕНО"].sum()
    
    # Распределение по оценкам
    km_5 = group_data[group_data["ОЦЕНКА"] == 5]["ПРОВЕРЕНО"].sum()
    km_4 = group_data[group_data["ОЦЕНКА"] == 4]["ПРОВЕРЕНО"].sum()
    km_3 = group_data[group_data["ОЦЕНКА"] == 3]["ПРОВЕРЕНО"].sum()
    km_2 = group_data[group_data["ОЦЕНКА"] == 2]["ПРОВЕРЕНО"].sum()

    n_uch = 0
    if fact_km > 0:
        n_uch = (km_5*5 + km_4*4 + km_3*3 - km_2*5) / fact_km

    return {
        "Уровень": level,
        "Группа": group_name,
        "Nуч": round(n_uch, 2),
        "Проверено (км)": round(fact_km, 3),
        "План (км)": round(plan_km, 3),
        "Полнота %": round((fact_km / plan_km * 100), 1) if plan_km > 0 else 0,
        "Отл": round(km_5, 3),
        "Хор": round(km_4, 3),
        "Удов": round(km_3, 3),
        "Неуд": round(km_2, 3)
    }

# --- ИНТЕРФЕЙС ---
st.title("📊 Единая система аналитики ПЧ-22")
st.markdown("---")

df_struct = load_admin_structure(URL_STRUCT)

if df_struct is not None:
    st.sidebar.success("✅ Справочник структуры загружен")
    uploaded_file = st.sidebar.file_uploader("Загрузите файл 'Оценка КМ'", type=["xlsx"])
    
    if uploaded_file:
        try:
            # 1. Загрузка и фильтрация
            df_raw = pd.read_excel(uploaded_file, sheet_name="Оценка КМ")
            df_raw.columns = [col.strip().upper() for col in df_raw.columns]
            
            # Фильтр направлений (как в старой программе)
            main_codes = ['24701', '24602', '24603']
            df_eval = df_raw[df_raw["КОДНАПР"].astype(str).isin(main_codes)].copy()

            # 2. План из справочника
            pd_plan_map = df_struct.groupby('ПД')['ПЛАН_ДЛИНА'].sum().to_dict()

            # 3. Расчет Линейных (ПД)
            final_stats = []
            for pd_id, group in df_eval.groupby("ПД"):
                p_km = pd_plan_map.get(pd_id, 0)
                final_stats.append(calculate_metrics(f"ПД-{pd_id}", group, "Линейный", p_km))

            # 4. Расчет Групповых (ПЧЗ / ПЧУ)
            groups_config = {
                "ПЧЗ Юг": [1, 2, 3, 4, 5, 12],
                "ПЧЗ Запад": [6, 7, 8, 9, 10, 11, 13, 14, 15],
                "ПЧУ-2": [4, 5, 12]
            }
            
            for g_name, pds in groups_config.items():
                g_data = df_eval[df_eval["ПД"].isin(pds)]
                g_plan = sum([pd_plan_map.get(p, 0) for p in pds])
                final_stats.append(calculate_metrics(g_name, g_data, "Групповой", g_plan))

            results_df = pd.DataFrame(final_stats)

            # --- МЕТРИКИ ---
            total_fact = df_eval["ПРОВЕРЕНО"].sum()
            total_plan = sum(pd_plan_map.values())
            
            c1, c2, c3 = st.columns(3)
            with c1:
                avg_n = results_df[results_df["Уровень"]=="Групповой"]["Nуч"].mean()
                st.metric("Средний Nуч по ПЧ", round(avg_n, 2))
            with c2:
                st.metric("Полнота проверки", f"{round(total_fact/total_plan*100, 1)}%")
            with c3:
                st.metric("Неуд (км)", round(df_eval[df_eval['ОЦЕНКА']==2]['ПРОВЕРЕНО'].sum(), 2))

            # --- ВИЗУАЛИЗАЦИЯ ---
            tab1, tab2, tab3 = st.tabs(["📋 Итоги", "📈 Графики", "🔍 Целостность пути"])

            with tab1:
                st.dataframe(
                    results_df.style.background_gradient(subset=['Nуч'], cmap='RdYlGn', vmin=3, vmax=5)
                    .background_gradient(subset=['Полнота %'], cmap='YlOrRd', vmin=80, vmax=100),
                    use_container_width=True
                )

            with tab2:
                fig = px.bar(results_df[results_df["Уровень"]=="Линейный"], 
                             x="Группа", y="Nуч", color="Полнота %", 
                             title="Качество по ПД (Цвет = Полнота)", text_auto=True)
                st.plotly_chart(fig, use_container_width=True)

            with tab3:
                st.subheader("Сверка по Пути и Направлению")
                path_fact = df_eval.groupby(['КОДНАПР', 'ПУТЬ', 'ПД'])['ПРОВЕРЕНО'].sum().reset_index()
                path_plan = df_struct.groupby(['НАПРАВЛЕНИЕ', 'ПУТЬ', 'ПД'])['ПЛАН_ДЛИНА'].sum().reset_index()
                
                detail_check = path_plan.merge(
                    path_fact, left_on=['НАПРАВЛЕНИЕ','ПУТЬ','ПД'], 
                    right_on=['КОДНАПР','ПУТЬ','ПД'], how='left'
                ).fillna(0)
                detail_check['ДЕФИЦИТ (КМ)'] = (detail_check['ПЛАН_ДЛИНА'] - detail_check['ПРОВЕРЕНО']).round(3)
                st.dataframe(detail_check.drop(columns=['КОДНАПР']), use_container_width=True)

            # --- ЭКСПОРТ EXCEL ---
            st.sidebar.markdown("---")
            st.sidebar.header("📥 Скачать отчет")
            
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                results_df.to_excel(writer, sheet_name='ИТОГИ_ОБЩИЕ', index=False)
                detail_check.to_excel(writer, sheet_name='ПОЛНОТА_ДЕТАЛЬНО', index=False)
                # Разделение по категориям
                for score, name in {5: "Отличные", 4: "Хорошие", 3: "Удовл", 2: "Неуд"}.items():
                    subset = df_eval[df_eval["ОЦЕНКА"] == score]
                    subset.to_excel(writer, sheet_name=name, index=False)

            st.sidebar.download_button(
                label="Скачать Excel (.xlsx)",
                data=buffer.getvalue(),
                file_name="Analiz_PCH22_Full.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        except Exception as e:
            st.error(f"Ошибка в коде: {e}")
            st.exception(e)
else:
    st.info("Ожидание подключения справочника...")
