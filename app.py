import streamlit as st
import pandas as pd
import re
from io import BytesIO
import os

st.set_page_config(page_title="CANoe Failure Extractor", layout="wide")

st.title("Vector CANoe HTML Test Report - Failure Extractor")

uploaded_file = st.file_uploader("Upload Vector CANoe HTML file", type="html")


def process_html_stream(uploaded_file):
    fail_data = []

    tc_id, tc_name = None, None
    inside_fail_section = False

    progress_bar = st.progress(0)
    status_text = st.empty()

    # ✅ Get total size (for progress)
    total_size = uploaded_file.size
    bytes_processed = 0

    chunk_size = 1024 * 1024  # 1 MB chunks

    # ✅ Reset pointer
    uploaded_file.seek(0)

    for chunk in uploaded_file:
        bytes_processed += len(chunk)

        # ✅ Update progress
        progress = min(bytes_processed / total_size, 1.0)
        progress_bar.progress(progress)
        status_text.text(f"Processing... {int(progress * 100)}%")

        # ✅ Decode chunk
        lines = chunk.decode("utf-8", errors="ignore").splitlines()

        for line in lines:
            # ✅ Detect failed test case
            if "TestcaseHeadingNegativeResult" in line:
                match = re.search(r'Test Case ([\d\/]+): (.+?): Failed', line)
                if match:
                    tc_id, tc_name = match.groups()
                    inside_fail_section = True
                continue

            # ✅ End of block
            if inside_fail_section and "</table>" in line:
                inside_fail_section = False
                continue

            # ✅ Extract failed rows
            if inside_fail_section and "NegativeResultCell" in line:
                cols = re.findall(r'<td.*?>(.*?)</td>', line)

                if len(cols) >= 3:
                    clean = lambda x: re.sub('<.*?>', '', x).strip()

                    fail_data.append((
                        tc_id,
                        tc_name,
                        clean(cols[0]),
                        clean(cols[1]) if len(cols) > 1 else "",
                        clean(cols[2]) if len(cols) > 2 else ""
                    ))

    progress_bar.progress(100)
    status_text.text("✅ Processing complete!")

    if not fail_data:
        return None, None

    df = pd.DataFrame(fail_data, columns=[
        "Test Case ID", "Test Case Name", "Timestamp", "Test Step", "Fail Description"
    ])

    df["Count"] = df.groupby(
        ["Test Case ID", "Test Case Name", "Fail Description"]
    )["Fail Description"].transform("count")

    df_summary = df.drop_duplicates(
        subset=["Test Case ID", "Test Case Name", "Fail Description"]
    )

    return df_summary, len(df_summary)


if uploaded_file:
    try:
        with st.spinner("🔄 Processing large HTML report efficiently..."):
            df_summary, count = process_html_stream(uploaded_file)

        if df_summary is None:
            st.warning("No failures found in the uploaded report.")
        else:
            st.success(f"✅ Extracted {count} unique failures.")

            # ✅ Safe display
            st.dataframe(df_summary.head(1000), use_container_width=True)

            if len(df_summary) > 1000:
                st.info("Showing first 1000 rows. Download full file below.")

            # ✅ Export
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
        st.error(f"❌ Error: {str(e)}")

else:
    st.info("Please upload a CANoe HTML report file.")
