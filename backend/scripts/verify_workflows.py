"""Verify staff workflows and sign-out on production using isolated release accounts."""
import argparse
import json
from pathlib import Path
import pyotp

from verify_browser import browser, check_page, click, select_option, wait_path
from verify_centres import choose_policy, evaluate, layout_check, ui_login
from verify_live import login, request, save_state


def link(name):
    references = json.loads(browser(["snapshot", "-i", "--json"]))["data"]["refs"]
    reference = next(key for key, item in references.items() if item["role"] == "link" and item["name"] == name)
    browser(["click", "@" + reference])


def tab(name):
    references = json.loads(browser(["snapshot", "-i", "--json"]))["data"]["refs"]
    reference = next(key for key, item in references.items() if item["role"] == "tab" and item["name"].startswith(name))
    browser(["click", "@" + reference])


def screenshot(root, name):
    layout_check()
    browser(["screenshot", str(root / (name + ".png"))])


def sign_out(api, role, root):
    access = evaluate("localStorage.getItem('risksure_access_token')")
    refresh = evaluate("localStorage.getItem('risksure_refresh_token')")
    click("Sign out")
    wait_path("/signed-out")
    browser(["wait", "--text", "Thank you"])
    browser(["wait", "a[href='/login']"])
    assert evaluate("localStorage.getItem('risksure_access_token') === null && localStorage.getItem('risksure_refresh_token') === null && localStorage.getItem('risksure_user') === null")
    request(api, "GET", "/auth/me", expected=401, token=access)
    request(api, "POST", "/auth/refresh", expected=401, token=refresh)
    screenshot(root, f"workflow-{role}-thank-you")
    browser(["wait", "1000"])
    wait_path("/signed-out")
    link("Sign in again")
    wait_path("/login")
    assert evaluate("document.querySelectorAll('input[name=role]').length") == 3
    print(f"{role}: Thank you, cleared local session, revoked access/refresh tokens, and return to login passed.", flush=True)


def verify_sign_outs(args):
    state = json.loads(args.state.read_text())
    base = args.base_url.rstrip("/")
    root = Path(__file__).resolve().parents[2] / "artifacts"
    browser(["open", base + "/login"], capture_output=False)
    browser(["eval", "localStorage.clear(); sessionStorage.clear(); true"])
    browser(["open", base + "/login"])
    browser(["set", "viewport", "1440", "1000"])
    for role in ("customer", "underwriter", "admin"):
        account = state["accounts"][role]
        browser(["click", f'label:has(input[name="role"][value="{role}"])'])
        browser(["fill", "#login-email", account["email"]])
        browser(["fill", "#login-password", account["password"]])
        click("Sign in")
        browser(["wait", 'input[aria-label="Authenticator code"]'])
        browser(["fill", 'input[aria-label="Authenticator code"]', pyotp.TOTP(account["totp_secret"]).now()])
        click("Verify code")
        wait_path("/" + role)
        browser(["wait", "--load", "networkidle"])
        check_page()
        if role == "customer":
            link("New Application")
            wait_path("/new-application")
            browser(["fill", "#name", "Discarded private sign-out draft"])
            browser(["fill", "#age", "36"])
            select_option("Select sex", "Female")
            click("Proceed to Risk Assessment")
            wait_path("/risk")
            assert evaluate("JSON.parse(sessionStorage.getItem('risksure_application_draft')).name") == "Discarded private sign-out draft"
        if role == "underwriter":
            link("Final Review")
            wait_path("/final")
            assert not evaluate("document.querySelector('main').textContent.includes('Discarded private sign-out draft')")
            screenshot(root, "workflow-draft-cleared-across-sessions")
            print("In-memory application draft was cleared across SPA sign-out and the next role login.", flush=True)
        if role == "admin":
            browser(["set", "viewport", "390", "844"])
        sign_out(base + "/api", role, root)
    state.setdefault("verification", {})["sign_out_draft_reset"] = True
    save_state(args.state, state)


