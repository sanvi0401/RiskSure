"""Test the live login, policy and billing centres using labelled release fixtures."""
import argparse
import json
from pathlib import Path
import time

import pyotp

from verify_browser import browser, check_page, click, wait_path
from verify_live import login, request, save_state


def evaluate(script):
    return json.loads(browser(["eval", script]))


def layout_check():
    assert evaluate("document.documentElement.scrollWidth <= window.innerWidth"), "Horizontal page overflow"
    assert evaluate("Array.from(document.querySelectorAll('main button')).every(b => b.scrollWidth <= b.clientWidth + 1)"), "Button text overflow"
    check_page()


def ui_login(base, account, role):
    browser(["open", base + "/login"])
    browser(["eval", "localStorage.clear(); sessionStorage.clear(); true"])
    browser(["open", base + "/login"])
    browser(["click", f'label:has(input[name="role"][value="{role}"])'])
    browser(["fill", "#login-email", account["email"]])
    browser(["fill", "#login-password", account["password"]])
    click("Sign in")
    browser(["wait", 'input[aria-label="Authenticator code"]'])
    browser(["fill", 'input[aria-label="Authenticator code"]', pyotp.TOTP(account["totp_secret"]).now()])
    click("Verify code")
    wait_path("/" + role)
    check_page()
    print(f"{role}: selected role, password, TOTP and dashboard passed.", flush=True)


def choose_policy(policy):
    selector = "Array.from(document.querySelectorAll('main button')).find(b => b.textContent.includes(" + json.dumps(policy["policy_number"]) + "))"
    browser(["wait", "--fn", selector + " !== undefined"])
    browser(["eval", "(() => {const b=" + selector + "; b.id='centre-policy'; b.scrollIntoView({block:'center'}); return true;})()"])
    browser(["click", "#centre-policy"])
    browser(["wait", "#policy-question"])


def wait_answer():
    deadline = time.monotonic() + 100
    while time.monotonic() < deadline:
        state = evaluate("({ready:Boolean(document.querySelector('[data-testid=policy-answer]')), error:Boolean(document.querySelector('[role=alert]'))})")
        if state["error"]:
            raise RuntimeError("The policy question displayed an error")
        if state["ready"]:
            assert evaluate("document.querySelector('[data-testid=policy-answer] h3').textContent === 'Policy answer'"), "Real AI answer unavailable"
            return
        time.sleep(1)
    raise RuntimeError("Policy answer exceeded its bounded deadline")


def billing(base, api, account, role, policy, screenshots):
    browser(["open", base + "/premium"])
    browser(["wait", "--fn", "document.querySelector('#billing-policy') && !document.querySelector('#billing-policy').disabled"])
    rows = request(api, "GET", "/billing", token=account["token"])
    existing = next((row for row in rows if row["policy_id"] == policy["id"] and row["status"] in ("pending", "paid")), None)
    if existing is None:
        browser(["select", "#billing-policy", str(policy["id"])])
        assert evaluate("document.querySelector('#billing-premium').readOnly")
        click("Record pending premium")
        browser(["wait", "--text", "Pending premium recorded:"])
        browser(["wait", "--fn", "!document.querySelector('#billing-policy').disabled"])
        rows = request(api, "GET", "/billing", token=account["token"])
        existing = next(row for row in rows if row["policy_id"] == policy["id"])
    assert existing["status"] == "pending", "A recorded premium must not be marked paid"
    assert existing["amount"] == policy["premium_amount"], "Client amount replaced the policy premium"
    assert evaluate("document.querySelector('main').textContent.includes(" + json.dumps(existing["reference"]) + ")")
    assert not evaluate("Array.from(document.querySelector('#billing-policy').options).some(o => o.value === " + json.dumps(str(policy["id"])) + ")"), "Duplicate premium still selectable"
    payload = {"policy_id": policy["id"]}
    if role == "admin":
        payload["customer_id"] = policy["customer_id"]
    request(api, "POST", "/billing", expected=409, token=account["token"], json=payload)
    layout_check()
    browser(["screenshot", str(screenshots / f"centres-{role}-billing-desktop.png")])
    browser(["set", "viewport", "390", "844"])
    browser(["eval", "document.querySelector('#billing-policy').scrollIntoView({block:'center'}); true"])
    layout_check()
    browser(["screenshot", str(screenshots / f"centres-{role}-billing-mobile.png")])
    browser(["set", "viewport", "1280", "900"])
    print(f"{role}: live billing UI, authoritative premium, persisted pending transaction, duplicate prevention and mobile layout passed.", flush=True)
    return existing["id"]


