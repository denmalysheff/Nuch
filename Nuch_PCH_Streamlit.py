import streamlit as st
import pandas as pd
import io
import requests
import urllib.parse

# --- НАСТРОЙКИ ---
# Вставьте сюда исправленную ссылку
URL_STRUCT = "https://raw.githubusercontent.com/denmalysheff/Nuch/refs/heads/main/adm_struktur.xlsx"

st.set_page_config(page_title="Аналитика ПЧ-22", layout="wide")

@st.cache_data
def load_admin_structure(url):
    try:
        # 1. Исправление типичных ошибок в ссылках GitHub
        if "github.com" in url and "raw.githubusercontent.com" not in url:
            url = url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
        
        # Убираем возможный лишний /raw/ в середине пути, который часто копируют по ошибке
        url = url.replace("Nuch/raw/refs", "Nuch/refs")

        # 2. Кодирование кириллицы
        parsed_url = list(urllib.parse.urlparse(url))
        parsed_url[2] = urllib.parse.quote(parsed_url[2])
        encoded_url = urllib.parse.urlunparse(parsed_url)
        
        # 3. Загрузка
        response = requests.get(encoded_url, timeout=15)
        response.raise_for_status() 
        
        f_bytes = io.BytesIO(response.content)
        # Если файл Excel
        df = pd.read_excel(f_bytes, engine='openpyxl')
        
        # Приводим названия колонок к единому стандарту (верхний регистр)
        df.columns = [col.strip().upper() for col in df.columns]
        
        # Расчет длины участков по паспорту
        if 'КМКОН' in df.columns and 'КМНАЧ' in df.columns:
            df['ПЛАН_ДЛИНА'] = abs(df['КМКОН'] - df['КМНАЧ'])
        
        return df
    except Exception as e:
        st.error(f"❌ Ошибка доступа к GitHub: {e}")
        st.info("Убедитесь, что файл в репозитории называется именно 'adm_struktur.xlsx'")
        return None

# --- ГЛАВНЫЙ ИНТЕРФЕЙС ---
st.title("📊 Мониторинг полноты проверки ПД")

df_struct = load_admin_structure(URL_STRUCT)

if df_struct is not None:
    st.sidebar.success("✅ Справочник структуры загружен")
    
    uploaded_file = st.sidebar.file_uploader("Загрузите файл 'Оценка КМ'", type=["xlsx"])
    
    if uploaded_file:
        try:
            # Читаем данные из загруженного файла
            df_eval = pd.read_excel(uploaded_file, sheet_name="Оценка КМ")
            df_eval.columns = [col.strip().upper() for col in df_eval.columns]

            # --- РАСЧЕТ ПОЛНОТЫ ---
            # Суммируем план из GitHub
            plan_by_pd = df_struct.groupby('ПД')['ПЛАН_ДЛИНА'].sum().reset_index()
            
            # Суммируем факт из загруженного файла
            fact_by_pd = df_eval.groupby('ПД')['ПРОВЕРЕНО'].sum().reset_index()
            
            # Слияние
            summary = plan_by_pd.merge(fact_by_pd, on='ПД', how='left').fillna(0)
            summary['ПРОЦЕНТ'] = (summary['ПРОВЕРЕНО'] / summary['ПЛАН_ДЛИНА'] * 100).round(1)
            
            # Отображение
            st.subheader("Сравнение паспортных данных и факта проверки")
            st.dataframe(
                summary.style.background_gradient(subset=['ПРОЦЕНТ'], cmap='RdYlGn', vmin=0, vmax=100),
                use_container_width=True
            )

        except Exception as e:
            st.error(f"Ошибка обработки файла: {e}")
    else:
        st.info("Ожидание загрузки файла оценки...")
