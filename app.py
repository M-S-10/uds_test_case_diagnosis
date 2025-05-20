import streamlit as st
from bs4 import BeautifulSoup
import pandas as pd
import re
from io import BytesIO

st.title("Vector CANoe HTML Test Report - Failure Extractor")

uploaded_file = st.file_uploader("Upload Vector CANoe HTML file", type="html")

if uploaded_file:
    soup = BeautifulSoup(uploaded_file, "html.parser")
    fail_data = []

    # Locate test cases with failure
    test_cases = soup.find_all("td", class_="TestcaseHeadingNegativeResult")

    for heading in test_cases:
        heading_text = heading.get_text(strip=True)
        match = re.search(r'Test Case ([\d\/]+): (.+): Failed', heading_text)
        if not match:
            continue
        tc_id, tc_name = match.groups()

        # Find the "Main Part of Test Case"
        main_part_tag = heading.find_next("big", string=re.compile("Main Part of Test Case"))
        if not main_part_tag:
            continue
        result_table = main_part_tag.find_parent("table").find_next_sibling("div").find("table", class_="ResultTable")

        if not result_table:
            continue

        for row in result_table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) == 4 and "NegativeResultCell" in cells[3].get("class", []):
                timestamp = cells[0].get_text(strip=True)
                step = cells[1].get_text(strip=True)
                description = cells[2].get_text(strip=True)
                fail_data.append((tc_id, tc_name, timestamp, step, description))

    if fail_data:
        df = pd.DataFrame(fail_data, columns=[
            "Test Case ID", "Test Case Name", "Timestamp", "Test Step", "Fail Description"
        ])

        df["Count"] = df.groupby(["Test Case ID", "Test Case Name", "Fail Description"])["Fail Description"].transform("count")
        df_summary = df.drop_duplicates(subset=["Test Case ID", "Test Case Name", "Fail Description"])

        st.success(f"✅ Extracted {len(df_summary)} unique failures.")
        st.dataframe(df_summary)

        # Export to Excel
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_summary.to_excel(writer, index=False, sheet_name='Failures')
        output.seek(0)

        st.download_button("📥 Download as Excel", data=output, file_name="failures_summary.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.warning("No failures found in the uploaded report.")
