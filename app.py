import os
from flask import Flask, request, jsonify
from playwright.sync_api import sync_playwright
import pandas as pd
import re

app = Flask(__name__)

# Set up a directory for uploading files
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Function to scrape and validate data
def filter_and_compare(playwright, breed_name, file_path):
    browser = playwright.chromium.launch(headless=False)  # Set to False to see the browser
    context = browser.new_context()
    page = context.new_page()

    # Open website and apply the breed filter
    page.goto("https://caninecommons.cancer.gov/#/explore")
    page.locator("button", has_text="Continue").click()  # Click "Continue"

    # Wait for the 'Breed' filter button to be visible and stable
    print("Waiting for the Breed filter button to be clickable...")
    page.wait_for_selector("div", timeout=10000)  # Wait for div containing the filter to appear
    page.get_by_role("button", name="Breed").click()
    # Build checkbox ID dynamically and click it
    checkbox_id = f"#checkbox_Breed_{breed_name.replace(' ', '_')}"
    page.wait_for_selector(checkbox_id, timeout=5000)
    print(f"🖱 Clicking checkbox for breed: {breed_name}")
    page.locator("//div[@id='Breed' and @role='button' and @tabindex='0']").click()
    # Wait for the table to load and scrape it
    page.wait_for_selector("table tbody tr", timeout=10000)
    rows = page.query_selector_all("table tbody tr")
    
    # Scrape data, ignoring the first column (checkbox)
    ui_data = []
    for row in rows:
        cells = row.query_selector_all("td")
        # Skipping the first column (checkbox) and scraping the rest
        cell_text = [cell.inner_text().strip() for cell in cells[1:]]  # Skip the first column (checkbox)
        ui_data.append(cell_text)

    # Ensure the columns are correctly aligned with the TSV data
    column_names = [
        "Case ID", "Study Code", "Study Type", "Breed", "Diagnosis", "Stage of Disease", 
        "Age", "Sex", "Neutered Status", "Weight (kg)", "Response to Treatment", "Cohort"
    ]
    df_ui = pd.DataFrame(ui_data, columns=column_names)

    print(f"✅ Scraped {len(df_ui)} rows from UI.")

    # Load TSV data
    print("📁 Loading local TSV data...")
    df_tsv = pd.read_csv(file_path, sep="\t")

    # Ensure the column headers match for comparison
    if list(df_ui.columns) != list(df_tsv.columns):
        return {"result": f"❌ Column mismatch between UI and TSV. Columns in UI: {df_ui.columns.tolist()}, Columns in TSV: {df_tsv.columns.tolist()}"}

    # Compare the data
    merged = df_ui.merge(df_tsv, how="outer", indicator=True)
    mismatches = merged[merged["_merge"] != "both"]

    if mismatches.empty:
        return {"result": "✅ PASS: UI data matches the TSV for breed = " + breed_name}
    else:
        return {
            "result": "❌ FAIL: Mismatches found",
            "mismatches": mismatches.to_dict(orient="records")
        }

    browser.close()

# Flask endpoint to handle file upload and breed validation
@app.route('/validate', methods=['POST'])
def validate():
    if 'file' not in request.files:
        return jsonify({"result": "❌ No file part"}), 400

    file = request.files['file']
    breed = request.form.get('breed', '').strip()

    if not breed:
        return jsonify({"result": "❌ No breed provided"}), 400

    # Save the uploaded file to the server
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(file_path)

    with sync_playwright() as playwright:
        result = filter_and_compare(playwright, breed, file_path)

    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True)