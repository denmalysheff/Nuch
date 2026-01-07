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
        st.error(f"❌ Ошибка справочника: {e}")
        return None

def get_nuch_val(row):
    """Функция расчета Nуч для строки агрегированных данных"""
    total = row['ПРОВЕРЕНО']
    if total == 0: return 0
    # Расчет: (5*отл + 4*хор + 3*удов - 5*неуд) / всего
    val = (row['ОТЛ']*5 + row['ХОР']*4 + row['УДОВ']*3 - row['НЕУД']*5) / total
    return round(val, 2)

st.title("📊 Аналитика ПЧ: Полнота и Качество (Nуч)")

df_struct = load_admin_structure(URL_STRUCT)

if df_struct is not None:
    st.sidebar.success("✅ Справочник структуры загружен")
    uploaded_file = st.sidebar.file_uploader("Загрузите файл 'Оценка КМ'", type=["xlsx"])
    
    if uploaded_file:
        try:
            df_eval = pd.read_excel(uploaded_file, sheet_name="Оценка КМ")
            df_eval.columns = [col.strip().upper() for col in df_eval.columns]

            # --- 1. ПОДГОТОВКА ПЛАНА ---
            df_struct['НАПРАВЛЕНИЕ'] = df_struct['НАПРАВЛЕНИЕ'].astype(str)
            df_struct['ПУТЬ'] = df_struct['ПУТЬ'].astype(str)
            plan_grouped = df_struct.groupby(['НАПРАВЛЕНИЕ', 'ПУТЬ', 'ПД'])['ПЛАН_ДЛИНА'].sum().reset_index()

            # --- 2. ПОДГОТОВКА ФАКТА И КАЧЕСТВА ---
            df_eval['КОДНАПР'] = df_eval['КОДНАПР'].astype(str)
            df_eval['ПУТЬ'] = df_eval['ПУТЬ'].astype(str)
            
            # Считаем километры по оценкам для каждой группы
            df_eval['ОТЛ'] = df_eval.apply(lambda r: r['ПРОВЕРЕНО'] if r['ОЦЕНКА'] == 5 else 0, axis=1)
            df_eval['ХОР'] = df_eval.apply(lambda r: r['ПРОВЕРЕНО'] if r['ОЦЕНКА'] == 4 else 0, axis=1)
            df_eval['УДОВ'] = df_eval.apply(lambda r: r['ПРОВЕРЕНО'] if r['ОЦЕНКА'] == 3 else 0, axis=1)
            df_eval['НЕУД'] = df_eval.apply(lambda r: r['ПРОВЕРЕНО'] if r['ОЦЕНКА'] == 2 else 0, axis=1)

            fact_grouped = df_eval.groupby(['КОДНАПР', 'ПУТЬ', 'ПД']).agg({
                'ПРОВЕРЕНО': 'sum',
                'ОТЛ': 'sum',
                'ХОР': 'sum',
                'УДОВ': 'sum',
                'НЕУД': 'sum'
            }).reset_index()

            # --- 3. СЛИЯНИЕ ---
            summary = plan_grouped.merge(
                fact_grouped, 
                left_on=['НАПРАВЛЕНИЕ', 'ПУТЬ', 'ПД'], 
                right_on=['КОДНАПР', 'ПУТЬ', 'ПД'], 
                how='left'
            ).fillna(0)

            summary['ПРОЦЕНТ %'] = (summary['ПРОВЕРЕНО'] / summary['ПЛАН_ДЛИНА'] * 100).round(1)
            summary['Nуч'] = summary.apply(get_nuch_val, axis=1)

            # --- 4. ИТОГИ ПО ВСЕЙ ДИСТАНЦИИ ---
            total_plan = summary['ПЛАН_ДЛИНА'].sum()
            total_fact = summary['ПРОВЕРЕНО'].sum()
            total_pct = round((total_fact / total_plan * 100), 1) if total_plan > 0 else 0
            
            avg_nuch = round((summary['Nуч'] * summary['ПРОВЕРЕНО']).sum() / total_fact, 2) if total_fact > 0 else 0

            # Отображение метрик
            m1, m2, m3 = st.columns(3)
            m1.metric("Общая полнота ПЧ", f"{total_pct}%", delta=f"{round(total_fact - total_plan, 2)} км")
            m2.metric("Средний Nуч по ПЧ", avg_nuch)
            m3.metric("Проверено км", f"{round(total_fact, 2)} из {round(total_plan, 2)}")

            # --- 5. ТАБЛИЦЫ ---
            tab1, tab2 = st.tabs(["📍 Детально по участкам", "🏢 Итого по ПД"])

            with tab1:
                cols_to_show = ['НАПРАВЛЕНИЕ', 'ПУТЬ', 'ПД', 'ПЛАН_ДЛИНА', 'ПРОВЕРЕНО', 'ПРОЦЕНТ %', 'Nуч']
                st.dataframe(
                    summary[cols_to_show].style.background_gradient(subset=['ПРОЦЕНТ %'], cmap='RdYlGn', vmin=0, vmax=100),
                    use_container_width=True
                )

            with tab2:
                pd_res = summary.groupby('ПД').agg({
                    'ПЛАН_ДЛИНА': 'sum',
                    'ПРОВЕРЕНО': 'sum',
                    'ОТЛ': 'sum', 'ХОР': 'sum', 'УДОВ': 'sum', 'НЕУД': 'sum'
                }).reset_index()
                pd_res['ПОЛНОТА %'] = (pd_res['ПРОВЕРЕНО'] / pd_res['ПЛАН_ДЛИНА'] * 100).round(1)
                pd_res['Nуч'] = pd_res.apply(get_nuch_val, axis=1)
                
                st.dataframe(
                    pd_res[['ПД', 'ПЛАН_ДЛИНА', 'ПРОВЕРЕНО', 'ПОЛНОТА %', 'Nуч']]
                    .style.background_gradient(subset=['Nуч'], cmap='RdYlGn', vmin=2, vmax=5),
                    use_container_width=True
                )

        except Exception as e:
            st.error(f"Ошибка в расчетах: {e}")
            st.exception(e)
