import streamlit as st
import pandas as pd
import io
import requests
import urllib.parse

# --- НАСТРОЙКИ ---
# ЗАМЕНИТЕ на вашу RAW-ссылку
URL_STRUCT = "https://raw.githubusercontent.com/ВАШ_ЛОГИН/РЕПО/main/adm_struktur.xlsx"

st.set_page_config(page_title="Аналитика ПЧ", layout="wide")

@st.cache_data
def load_admin_structure(url):
    try:
        # Корректировка ссылки, если вставлена обычная вместо Raw
        if "github.com" in url and "raw.githubusercontent.com" not in url:
            url = url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
        
        # Кодирование кириллицы в URL
        parsed_url = list(urllib.parse.urlparse(url))
        parsed_url[2] = urllib.parse.quote(parsed_url[2])
        encoded_url = urllib.parse.urlunparse(parsed_url)
        
        response = requests.get(encoded_url, timeout=15)
        response.raise_for_status()
        
        f_bytes = io.BytesIO(response.content)
        if encoded_url.lower().endswith('.csv'):
            df = pd.read_csv(f_bytes, encoding='utf-8-sig')
        else:
            df = pd.read_excel(f_bytes, engine='openpyxl')
        
        # Приводим названия колонок к верхнему регистру, чтобы избежать ошибок
        df.columns = [col.upper() for col in df.columns]
        
        if 'КМКОН' in df.columns and 'КМНАЧ' in df.columns:
            df['ПЛАН_ДЛИНА'] = abs(df['КМКОН'] - df['КМНАЧ'])
        else:
            st.error(f"В справочнике не найдены колонки КМНАЧ/КМКОН. Найдено: {list(df.columns)}")
            return None
            
        return df
    except Exception as e:
        st.error(f"Ошибка загрузки справочника: {e}")
        return None

# --- ИНТЕРФЕЙС ---
st.title("📊 Система мониторинга")

df_struct = load_admin_structure(URL_STRUCT)

if df_struct is not None:
    st.sidebar.success("✅ Справочник структуры подключен")
    
    uploaded_file = st.sidebar.file_uploader("Загрузите 'Оценка КМ' (xlsx)", type=["xlsx"])
    
    if uploaded_file:
        try:
            # Читаем данные оценки
            df_eval = pd.read_excel(uploaded_file, sheet_name="Оценка КМ")
            df_eval.columns = [col.upper() for col in df_eval.columns] # Тоже в верхний регистр
            
            # --- ЛОГИКА ПРОВЕРКИ ПОЛНОТЫ ---
            # 1. Группируем паспортные данные из GitHub по ПД
            pd_plan = df_struct.groupby('ПД')['ПЛАН_ДЛИНА'].sum().reset_index()
            
            # 2. Считаем сколько реально проверено в файле оценки
            # (предполагаем, что колонка ПРОВЕРЕНО содержит длину участка)
            pd_fact = df_eval.groupby('ПД')['ПРОВЕРЕНО'].sum().reset_index()
            
            # 3. Объединяем
            check_df = pd_plan.merge(pd_fact, on='ПД', how='left').fillna(0)
            check_df['ПРОЦЕНТ'] = (check_df['ПРОВЕРЕНО'] / check_df['ПЛАН_ДЛИНА'] * 100).round(1)
            
            # Вывод результата
            st.subheader("Проверка полноты оценки по ПД")
            st.dataframe(check_df.style.background_gradient(subset=['ПРОЦЕНТ'], cmap='RdYlGn', vmin=0, vmax=100))
            
            # Если есть ПД с процентом < 100, выводим предупреждение
            low_coverage = check_df[check_df['ПРОЦЕНТ'] < 95]
            if not low_coverage.empty:
                st.warning(f"Внимание! Следующие ПД проверены не полностью: {low_coverage['ПД'].tolist()}")

        except Exception as e:
            st.error(f"Ошибка при обработке файла: {e}")
    else:
        st.info("Пожалуйста, загрузите файл 'Оценка КМ' для начала анализа.")
