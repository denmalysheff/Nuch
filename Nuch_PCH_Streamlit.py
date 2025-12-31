import streamlit as st
import pandas as pd
import io
import plotly.express as px  # Для графиков

# Настройка страницы
st.set_page_config(page_title="Аналитика Nуч ПЧ", layout="wide")

st.title("📊 Расширенный расчет балловой оценки")
st.markdown("---")


def calculate_nuch(group_name, group, level):
    total_length = group["ПРОВЕРЕНО"].sum()
    # Округление до 3 знаков для точности километров
    excellent_km = round(group[group["ОЦЕНКА"] == 5]["ПРОВЕРЕНО"].sum(), 3)
    good_km = round(group[group["ОЦЕНКА"] == 4]["ПРОВЕРЕНО"].sum(), 3)
    satisfactory_km = round(group[group["ОЦЕНКА"] == 3]["ПРОВЕРЕНО"].sum(), 3)
    unsatisfactory_km = round(group[group["ОЦЕНКА"] == 2]["ПРОВЕРЕНО"].sum(), 3)

    if total_length == 0:
        n_uch = 0
    else:
        # Формула расчета Nуч
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


# --- ИНТЕРФЕЙС ЗАГРУЗКИ ---
st.sidebar.header("📂 Входные данные")
uploaded_file = st.sidebar.file_uploader("Загрузите Excel-файл (Лист 'Оценка КМ')", type=["xlsx"])

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file, sheet_name="Оценка КМ")

        # Проверка структуры
        required_columns = {"КОДНАПР", "ОЦЕНКА", "ПД", "KM", "ПУТЬ", "ПРОВЕРЕНО", "ПРИЧИНА"}
        if not required_columns.issubset(df.columns):
            st.error(f"Ошибка! В файле нет нужных колонок: {required_columns - set(df.columns)}")
        else:
            # 1. Фильтрация и подготовка
            filtered_df = df[df["КОДНАПР"].isin([24701, 24602, 24603])].copy()

            # 2. Расчеты
            results = []
            # По ПД
            for pd_name, group in filtered_df.groupby("ПД"):
                results.append(calculate_nuch(f"ПД-{pd_name}", group, "Линейный"))

            # По группам (Юг, Запад, ПЧУ)
            groups_map = {
                "ПЧЗ Юг": [1, 2, 3, 4, 5, 12],
                "ПЧЗ Запад": [6, 7, 8, 9, 10, 11, 13, 14, 15],
                "ПЧУ-2": [4, 5, 12]
            }

            for label, pds in groups_map.items():
                group_data = filtered_df[filtered_df["ПД"].isin(pds)]
                results.append(calculate_nuch(label, group_data, "Групповой"))

            # Общий итог
            results.append(calculate_nuch("ПЧ (ИТОГО)", filtered_df, "Предприятие"))

            results_df = pd.DataFrame(results)

            # --- ВИЗУАЛИЗАЦИЯ ---
            st.subheader("📈 Аналитика по подразделениям")

            # График Nуч по ПД
            pd_only = results_df[results_df["Уровень"] == "Линейный"]
            fig = px.bar(pd_only, x="Группа", y="Nуч",
                         title="Балловая оценка (Nуч) по ПД",
                         color="Nуч", color_continuous_scale="RdYlGn")
            st.plotly_chart(fig, use_container_width=True)

            # --- ТАБЛИЦЫ ---
            tab1, tab2, tab3 = st.tabs(["📋 Сводная таблица", "❌ Неудовлетворительные", "🔗 Связи данных"])

            with tab1:
                st.dataframe(results_df.style.highlight_max(axis=0, subset=['Nуч'], color='#90ee90'),
                             use_container_width=True)

            with tab2:
                unsat = filtered_df[filtered_df["ОЦЕНКА"] == 2][["ПД", "KM", "ПУТЬ", "ПРИЧИНА"]]
                if not unsat.empty:
                    st.warning(f"Обнаружено неудовлетворительных километров: {len(unsat)}")
                    st.table(unsat)
                else:
                    st.success("Неудовлетворительных километров нет!")

            with tab3:
                st.info("В этой вкладке показано, какие ПД входят в составные группы.")
                for label, pds in groups_map.items():
                    st.write(f"**{label}**: включает ПД № {', '.join(map(str, pds))}")

            # --- ФАЙЛ СО СВЯЗЯМИ (Многостраничный Excel) ---
            st.sidebar.markdown("---")
            st.sidebar.header("📥 Выгрузка")

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                results_df.to_excel(writer, sheet_name="ИТОГИ_Nуч", index=False)
                filtered_df.to_excel(writer, sheet_name="Все_данные_фильтр", index=False)
                # Листы по категориям
                for score, name in {5: "Отличные", 4: "Хорошие", 3: "Удовл", 2: "Неуд"}.items():
                    subset = filtered_df[filtered_df["ОЦЕНКА"] == score]
                    subset.to_excel(writer, sheet_name=name, index=False)

                # Лист со связями групп
                connections = pd.DataFrame([{"Группа": k, "Состав ПД": str(v)} for k, v in groups_map.items()])
                connections.to_excel(writer, sheet_name="Связи_групп", index=False)

            st.sidebar.download_button(
                label="Скачать полный отчет (.xlsx)",
                data=output.getvalue(),
                file_name="Анализ_ПЧ_Полный_Отчет.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except Exception as e:
        st.error(f"Ошибка: {e}")
else:
    st.info("Ожидание загрузки файла...")

st.sidebar.caption("Разработчик: Малышев ДВ")