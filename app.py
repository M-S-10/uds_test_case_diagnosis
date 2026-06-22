import streamlit as st
from bs4 import BeautifulSoup
import pandas as pd
import re
from io import BytesIO
import os

st.set_page_config(page_title="CANoe Failure Extractor", layout="wide")

st.title("Vector CANoe HTML Test Report - Failure Extractor")

uploaded_file = st.file_uploader("Upload Vector CANoe HTML file", type="html")


# ✅ Cache processing to avoid recomputation
@st.cache_data(show_spinner=True)
def process_html(html_bytes):
    html_content = html_bytes.decode("utf-8", errors="ignore")

    # ✅ Use faster parser
    soup = BeautifulSoup(html_content, "lxml")

    fail_data = []

    # ✅ Find only failed test cases
    test_cases = soup.find_all("td", class_="TestcaseHeadingNegativeResult")

    for heading in test_cases:
        heading_text = heading.get_text(strip=True)

        match = re.search(r'Test Case ([\d\/]+): (.+): Failed', heading_text)
        if not match:
            continue

        tc_id, tc_name = match.groups()

        # ✅ Efficient "Main Part" lookup
        main_part_tag = heading.find_next(
            lambda tag: tag.name == "big" and "Main Part of Test Case" in tag.text
        )
        if not main_part_tag:
            continue

        parent_table = main_part_tag.find_parent("table")
        if not parent_table:
            continue

        next_div = parent_table.find_next_sibling("div")
        if not next_div:
            continue

        result_table = next_div.find("table", class_="ResultTable")
        if not result_table:
            continue

        # ✅ Extract failed rows only
        for row in result_table.find_all("tr"):
            cells = row.find_all("td")

            if len(cells) < 4:
                continue

            classes = cells[3].get("class", [])
            if "NegativeResultCell" not in classes:
                continue

            fail_data.append((
                tc_id,
                tc_name,
                cells[0].get_text(strip=True),
                cells[1].get_text(strip=True),
                cells[2].get_text(strip=True)
            ))

    # ✅ Convert to DataFrame safely
    if not fail_data:
        return None, None

    df = pd.DataFrame(fail_data, columns=[
        "Test Case ID", "Test Case Name", "Timestamp", "Test Step", "Fail Description"
    ])

    # ✅ Optimize grouping
    df["Count"] = df.groupby(
        ["Test Case ID", "Test Case Name", "Fail Description"]
    )["Fail Description"].transform("count")

    df_summary = df.drop_duplicates(
        subset=["Test Case ID", "Test Case Name", "Fail Description"]
    )

    return df_summary, len(df_summary)


if uploaded_file:
    try:
        # ✅ Read ONCE (important for large files)
        html_bytes = uploaded_file.read()

        with st.spinner("🔄 Processing large HTML report..."):
            df_summary, count = process_html(html_bytes)

        if df_summary is None or df_summary.empty:
            st.warning("No failures found in the uploaded report.")
        else:
            st.success(f"✅ Extracted {count} unique failures.")

            # ✅ Prevent UI crash for large datasets
            st.dataframe(df_summary.head(1000), use_container_width=True)

            if len(df_summary) > 1000:
                st.info("Showing first 1000 rows. Download full file below.")

            # ✅ Excel export
            html_filename = uploaded_file.name
            base_name = os.path.splitext(html_filename)[0]
            output_filename = f"{base_name}.xlsx"

            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_summary.to_excel(writer, index=False, sheet_name='Failures')

            output.seek(0)

            st.download_button(
                label=f"📥 Download '{output_filename}'",
                data=output,
                file_name=output_filename,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except Exception as e:
        st.error(f"❌ Error processing file: {str(e)}")

else:
    st.info("Please upload a CANoe HTML report file.")
