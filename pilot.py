import re
import pandas as pd
from playwright.sync_api import sync_playwright

def filter_and_compare(playwright, breed_name: str):
    browser = playwright.chromium.launch(headless=False)  # Set to False to see the browser
    context = browser.new_context()
    page = context.new_page()

    print(f"🔄 Navigating to site and applying filter for breed: {breed_name}")
    page.goto("https://caninecommons.cancer.gov/#/explore")
    page.get_by_role("button", name="Continue").click()

    # Open 'Breed' filter panel
    page.locator("div").filter(
        has_text=re.compile(r"^BreedSort alphabeticallySort by count$")
    ).get_by_role("button").click()

    # Build checkbox ID dynamically and click it
    checkbox_id = f"#checkbox_Breed_{breed_name.replace(' ', '_')}"
    print(f"🖱 Clicking checkbox: {checkbox_id}")
    page.wait_for_selector(checkbox_id, timeout=5000)
    page.locator(checkbox_id).click()

    # Wait for filtered table to load
    page.wait_for_selector("table tbody tr", timeout=10000)
    print("📋 Scraping filtered table data from UI...")

    rows = page.query_selector_all("table tbody tr")
    ui_data = []

    for row in rows:
        cells = row.query_selector_all("td")
        cell_text = [cell.inner_text().strip() for cell in cells]
        if len(cell_text) >= 6:
            ui_data.append({
                "Breed": cell_text[3],
                "Diagnosis": cell_text[4],
                "Stage of Disease": cell_text[5]
            })

    df_ui = pd.DataFrame(ui_data)
    print(f"✅ Scraped {len(df_ui)} rows from UI.")

    # Load and filter TSV
    print("📁 Loading local TSV data...")
    df_tsv = pd.read_csv("/Users/esiqa/cases.tsv", sep="\t")
    df_expected = df_tsv[df_tsv["Breed"].str.lower() == breed_name.lower()]

    # Compare TSV vs UI data
    print("🧪 Comparing UI data with TSV...")
    merged = pd.merge(df_ui, df_expected, how="outer", indicator=True)
    mismatches = merged[merged["_merge"] != "both"]

    # Label the mismatch source
    mismatches["Source"] = mismatches["_merge"].map({
        "left_only": "UI Extra",
        "right_only": "Missing in UI",
        "both": "Matched"
    })

    # Clean up columns
    final_report = mismatches[["Breed", "Diagnosis", "Stage of Disease", "Source"]]
    report_path = "comparison_report.csv"

    if final_report.empty:
        print(f"✅ PASS: All UI data matches the TSV for breed = {breed_name}")
        pd.DataFrame([], columns=["Breed", "Diagnosis", "Stage of Disease", "Source"]).to_csv(report_path, index=False)
    else:
        print("❌ FAIL: Differences found. Report generated:")
        print(final_report)
        final_report.to_csv(report_path, index=False)

    print(f"📄 Report saved as: {report_path}")
    print("🛑 Browser is still open. Please inspect manually.")
    input("👉 Press ENTER here after reviewing the browser window...")

    # NOTE: We do NOT close the browser so user can inspect manually
    # context.close()
    # browser.close()

# --- Manual startup to keep browser open ---
playwright = sync_playwright().start()
filter_and_compare(playwright, "Boxer")  # Replace "Boxer" with any breed from your TSV