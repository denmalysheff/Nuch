import streamlit as st
import pandas as pd
import io
import requests
import urllib.parse

# --- НАСТРОЙКИ ---
# Убедитесь, что ссылка ведет на RAW файл (начинается с raw.githubusercontent.com)
URL_STRUCT = "https://github.com/denmalysheff/Nuch/blob/main/adm_struktur.xlsx"

@st.cache_data
def load_admin_structure(url):
    try:
        # 1. Кодируем URL на случай кириллицы
        parsed_url = list(urllib.parse.urlparse(url))
        parsed_url[2] = urllib.parse.quote(parsed_url[2])
        encoded_url = urllib.parse.urlunparse(parsed_url)
        
        # 2. Скачиваем файл через requests
        response = requests.get(encoded_url)
        response.raise_for_status()  # Проверка, что файл доступен
        
        # 3. Читаем из байтов
        file_bytes = io.BytesIO(response.content)
        
        if encoded_url.lower().endswith('.csv'):
            df = pd.read_csv(file_bytes, encoding='utf-8-sig')
        else:
            # Явно указываем движок openpyxl для Excel
            df = pd.read_excel(file_bytes, engine='openpyxl')
        
        # Расчет плановой длины
        df['ПЛАН_ДЛИНА'] = abs(df['КМКОН'] - df['КМНАЧ'])
        return df
    except Exception as e:
        st.error(f"Критическая ошибка загрузки справочника: {e}")
        return None