def verify(args):
    state = json.loads(args.state.read_text())
    base = args.base_url.rstrip("/")
    api = base + "/api"
    root = Path(__file__).resolve().parents[2] / "artifacts"
    accounts = state["accounts"]
    for role in ("customer", "underwriter", "admin"):
        login(api, accounts[role], role)
        save_state(args.state, state)
    customer, underwriter, admin = (accounts[role] for role in ("customer", "underwriter", "admin"))
    if not state.get("workflow_application_id"):
        result = request(api, "POST", "/save", token=customer["token"], json={
            "name": "RiskSure Workflow Release Verification", "age": 36, "sex": "female",
            "bmi": 23.5, "children": 1, "smoker": "no", "region": "southeast",
        })
        state["workflow_application_id"] = result["application"]["id"]
        save_state(args.state, state)
    case_id = state["workflow_application_id"]
    browser(["open", base + "/login"], capture_output=False)
    browser(["set", "viewport", "1440", "1000"])
    ui_login(base, underwriter, "underwriter")
    browser(["wait", "--text", "Application queue"])
    tab("Unassigned")
    browser(["fill", 'input[aria-label="Search applications"]', str(case_id)])
    case = request(api, "GET", f"/applications/{case_id}", token=underwriter["token"])
    browser(["open", base + f"/underwriter?case={case_id}"])
    if case["review_status"] != "completed":
        browser(["wait", "#underwriting-decision"])
        if case["assigned_underwriter_id"] is None:
            assert evaluate("document.querySelector('#underwriting-decision').disabled")
            click("Assign to me")
            browser(["wait", "--text", "Application assigned to you."])
        browser(["wait", "--fn", "!document.querySelector('#underwriting-decision').disabled"])
        tab("My cases")
        browser(["fill", 'input[aria-label="Search applications"]', case["name"]])
        browser(["wait", "--text", f"Case #{case_id}"])
        browser(["open", base + f"/underwriter?case={case_id}"])
        browser(["wait", "#underwriting-decision"])
        browser(["select", "#underwriting-decision", "Rejected"])
        browser(["fill", "#underwriting-reason", "Isolated release fixture: verify confirmed human review, not a customer decision."])
        click("Review decision")
        browser(["wait", "--text", "Confirm underwriting decision"])
        screenshot(root, "workflow-decision-confirmation")
        click("Back to review")
        assert request(api, "GET", f"/applications/{case_id}", token=underwriter["token"])["review_status"] != "completed"
        click("Review decision")
        click("Record decision")
        browser(["wait", "--text", f"Decision recorded for case #{case_id}:"])
    browser(["wait", "--text", "Completed decision"])
    assert not evaluate("Boolean(document.querySelector('#underwriting-decision'))")
    request(api, "PUT", f"/underwriting/applications/{case_id}/assign", expected=409, token=underwriter["token"], json={})
    screenshot(root, "workflow-underwriter-completed")
    link("Application details")
    wait_path(f"/underwriter/applications/{case_id}")
    browser(["wait", "--text", "Applicant information"])
    browser(["click", 'nav[aria-label="Case navigation"] a[href^="/underwriter?"]'])
    wait_path("/underwriter")
    browser(["wait", "--text", "Completed decision"])
    assert evaluate("new URLSearchParams(location.search).get('case')") == str(case_id)
    browser(["open", base + f"/relationship-graph?application_id={state['application_id']}"])
    browser(["wait", "svg[role=img]"])
    assert evaluate("document.querySelector('main').textContent.includes('Source: neo4j')")
    browser(["open", base + f"/underwriter?case={case_id}"])
    browser(["wait", "--text", "Completed decision"])
    browser(["set", "viewport", "320", "740"])
    screenshot(root, "workflow-underwriter-mobile")
    sign_out(api, "underwriter", root)

    browser(["set", "viewport", "1440", "1000"])
    ui_login(base, admin, "admin")
    browser(["wait", "--text", "Risk distribution"])
    screenshot(root, "workflow-admin-overview")
    tab("Workload")
    browser(["wait", "--text", "Underwriting workload"])
    overview = request(api, "GET", "/admin/overview", token=admin["token"])
    active_cases = request(api, "GET", "/underwriting/queue", token=admin["token"])
    for item in overview["underwriting_workload"]:
        assert item["assigned_applications"] == sum(row["assigned_underwriter_id"] == item["user_id"] and row["review_status"] != "completed" for row in active_cases)
    tab("Users")
    browser(["fill", 'input[aria-label="Search users"]', admin["email"]])
    assert evaluate("document.querySelector('main select').disabled")
    browser(["fill", 'input[aria-label="Search users"]', accounts["other_underwriter"]["email"]])
    browser(["select", "main select", "customer"])
    browser(["wait", "--text", "Confirm account role change"])
    screenshot(root, "workflow-role-confirmation")
    click("Cancel")
    assert evaluate("document.querySelector('main select').value") == "underwriter"
    users = request(api, "GET", "/admin/users", token=admin["token"])
    assert next(row for row in users if row["email"] == accounts["other_underwriter"]["email"])["role"] == "underwriter"
    browser(["set", "viewport", "320", "740"])
    screenshot(root, "workflow-admin-users-mobile")
    tab("Audit")
    browser(["fill", 'input[aria-label="Filter audit by action"]', "underwriting_decision"])
    click("Apply filters")
    browser(["wait", "--fn", "!Array.from(document.querySelectorAll('button')).find(b=>b.textContent.trim()==='Apply filters').disabled"])
    audit = request(api, "GET", "/admin/audit-logs?action=underwriting_decision", token=admin["token"])
    assert any(row["entity_id"] == case_id for row in audit)
    screenshot(root, "workflow-admin-audit-mobile")
    browser(["open", base + f"/relationship-graph?application_id={case_id}"])
    browser(["wait", "svg[role=img]"])
    check_page()
    graph = request(api, "GET", f"/graph?application_id={case_id}", token=admin["token"])
    assert graph["source"] == "neo4j"
    assert any(node["id"] == f"application-{case_id}" for node in graph["nodes"])
    browser(["open", base + "/admin/graph"])
    browser(["wait", "svg[role=img]"])
    check_page()
    browser(["open", base + "/premium"])
    browser(["wait", "#billing-policy"])
    screenshot(root, "workflow-admin-billing-mobile")
    sign_out(api, "admin", root)

    browser(["set", "viewport", "390", "844"])
    ui_login(base, customer, "customer")
    browser(["wait", "--text", "My applications"])
    screenshot(root, "workflow-customer-mobile")
    browser(["open", base + "/policy"])
    policies = request(api, "GET", "/policies", token=customer["token"])
    choose_policy(next(row for row in policies if row["application_id"] == state["application_id"]))
    assert not evaluate("Boolean(document.querySelector('#policy-document'))")
    screenshot(root, "workflow-customer-policy-mobile")
    sign_out(api, "customer", root)
    browser(["open", base + "/underwriter"])
    browser(["wait", "--fn", "location.pathname === '/login'"])
    assert not evaluate("Boolean(document.querySelector('#underwriting-decision'))")
    state.setdefault("verification", {})["staff_workflows_and_sign_out"] = True
    save_state(args.state, state)
    print("Production staff workflows, desktop/mobile layout, policy/billing smoke checks, and all three sign-outs passed.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--sign-outs-only", action="store_true")
    args = parser.parse_args()
    if args.sign_outs_only:
        verify_sign_outs(args)
    else:
        verify(args)
