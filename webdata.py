import re
import pandas as pd
from playwright.sync_api import sync_playwright

# Step 1: Apply Breed Filter
def filter_by_breed(playwright, breed_name: str):
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    print(f"🌐 Navigating to site and applying breed filter: {breed_name}")
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

    print(f"✅ Breed filter '{breed_name}' applied.")
    return page, context, browser


# Step 2: Capture UI Table and Save to CSV
def data_capture(page):
    print("📋 Scraping table...")

    page.wait_for_selector("table tbody tr", timeout=10000)

    # ✅ Correct headers without the checkbox column
    column_names = [
        "Case ID", "Study Code", "Study Type", "Breed", "Diagnosis",
        "Stage Of Disease", "Age", "Sex", "Neutered Status",
        "Weight (kg)", "Response to Treatment", "Cohort"
    ]

    rows = page.query_selector_all("table tbody tr")
    scraped_data = []

    for row in rows:
        cells = row.query_selector_all("td")

        # ⚠️ Skip the checkbox cell (first <td>)
        row_data = [cell.inner_text().strip() for cell in cells[1:]]

        # Ensure row matches header length
        if len(row_data) > len(column_names):
            row_data = row_data[:len(column_names)]
        elif len(row_data) < len(column_names):
            row_data += [""] * (len(column_names) - len(row_data))

        scraped_data.append(row_data)

    df = pd.DataFrame(scraped_data, columns=column_names)
    df.to_csv("ui_scraped_data.csv", index=False)

    print("✅ Data saved to ui_scraped_data.csv")
    print(df.head())
    input("🛑 Press ENTER to exit after inspecting the browser...")


# --- Run the full process ---
if __name__ == "__main__":
    playwright = sync_playwright().start()
    page, context, browser = filter_by_breed(playwright, "Boxer")
    data_capture(page)