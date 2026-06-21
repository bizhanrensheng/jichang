import argparse
import json
import os
import re
import time
from dataclasses import dataclass

import ddddocr
import requests
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright


BASE_URL = "https://999.999865.xyz"
LOGIN_URL = f"{BASE_URL}/login"
TIMEOUT = 15000
PUSHPLUS_TOKEN = os.getenv("PUSHPLUS_TOKEN", "").strip()

# Add more accounts here:
# {"username": "your_username", "password": "your_password"}
ACCOUNTS = [
    
]


@dataclass
class Account:
    username: str
    password: str


def load_accounts() -> list[Account]:
    raw = os.getenv("CHECKIN_ACCOUNTS", "").strip()
    if not raw:
        source = ACCOUNTS
    else:
        try:
            source = json.loads(raw)
        except json.JSONDecodeError:
            source = []
            for item in raw.split(","):
                if ":" not in item:
                    continue
                username, password = item.split(":", 1)
                source.append({"username": username.strip(), "password": password.strip()})

    accounts: list[Account] = []
    for item in source:
        username = str(item.get("username", "")).strip()
        password = str(item.get("password", "")).strip()
        if username and password:
            accounts.append(Account(username=username, password=password))
    return accounts


def clean_text(text: str | None) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", text or "")


def send_pushplus(title: str, content: str) -> None:
    if not PUSHPLUS_TOKEN:
        return

    try:
        pushplus_url = "http://www.pushplus.plus/send"
        pushplus_data = {
            "token": PUSHPLUS_TOKEN,
            "title": title,
            "content": content.replace("\n", "<br>"),
            "template": "html",
        }
        response = requests.post(pushplus_url, json=pushplus_data, timeout=10)
        print(f"PushPlus response status: {response.status_code}")
        print(f"PushPlus response body: {response.text}")
        response.raise_for_status()
        print("PushPlus notification sent")
    except Exception as exc:
        print(f"PushPlus notification failed: {exc}")


def wait_page_ready(page: Page) -> None:
    """等待页面加载完成
    
    先等待 DOM 内容加载完成，再等待网络空闲，超时不影响继续执行
    
    Args:
        page: Playwright Page 对象，代表浏览器页面
    """
    # 等待 DOM 内容加载完成（HTML 解析完毕）
    try:
        page.wait_for_load_state("domcontentloaded", timeout=TIMEOUT)
    except PlaywrightTimeoutError:
        # 超时不中断流程，继续尝试等待网络空闲
        pass
    # 等待网络空闲（500ms 内没有网络请求）
    try:
        page.wait_for_load_state("networkidle", timeout=5000)
    except PlaywrightTimeoutError:
        # 网络空闲超时不影响后续操作，直接忽略
        pass


def click_first_visible(page: Page, selectors: list[str], timeout: int = 2500) -> bool:
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            locator.wait_for(state="visible", timeout=timeout)
            locator.click(timeout=timeout)
            return True
        except PlaywrightTimeoutError:
            continue
        except Exception:
            continue
    return False


def close_popups(page: Page) -> None:
    # The site uses checkbox-driven modals. Some confirm buttons do not close them
    # reliably, so clear checked modal toggles after trying normal buttons.
    click_first_visible(
        page,
        [
            "button:has-text('我知道了')",
            "button:has-text('我已知晓')",
            "button:has-text('关闭')",
            "button:has-text('取消')",
        ],
        timeout=1200,
    )
    page.evaluate(
        """
        () => {
            for (const el of document.querySelectorAll('input.modal-toggle:checked,input[type=checkbox]:checked')) {
                const label = el.getAttribute('aria-label') || '';
                if (label.includes('每日签到')) continue;
                el.checked = false;
                el.dispatchEvent(new Event('change', { bubbles: true }));
                el.dispatchEvent(new Event('input', { bubbles: true }));
            }
            document.documentElement.style.overflow = '';
            document.body.style.overflow = '';
        }
        """
    )
    page.wait_for_timeout(300)


def login(page: Page, account: Account) -> None:
    print(f"[{account.username}] opening login page")
    page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=TIMEOUT)
    wait_page_ready(page)

    page.locator("input[name='username'], #username").first.fill(account.username, timeout=TIMEOUT)
    page.locator("input[name='password'], #password").first.fill(account.password, timeout=TIMEOUT)
    page.locator("button[type='submit'], button:has-text('登录')").first.click(timeout=TIMEOUT)

    try:
        page.wait_for_url("**/dashboard**", timeout=TIMEOUT)
    except PlaywrightTimeoutError as exc:
        body = page.locator("body").inner_text(timeout=5000)
        short_body = " ".join(body.split())[:300]
        raise RuntimeError(f"login did not reach dashboard. current url={page.url}, page text={short_body}") from exc

    wait_page_ready(page)
    print(f"[{account.username}] login success, dashboard loaded")


def enter_pro_mode_if_needed(page: Page, account: Account) -> None:
    close_popups(page)

    if page.get_by_text("每日签到", exact=True).count() > 0:
        return

    clicked = click_first_visible(
        page,
        [
            "text=进入专业模式",
            "div.cursor-pointer:has-text('专业人士')",
            "div:has-text('进入专业模式')",
        ],
        timeout=3000,
    )
    if clicked:
        print(f"[{account.username}] clicked pro mode")
        wait_page_ready(page)
        page.wait_for_timeout(800)
        close_popups(page)


