import streamlit as st
import pandas as pd
import io
import requests
import urllib.parse

# --- НАСТРОЙКИ ---
URL_STRUCT = "https://raw.githubusercontent.com/denmalysheff/Nuch/refs/heads/main/adm_struktur.xlsx"

st.set_page_config(page_title="Аналитика ПЧ-22", layout="wide")

@st.cache_data
def load_admin_structure(url):
    try:
        # Очистка ссылки
        url = url.replace("Nuch/raw/refs", "Nuch/refs")
        parsed_url = list(urllib.parse.urlparse(url))
        parsed_url[2] = urllib.parse.quote(parsed_url[2])
        encoded_url = urllib.parse.urlunparse(parsed_url)
        
        response = requests.get(encoded_url, timeout=15)
        response.raise_for_status() 
        
        df = pd.read_excel(io.BytesIO(response.content), engine='openpyxl')
        df.columns = [col.strip().upper() for col in df.columns]
        
        # Расчет плановой длины из КМНАЧ и КМКОН
        if 'КМКОН' in df.columns and 'КМНАЧ' in df.columns:
            df['ПЛАН_ДЛИНА'] = abs(df['КМКОН'] - df['КМНАЧ'])
        return df
    except Exception as e:
        st.error(f"❌ Ошибка справочника: {e}")
        return None

st.title("📊 Мониторинг полноты оценки участков")

df_struct = load_admin_structure(URL_STRUCT)

if df_struct is not None:
    st.sidebar.success("✅ Справочник структуры загружен")
    uploaded_file = st.sidebar.file_uploader("Загрузите файл 'Оценка КМ'", type=["xlsx"])
    
    if uploaded_file:
        try:
            # Загружаем факт
            df_eval = pd.read_excel(uploaded_file, sheet_name="Оценка КМ")
            df_eval.columns = [col.strip().upper() for col in df_eval.columns]

            # Группируем ПЛАН (из GitHub) по Направлению, Пути и ПД
            # Приводим типы к строкам для надежности слияния
            df_struct['НАПРАВЛЕНИЕ'] = df_struct['НАПРАВЛЕНИЕ'].astype(str)
            df_struct['ПУТЬ'] = df_struct['ПУТЬ'].astype(str)
            
            plan_grouped = df_struct.groupby(['НАПРАВЛЕНИЕ', 'ПУТЬ', 'ПД'])['ПЛАН_ДЛИНА'].sum().reset_index()

            # Группируем ФАКТ (из файла) по тем же полям
            df_eval['КОДНАПР'] = df_eval['КОДНАПР'].astype(str)
            df_eval['ПУТЬ'] = df_eval['ПУТЬ'].astype(str)
            
            fact_grouped = df_eval.groupby(['КОДНАПР', 'ПУТЬ', 'ПД'])['ПРОВЕРЕНО'].sum().reset_index()

            # Слияние по трем условиям: Направление, Путь, ПД
            summary = plan_grouped.merge(
                fact_grouped, 
                left_on=['НАПРАВЛЕНИЕ', 'ПУТЬ', 'ПД'], 
                right_on=['КОДНАПР', 'ПУТЬ', 'ПД'], 
                how='left'
            ).fillna(0)

            summary['ПРОЦЕНТ %'] = (summary['ПРОВЕРЕНО'] / summary['ПЛАН_ДЛИНА'] * 100).round(1)
            
            # Убираем лишний столбец после слияния
            if 'КОДНАПР' in summary.columns:
                summary = summary.drop(columns=['КОДНАПР'])

            st.subheader("Детальный отчет по участкам (Направление + Путь + ПД)")
            
            # Безопасное отображение таблицы с градиентом
            try:
                st.dataframe(
                    summary.style.background_gradient(subset=['ПРОЦЕНТ %'], cmap='RdYlGn', vmin=0, vmax=100),
                    use_container_width=True
                )
            except:
                # Если matplotlib все еще не виден, выводим простую таблицу
                st.dataframe(summary, use_container_width=True)

            # Итого по ПД (агрегировано)
            st.subheader("Итоговая полнота по ПД (все пути)")
            pd_summary = summary.groupby('ПД')[['ПЛАН_ДЛИНА', 'ПРОВЕРЕНО']].sum().reset_index()
            pd_summary['ПРОЦЕНТ %'] = (pd_summary['ПРОВЕРЕНО'] / pd_summary['ПЛАН_ДЛИНА'] * 100).round(1)
            st.table(pd_summary)

        except Exception as e:
            st.error(f"Ошибка обработки: {e}")
            st.exception(e) # Позволит увидеть детали ошибки
