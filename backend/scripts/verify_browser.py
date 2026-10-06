"""Verify live UI authentication without exposing credentials or token responses."""
import argparse
import json
from pathlib import Path
import secrets
import shutil
import subprocess
import time

import pyotp
import requests


def browser(arguments, capture_output=True):
    executable = shutil.which("npx.cmd") or shutil.which("npx")
    output = {"capture_output": True} if capture_output else {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    try:
        result = subprocess.run([executable, "--yes", "agent-browser", *arguments],
                                text=True, timeout=90, **output)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Browser action timed out: {arguments[0]}") from None
    if result.returncode:
        raise RuntimeError(f"Browser action failed: {arguments[0]}")
    return result.stdout.strip() if capture_output else ""


def click(name):
    browser(["eval", "Array.from(document.querySelectorAll('button')).find(b => b.textContent.trim() === "
             + json.dumps(name) + ")?.scrollIntoView({block:'center'}); true"])
    browser(["find", "role", "button", "click", "--name", name, "--exact"])


def fill_multiline(selector, value):
    # Windows command shims truncate literal newlines; enter them as keystrokes.
    lines = value.split("\n")
    browser(["fill", selector, lines[0]])
    for line in lines[1:]:
        browser(["press", "Control+End"])
        browser(["press", "Enter"])
        if line:
            browser(["type", selector, line])


def wait_path(path):
    browser(["wait", "--fn", "window.location.pathname === " + json.dumps(path)])


def check_page():
    if json.loads(browser(["eval", "Boolean(document.querySelector('[role=alert]'))"])):
        raise RuntimeError("The live page displayed an error alert")
    if browser(["errors"]):
        raise RuntimeError("Browser reported an uncaught error")


def wait_ai_summary():
    deadline = time.monotonic() + 100
    while time.monotonic() < deadline:
        result = json.loads(browser(["eval", "({ready:Array.from(document.querySelectorAll('h3'))"
                                     ".some(heading => heading.textContent.trim() === 'AI interpretation'), "
                                     "error:Boolean(document.querySelector('[role=alert]'))})"]))
        if result["error"]:
            raise RuntimeError("The live AI summary displayed an error alert")
        if result["ready"]:
            return
        time.sleep(1)
    raise RuntimeError("The live AI summary exceeded its bounded deadline")


def select_option(placeholder, value):
    browser(["eval", "(() => { const trigger = Array.from(document.querySelectorAll('[role=combobox]'))"
             ".find(b => b.textContent.trim() === " + json.dumps(placeholder) + "); "
             "trigger.setAttribute('data-release-select', 'true'); trigger.scrollIntoView({block:'center'}); return true; })()"])
    browser(["click", '[data-release-select="true"]'])
    references = json.loads(browser(["snapshot", "-i", "--json"]))["data"]["refs"]
    option = next(key for key, item in references.items() if item["role"] == "option" and item["name"] == value)
    browser(["click", "@" + option])
    browser(["wait", "--fn", "document.querySelector('[data-release-select]').textContent.trim() === " + json.dumps(value)])
    browser(["eval", "document.querySelector('[data-release-select]').removeAttribute('data-release-select'); true"])


def customer_flow(args, state):
    existing_ids = json.loads(browser(["eval", "(async () => { const response = await fetch('/api/applications', "
        "{headers:{Authorization:'Bearer '+localStorage.getItem('risksure_access_token')}}); "
        "if (!response.ok) throw new Error('Application verification failed'); "
        "return (await response.json()).map(row => row.id); })()"] ))
    click("Start an application")
    wait_path("/new-application")
    name = "RiskSure Browser Verification " + secrets.token_hex(3)
    browser(["fill", "#name", name])
    browser(["fill", "#age", "36"])
    select_option("Select sex", "Female")
    click("Proceed to Risk Assessment")
    wait_path("/risk")
    print("Customer applicant intake: passed.", flush=True)
    browser(["fill", "#bmi", "23.5"])
    browser(["fill", "#children", "1"])
    select_option("Select smoker status", "No")
    select_option("Select region", "Southeast")
    click("Calculate Risk")
    browser(["wait", "--text", "Review Application"])
    click("Review Application")
    wait_path("/final")
    print("Customer real risk assessment and final review: passed.", flush=True)
    click("Submit Application")
    wait_path("/customer")
    browser(["wait", "--text", "My applications"])
    application = json.loads(browser(["eval", "(async () => { const response = await fetch('/api/applications', "
        "{headers:{Authorization:'Bearer '+localStorage.getItem('risksure_access_token')}}); "
        "if (!response.ok) throw new Error('Application verification failed'); "
        "const rows = await response.json(); const row = rows.find(row => !" + json.dumps(existing_ids) + ".includes(row.id)); "
        "return row ? {id:row.id,status:row.review_status} : null; })()"] ))
    if not application or not isinstance(application["id"], int):
        raise RuntimeError("The browser-submitted application was not persisted")
    if application["status"] != "pending":
        raise RuntimeError("A submitted application bypassed human review")
    application_id = application["id"]
    browser(["wait", "--text", f"Application #{application_id}"])
    state["browser_application_id"] = application_id
    args.state.write_text(json.dumps(state, indent=2))
    check_page()
    print(f"Customer UI risk calculation, submission and persisted application #{application_id}: passed.", flush=True)


def human_decision(args, state):
    application_id = state["browser_application_id"]
    browser(["open", args.base_url + "/underwriter"])
    browser(["wait", "--text", f"Case #{application_id}"])
    selector = "Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes(" + json.dumps(f"Case #{application_id} ") + "))"
    browser(["eval", "(() => { const button = " + selector + "; button.id = 'release-verification-case'; "
             "button.scrollIntoView({block:'center'}); return true; })()"])
    browser(["click", "#release-verification-case"])
    click("Assign to me")
    browser(["wait", "--text", "Application assigned to you."])
    browser(["select", "#underwriting-decision", "Approved"])
    browser(["fill", "#underwriting-reason", "Isolated browser release verification of human review."])
    click("Review decision")
    browser(["wait", "--text", "Confirm underwriting decision"])
    click("Record decision")
    browser(["wait", "--text", f"Decision recorded for case #{application_id}:"])
    check_page()
    print(f"Underwriter UI assignment and human decision for application #{application_id}: passed.", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--role", required=True, choices=["customer", "underwriter", "admin"])
    parser.add_argument("--first-setup", action="store_true")
    parser.add_argument("--customer-flow", action="store_true")
    parser.add_argument("--human-decision", action="store_true")
    args = parser.parse_args()
    state = json.loads(args.state.read_text())
    account = state["accounts"][args.role]
    if args.customer_flow and not args.first_setup:
        account = state["accounts"].get("browser_customer", account)
    if args.first_setup:
        account = {"email": f"release-browser-{secrets.token_hex(5)}@example.invalid",
                   "password": secrets.token_urlsafe(24)}
        response = requests.post(args.base_url.rstrip("/") + "/api/auth/register", json={
            "email": account["email"], "password": account["password"],
            "full_name": "RiskSure Browser Release Verification"}, timeout=30)
        if response.status_code != 201:
            raise RuntimeError(f"Browser verification registration failed: {response.status_code}")
        state["accounts"]["browser_customer"] = account
        args.state.write_text(json.dumps(state, indent=2))
    # A new Windows daemon inherits output handles; do not give startup a pipe.
    browser(["open", args.base_url + "/login"], capture_output=False)
    browser(["eval", "localStorage.clear(); sessionStorage.clear(); true"])
    browser(["open", args.base_url + "/login"])
    browser(["click", 'label:has(input[name="role"][value="' + args.role + '"])'])
    browser(["fill", "input[type=email]", account["email"]])
    browser(["fill", "input[type=password]", account["password"]])
    click("Sign in")
    browser(["wait", 'input[aria-label="Authenticator code"]'])
    if args.first_setup:
        browser(["wait", "code"])
        account["totp_secret"] = json.loads(browser(["eval", "document.querySelector('code').textContent"]))
        args.state.write_text(json.dumps(state, indent=2))
    browser(["fill", 'input[aria-label="Authenticator code"]', pyotp.TOTP(account["totp_secret"]).now()])
    click("Verify code")
    if args.first_setup:
        browser(["wait", "--text", "Save your recovery codes"])
        click("Continue")
    wait_path("/" + args.role)
    browser(["wait", "--load", "networkidle"])
    browser(["wait", "--text", {"customer": "My applications", "admin": "Risk distribution",
                                  "underwriter": "Application queue"}[args.role]])
    check_page()
    root = Path(__file__).resolve().parents[2]
    screenshot = root / "artifacts" / f"production-{args.role}.png"
    browser(["screenshot", str(screenshot)])
    errors = browser(["errors"])
    print(f"{args.role}: browser login, authenticator verification and dashboard passed.", flush=True)
    print(f"{args.role}: uncaught browser errors: {'present' if errors else 'none'}", flush=True)
    if errors:
        raise RuntimeError("Browser reported an uncaught error")
    if args.customer_flow:
        customer_flow(args, state)
    if args.role == "underwriter" and state.get("application_id"):
        application_id = state["application_id"]
        for path, label, content in ((f"/applications/{application_id}", "application", "Applicant information"),
                            (f"/case-intelligence?id={application_id}", "case-intelligence", "Retrieved policy evidence"),
                            (f"/relationship-graph?application_id={application_id}", "relationship-graph", "Relationship Map")):
            browser(["open", args.base_url + path])
            browser(["wait", "--text", content])
            browser(["wait", "svg[role=img]"])
            check_page()
            if label == "case-intelligence":
                click("Generate evidence summary")
                wait_ai_summary()
                check_page()
            browser(["screenshot", str(root / "artifacts" / f"production-{label}.png")])
            print(f"Underwriter {label}: loaded evidence passed.", flush=True)
    if args.human_decision:
        human_decision(args, state)
    if args.role == "admin":
        browser(["open", args.base_url + "/admin/graph"])
        browser(["wait", "--text", "Graph investigation"])
        browser(["wait", "svg[role=img]"])
        check_page()
        browser(["screenshot", str(root / "artifacts" / "production-admin-graph.png")])
        print("Admin system graph: page rendered.", flush=True)


if __name__ == "__main__":
    main()
