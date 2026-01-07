import streamlit as st
import pandas as pd
import io
import plotly.express as px

# --- НАСТРОЙКИ ---
# ЗАМЕНИТЕ ЭТУ ССЫЛКУ на прямую ссылку (Raw) из вашего GitHub репозитория
URL_STRUCT = "https://github.com/denmalysheff/Nuch/blob/main/adm_struktur.xlsx"

st.set_page_config(page_title="Аналитика Nуч ПЧ", layout="wide")

st.title("📊 Система мониторинга балловой оценки и полноты проверки")
st.markdown("---")

# Функция загрузки структуры (кэшируем, чтобы не качать при каждом клике)
@st.cache_data
def load_admin_structure(url):
    try:
        if url.endswith('.csv'):
            df = pd.read_csv(url)
        else:
            df = pd.read_excel(url)
        
        # Расчет плановой длины
        df['ПЛАН_ДЛИНА'] = abs(df['КМКОН'] - df['КМНАЧ'])
        return df
    except Exception as e:
        st.error(f"Не удалось загрузить справочник структуры с GitHub: {e}")
        return None

def calculate_nuch(group_name, group, level):
    total_length = group["ПРОВЕРЕНО"].sum()
    excellent_km = round(group[group["ОЦЕНКА"] == 5]["ПРОВЕРЕНО"].sum(), 3)
    good_km = round(group[group["ОЦЕНКА"] == 4]["ПРОВЕРЕНО"].sum(), 3)
    satisfactory_km = round(group[group["ОЦЕНКА"] == 3]["ПРОВЕРЕНО"].sum(), 3)
    unsatisfactory_km = round(group[group["ОЦЕНКА"] == 2]["ПРОВЕРЕНО"].sum(), 3)

    n_uch = 0
    if total_length > 0:
        n_uch = round((excellent_km * 5 + good_km * 4 + satisfactory_km * 3 - unsatisfactory_km * 5) / total_length, 2)

    return {
        "Уровень": level,
        "Группа": group_name,
        "Nуч": n_uch,
        "отл": excellent_km,
        "хор": good_km,
        "удов": satisfactory_km,
        "неуд": unsatisfactory_km,
        "проверено": round(total_length, 3)
    }

# --- ПОДГОТОВКА ДАННЫХ ---
df_struct = load_admin_structure(URL_STRUCT)

st.sidebar.header("📂 Загрузка данных")
uploaded_file = st.sidebar.file_uploader("Загрузите файл 'Оценка КМ' (xlsx)", type=["xlsx"])

if uploaded_file and df_struct is not None:
    try:
        # 1. Обработка справочника
        pd_plan = df_struct.groupby('ПД')['ПЛАН_ДЛИНА'].sum().reset_index()

        # 2. Загрузка данных пользователя
        df = pd.read_excel(uploaded_file, sheet_name="Оценка КМ")
        
        required_cols = {"КОДНАПР", "ОЦЕНКА", "ПД", "ПРОВЕРЕНО"}
        if not required_cols.issubset(df.columns):
            st.error(f"В файле отсутствуют необходимые колонки: {required_cols - set(df.columns)}")
        else:
            # Фильтрация по кодам направлений
            filtered_df = df[df["КОДНАПР"].isin([24701, 24602, 24603])].copy()

            # Расчет Nуч
            results = []
            for pd_id, group in filtered_df.groupby("ПД"):
                results.append(calculate_nuch(str(pd_id), group, "Линейный"))

            # Групповые расчеты
            groups_map = {
                "ПЧЗ Юг": [1, 2, 3, 4, 5, 12],
                "ПЧЗ Запад": [6, 7, 8, 9, 10, 11, 13, 14, 15],
                "ПЧУ-2": [4, 5, 12]
            }
            for label, pds in groups_map.items():
                group_data = filtered_df[filtered_df["ПД"].isin(pds)]
                results.append(calculate_nuch(label, group_data, "Групповой"))

            results_df = pd.DataFrame(results)

            # 3. Анализ полноты (Слияние факта и плана)
            # Берем только линейные участки для сравнения
            fact_pd = results_df[results_df["Уровень"] == "Линейный"].copy()
            fact_pd["Группа"] = pd.to_numeric(fact_pd["Группа"])
            
            completeness = pd_plan.merge(fact_pd, left_on="ПД", right_on="Группа", how="left")
            completeness["проверено"] = completeness["проверено"].fillna(0)
            completeness["Процент"] = round((completeness["проверено"] / completeness["ПЛАН_ДЛИНА"]) * 100, 1)
            completeness["Остаток"] = round(completeness["ПЛАН_ДЛИНА"] - completeness["проверено"], 3)

            # --- ИНТЕРФЕЙС ---
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Качество (Nуч)")
                fig_n = px.bar(fact_pd, x="Группа", y="Nуч", color="Nуч", color_continuous_scale="RdYlGn")
                st.plotly_chart(fig_n, use_container_width=True)

            with col2:
                st.subheader("Полнота проверки (%)")
                fig_p = px.bar(completeness, x="ПД", y="Процент", color="Процент", 
                               range_y=[0, 105], color_continuous_scale="Blues")
                st.plotly_chart(fig_p, use_container_width=True)

            tab1, tab2, tab3 = st.tabs(["📊 Итоги Nуч", "✅ Детальная полнота", "⚠️ Ошибки/Неуды"])

            with tab1:
                st.dataframe(results_df, use_container_width=True)

            with tab2:
                st.dataframe(
                    completeness[["ПД", "ПЛАН_ДЛИНА", "проверено", "Процент", "Остаток"]]
                    .style.background_gradient(subset=["Процент"], cmap="RdYlGn")
                )

            with tab3:
                unsat = filtered_df[filtered_df["ОЦЕНКА"] == 2]
                if not unsat.empty:
                    st.warning(f"Выявлено неудовлетворительных километров: {len(unsat)}")
                    st.dataframe(unsat[["ПД", "KM", "ПУТЬ", "ПРИЧИНА"]])
                
                missing = completeness[completeness["Процент"] < 90]
                if not missing.empty:
                    st.error("Участки с низким процентом проверки (менее 90%):")
                    st.dataframe(missing[["ПД", "ПЛАН_ДЛИНА", "проверено", "Процент"]])

            # --- ЭКСПОРТ ---
            st.sidebar.markdown("---")
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                results_df.to_excel(writer, sheet_name="ИТОГИ_Nуч", index=False)
                completeness.to_excel(writer, sheet_name="ПОЛНОТА", index=False)
                filtered_df[filtered_df["ОЦЕНКА"] == 2].to_excel(writer, sheet_name="НЕУДЫ", index=False)
            
            st.sidebar.download_button("📥 Скачать отчет", output.getvalue(), "Report.xlsx")

    except Exception as e:
        st.error(f"Ошибка обработки: {e}")

elif df_struct is None:
    st.warning("⚠️ Ошибка: Справочник структуры не загружен с GitHub. Проверьте ссылку URL_STRUCT.")
else:
    st.info("👋 Загрузите файл 'Оценка КМ' для начала анализа.")

st.sidebar.caption("Справочник структуры: подключен (GitHub)")

