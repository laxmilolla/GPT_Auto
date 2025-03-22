import os
import re
import pandas as pd
from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright

app = Flask(__name__)

# Setup upload folder
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# 🔍 Main validation logic
def filter_and_compare(playwright, breed_name, file_path):
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    print(f"🌐 Navigating to site and applying filter for: {breed_name}")
    page.goto("https://caninecommons.cancer.gov/#/explore")
    page.get_by_role("button", name="Continue").click()

    # ✅ Simpler click on 'Breed' filter
    page.locator("text=Breed").click()

    # 🖱 Click specific breed checkbox
    checkbox_id = f"#checkbox_Breed_{breed_name.replace(' ', '_')}"
    print(f"Clicking: {checkbox_id}")
    page.wait_for_selector(checkbox_id, timeout=5000)
    page.locator(checkbox_id).click()

    page.wait_for_selector("table tbody tr", timeout=10000)
    print("📋 Scraping table data...")

    # Scrape data skipping checkbox column
    column_names = [
        "Case ID", "Study Code", "Study Type", "Breed", "Diagnosis", "Stage Of Disease",
        "Age", "Sex", "Neutered Status", "Weight (kg)", "Response to Treatment", "Cohort"
    ]

    rows = page.query_selector_all("table tbody tr")
    scraped_data = []

    for row in rows:
        cells = row.query_selector_all("td")
        row_data = [cell.inner_text().strip() for cell in cells[1:]]  # skip first (checkbox)
        if len(row_data) > len(column_names):
            row_data = row_data[:len(column_names)]
        elif len(row_data) < len(column_names):
            row_data += [""] * (len(column_names) - len(row_data))
        scraped_data.append(row_data)

    df_ui = pd.DataFrame(scraped_data, columns=column_names)
    df_ui.columns = [col.lower() for col in df_ui.columns]
    df_ui = df_ui.sort_values(by=df_ui.columns.tolist()).reset_index(drop=True)

    print(f"✅ Scraped {len(df_ui)} UI records.")

    # Load TSV and normalize
    df_tsv = pd.read_csv(file_path, sep="\t")
    df_tsv.columns = [col.lower() for col in df_tsv.columns]
    df_tsv = df_tsv.sort_values(by=df_tsv.columns.tolist()).reset_index(drop=True)

    # Find matching columns
    common_cols = [col for col in df_ui.columns if col in df_tsv.columns]
    df_ui = df_ui[common_cols]
    df_tsv = df_tsv[common_cols]

    # Compare
    diff = df_ui.compare(df_tsv, keep_shape=True, keep_equal=False)

    if diff.empty:
        return {"result": f"✅ PASS: UI matches uploaded TSV for breed '{breed_name}'"}
    else:
        diff_path = os.path.join("uploads", "comparison_report.csv")
        diff.to_csv(diff_path, index=False)
        return {
            "result": f"❌ FAIL: Mismatches found for breed '{breed_name}'",
            "report": f"Saved diff report at: {diff_path}"
        }

# 🚀 Flask endpoint
@app.route('/validate', methods=['POST'])
def validate():
    if 'file' not in request.files:
        return jsonify({"result": "❌ No file part"}), 400

    file = request.files['file']
    breed = request.form.get('breed', '').strip()

    if not file or not breed:
        return jsonify({"result": "❌ Missing file or breed"}), 400

    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(file_path)

    with sync_playwright() as playwright:
        result = filter_and_compare(playwright, breed, file_path)

    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True)