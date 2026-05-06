from pathlib import Path

from playwright.sync_api import sync_playwright


BASE_URL = "http://127.0.0.1:8090"
OUT_DIR = Path("docs/screenshots")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(
            viewport={"width": 1600, "height": 1000},
            locale="ru-RU",
        )
        page = context.new_page()

        page.goto(f"{BASE_URL}/", wait_until="networkidle")
        page.screenshot(path=str(OUT_DIR / "web-login-real.png"), full_page=True)

        # Emulate authenticated UI by setting operator cookie.
        context.add_cookies(
            [
                {
                    "name": "operator_name",
                    "value": "demo",
                    "url": BASE_URL,
                }
            ]
        )

        page.goto(f"{BASE_URL}/", wait_until="networkidle")
        page.screenshot(path=str(OUT_DIR / "web-dashboard-real.png"), full_page=True)

        page.locator("button[hx-get='/ui/verify']").first.click()
        page.wait_for_timeout(800)
        page.screenshot(path=str(OUT_DIR / "web-verify-real.png"), full_page=True)

        browser.close()


if __name__ == "__main__":
    main()