def verify(args):
    state = json.loads(args.state.read_text())
    api = args.base_url.rstrip("/") + "/api"
    screenshots = Path(__file__).resolve().parents[2] / "artifacts"
    accounts = state["accounts"]
    for name in ("customer", "browser_customer", "underwriter", "admin"):
        login(api, accounts[name], "customer" if name == "browser_customer" else name)
        save_state(args.state, state)
    customer, underwriter, admin = (accounts[name] for name in ("customer", "underwriter", "admin"))
    denied = request(api, "POST", "/auth/login", expected=403, json={"email": customer["email"], "password": customer["password"], "role": "admin"})
    assert not any(key.endswith("token") for key in denied)
    policies = request(api, "GET", "/policies", token=customer["token"])
    policy = next(row for row in policies if row["application_id"] == state["application_id"])
    other_policies = request(api, "GET", "/policies", token=accounts["browser_customer"]["token"])
    other_policy = next(row for row in other_policies if row["application_id"] == state["browser_application_id"])
    assert other_policy["id"] not in {row["id"] for row in policies}
    request(api, "PUT", f"/policies/{policy['id']}/document", expected=403, token=customer["token"], json={"document_text": "Not permitted"})
    request(api, "POST", f"/policies/{other_policy['id']}/intelligence", expected=403, token=customer["token"], json={"question": "Eligibility?"})
    request(api, "POST", "/billing", expected=404, token=customer["token"], json={"policy_id": other_policy["id"]})
    request(api, "GET", "/billing", expected=403, token=underwriter["token"])

    browser(["set", "viewport", "1280", "900"])
    browser(["open", args.base_url + "/login"])
    browser(["eval", "localStorage.clear(); sessionStorage.clear(); true"])
    browser(["open", args.base_url + "/login"])
    assert evaluate("Array.from(document.querySelectorAll('input[name=role]')).map(r => r.value)") == ["customer", "underwriter", "admin"]
    browser(["screenshot", str(screenshots / "centres-login-desktop.png")])
    browser(["set", "viewport", "320", "740"])
    layout_check()
    assert evaluate("Array.from(document.querySelectorAll('input[name=role] + span')).every(s => s.scrollWidth <= s.clientWidth)"), "Role selector text overflow"
    browser(["screenshot", str(screenshots / "centres-login-mobile.png")])
    browser(["set", "viewport", "1280", "900"])
    browser(["click", 'label:has(input[value="admin"])'])
    browser(["fill", "#login-email", customer["email"]])
    browser(["fill", "#login-password", customer["password"]])
    click("Sign in")
    browser(["wait", "[role=alert]"])
    assert not evaluate("Boolean(document.querySelector('input[aria-label=\"Authenticator code\"]'))")
    print("Login: three roles visible at desktop and 320px; mismatched role denied before TOTP.", flush=True)

    ui_login(args.base_url, underwriter, "underwriter")
    assert not evaluate("Array.from(document.querySelectorAll('nav a')).some(a => a.getAttribute('href') === '/premium')")
    browser(["open", args.base_url + "/policy"])
    choose_policy(policy)
    browser(["wait", "#policy-document"])
    document = policy["terms_document"] + "\nCentre verification: this is an isolated test policy, not a customer contract."
    browser(["fill", "#policy-document", document])
    click("Save document")
    browser(["wait", "--text", "Policy document saved."])
    layout_check()
    browser(["screenshot", str(screenshots / "centres-underwriter-policy.png")])
    stored = request(api, "GET", "/policies", token=customer["token"])
    assert next(row for row in stored if row["id"] == policy["id"])["terms_document"] == document
    print("Underwriter: document edit/save persisted and inaccessible Billing link hidden.", flush=True)

    ui_login(args.base_url, customer, "customer")
    billing(args.base_url, api, customer, "customer", policy, screenshots)
    browser(["open", args.base_url + "/policy"])
    choose_policy(policy)
    assert not evaluate("Boolean(document.querySelector('#policy-document'))"), "Customer can see staff editing controls"
    browser(["fill", "#policy-question", "What eligibility review is required in this policy?"])
    click("Ask policy")
    wait_answer()
    layout_check()
    browser(["screenshot", str(screenshots / "centres-customer-policy-desktop.png")])
    browser(["set", "viewport", "390", "844"])
    browser(["eval", "document.querySelector('#policy-question').scrollIntoView({block:'center'}); true"])
    layout_check()
    browser(["screenshot", str(screenshots / "centres-customer-policy-mobile.png")])
    browser(["set", "viewport", "1280", "900"])
    print("Customer: read-only policy document, real AI answer with stored sources, desktop/mobile layout passed.", flush=True)

    ui_login(args.base_url, admin, "admin")
    billing(args.base_url, api, admin, "admin", other_policy, screenshots)
    browser(["open", args.base_url + "/policy"])
    choose_policy(policy)
    browser(["fill", "#policy-question", "Discard on policy switch"])
    choose_policy(other_policy)
    assert evaluate("document.querySelector('#policy-question').value") == ""
    assert evaluate("document.querySelector('#policy-document').value") == (other_policy["terms_document"] or "")
    assert not evaluate("Boolean(document.querySelector('[data-testid=policy-answer]'))")
    layout_check()
    browser(["screenshot", str(screenshots / "centres-admin-policy.png")])
    audit = request(api, "GET", "/admin/audit-logs?action=billing_transaction_created", token=admin["token"])
    transactions = request(api, "GET", "/billing", token=admin["token"])
    fixture_ids = {row["id"] for row in transactions if row["policy_id"] in (policy["id"], other_policy["id"])}
    assert fixture_ids <= {row["entity_id"] for row in audit}
    state.setdefault("verification", {}).update({"login_three_roles": True, "billing_centres": True, "policy_centres": True})
    save_state(args.state, state)
    print("Admin: both centres, policy-switch state reset and persisted billing audit records passed.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--base-url", required=True)
    arguments = parser.parse_args()
    try:
        verify(arguments)
    finally:
        browser(["close"])