def open_sign_modal(page: Page, account: Account) -> None:
    close_popups(page)

    # Prefer the real modal checkbox when available. It opens the same UI as the
    # visible "daily check-in" card but avoids clicking a nested label by mistake.
    opened = page.evaluate(
        """
        () => {
            const box = document.querySelector('#sign, input[id="sign"]');
            if (box) {
                box.checked = true;
                box.dispatchEvent(new Event('change', { bubbles: true }));
                box.dispatchEvent(new Event('input', { bubbles: true }));
                return true;
            }
            return false;
        }
        """
    )

    if not opened:
        opened = click_first_visible(
            page,
            [
                "text=每日签到",
                "label:has-text('每日签到')",
                "button:has-text('每日签到')",
            ],
            timeout=4000,
        )

    if not opened:
        raise RuntimeError("cannot find daily check-in entry")

    page.get_by_role("heading", name="签到").wait_for(state="visible", timeout=TIMEOUT)
    print(f"[{account.username}] sign modal opened")


def close_sign_modal(page: Page) -> None:
    page.evaluate(
        """
        () => {
            const box = document.querySelector('#sign, input[id="sign"]');
            if (box) {
                box.checked = false;
                box.dispatchEvent(new Event('change', { bubbles: true }));
                box.dispatchEvent(new Event('input', { bubbles: true }));
            }
            document.documentElement.style.overflow = '';
            document.body.style.overflow = '';
        }
        """
    )
    page.wait_for_timeout(500)


def reopen_sign_modal(page: Page, account: Account) -> None:
    close_sign_modal(page)
    open_sign_modal(page, account)


def read_captcha(page: Page, ocr: ddddocr.DdddOcr) -> str:
    image = page.locator("img[alt='captcha']").first
    image.wait_for(state="visible", timeout=TIMEOUT)
    image_bytes = image.screenshot(type="png")
    return clean_text(ocr.classification(image_bytes))


def submit_sign(page: Page, account: Account, ocr: ddddocr.DdddOcr, retries: int) -> bool:
    for attempt in range(1, retries + 1):
        captcha = read_captcha(page, ocr)
        print(f"[{account.username}] captcha attempt {attempt}/{retries}: {captcha!r}")

        if not captcha:
            print(f"[{account.username}] captcha empty, reopen sign modal and retry")
            reopen_sign_modal(page, account)
            continue

        page.get_by_placeholder("请输入验证码").fill(captcha, timeout=TIMEOUT)
        page.get_by_role("button", name="签到").last.click(timeout=TIMEOUT)
        page.wait_for_timeout(1500)

        body = page.locator("body").inner_text(timeout=TIMEOUT)
        if "今日已签到" in body or "Already checked" in body:
            print(f"[{account.username}] already checked in today")
            return True
        if "签到成功" in body or "Check-in successful" in body:
            print(f"[{account.username}] check-in success")
            return True
        if "验证码" in body or "captcha" in body.lower():
            print(f"[{account.username}] captcha failed, reopen daily check-in and retry")
            reopen_sign_modal(page, account)
            continue

        print(f"[{account.username}] submit result not recognized, page text checked")
        return False

    print(f"[{account.username}] check-in failed after retries")
    return False


def logout_or_reset(page: Page) -> None:
    try:
        page.goto(f"{BASE_URL}/", wait_until="domcontentloaded", timeout=TIMEOUT)
        wait_page_ready(page)
        click_first_visible(page, ["text=注销", "a:has-text('注销')"], timeout=2500)
    except Exception:
        pass


def run_account(browser, account: Account, ocr: ddddocr.DdddOcr, retries: int, slow: int) -> bool:
    context = browser.new_context(viewport={"width": 1366, "height": 900}, locale="zh-CN")
    page = context.new_page()
    page.set_default_timeout(TIMEOUT)

    try:
        login(page, account)
        enter_pro_mode_if_needed(page, account)
        open_sign_modal(page, account)
        return submit_sign(page, account, ocr, retries)
    finally:
        if slow:
            page.wait_for_timeout(slow)
        context.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Browser-based check-in script")
    parser.add_argument("--retries", type=int, default=8, help="captcha retry count per account")
    parser.add_argument("--interval", type=float, default=1.5, help="seconds between accounts")
    parser.add_argument("--headless", action="store_true", help="run without visible browser")
    parser.add_argument("--slow", type=int, default=800, help="ms to keep page visible before closing")
    args = parser.parse_args()

    accounts = load_accounts()
    if not accounts:
        print("No accounts configured. Edit ACCOUNTS or set CHECKIN_ACCOUNTS.")
        return 2

    ocr = ddddocr.DdddOcr(show_ad=False)
    ok_count = 0
    results: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless, slow_mo=150)
        try:
            for index, account in enumerate(accounts, start=1):
                try:
                    if run_account(browser, account, ocr, max(1, args.retries), args.slow):
                        ok_count += 1
                        results.append(f"[OK] {account.username}: checked in or already checked in")
                    else:
                        results.append(f"[FAIL] {account.username}: check-in failed")
                except Exception as exc:
                    print(f"[{account.username}] error: {exc}")
                    results.append(f"[ERROR] {account.username}: {exc}")

                if index < len(accounts):
                    time.sleep(max(0, args.interval))
        finally:
            browser.close()

    summary = f"done: {ok_count}/{len(accounts)} account(s) checked in or already checked in"
    print(summary)
    send_pushplus("机场签到结果", "\n".join([summary, *results]))
    return 0 if ok_count == len(accounts) else 1


if __name__ == "__main__":
    raise SystemExit(main())
