from flask import Flask, render_template, request, jsonify
import os
import time
import requests
import pandas as pd
from base64 import b64encode

app = Flask(__name__)

# ===============================
# CONFIG
# ===============================
CLIENT_ID = os.getenv("OPMS_CLIENT_ID", "").strip()
CLIENT_SECRET = os.getenv("OPMS_CLIENT_SECRET", "").strip()

TOKEN_URL = "https://auth.opms.com.au/api/authenticate/token"
API_BASE = "https://api.opms.com.au"
TARGET_SITE_ID = 17
PAGE_SIZE = 100

ALLOWED_SHIFTS = ["DS", "NS", "ANY"]
SLEEP_SECONDS = 0.2
MAX_RETRIES = 3


# ===============================
# GET ACCESS TOKEN
# ===============================
def get_access_token():
    if not CLIENT_SECRET:
        raise ValueError("OPMS_CLIENT_SECRET is empty. Please set it first.")

    auth_str = f"{CLIENT_ID}:{CLIENT_SECRET}"
    b64_auth = b64encode(auth_str.encode()).decode()

    headers = {
        "Authorization": f"Basic {b64_auth}",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    res = requests.post(
        TOKEN_URL,
        headers=headers,
        data={"grant_type": "client_credentials"},
        timeout=60
    )
    res.raise_for_status()
    return res.json()["access_token"]


# ===============================
# GET ALL EMPLOYEES FROM SITE
# ===============================
def get_all_shutdown_employees(token, site_id=17, page_size=100):
    url = f"{API_BASE}/sites/employees"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }

    all_rows = []
    after = None
    page_num = 1

    while True:
        params = {
            "site_ids": str(site_id),
            "page_size": page_size
        }

        if after:
            params["after"] = after

        print(f"\nFetching page {page_num} ...")
        print("Params:", params)

        res = requests.get(url, headers=headers, params=params, timeout=60)
        print("Status:", res.status_code)
        print("Response preview:", res.text[:1000])
        res.raise_for_status()

        data = res.json()
        rows = data.get("data", [])

        if not rows:
            break

        all_rows.extend(rows)

        next_cursor = data.get("next_cursor")
        print("Rows this page:", len(rows))
        print("Next cursor:", next_cursor)

        if not next_cursor:
            break

        after = next_cursor
        page_num += 1
        time.sleep(0.2)

    return all_rows


# ===============================
# BUILD DATAFRAME
# ===============================
def build_employee_df(rows):
    result = []

    for row in rows:
        emp = row.get("employee", {}) or {}
        pos = row.get("position", {}) or {}
        team = row.get("team", {}) or {}

        team_name = str(team.get("name", "") or "").strip().upper()

        # 去掉 ASSETS
        if team_name == "ASSETS":
            continue

        first_name = emp.get("first_name", "") or ""
        middle_name = emp.get("middle_name", "") or ""
        last_name = emp.get("last_name", "") or ""

        full_name = " ".join(
            [x for x in [first_name, middle_name, last_name] if x]
        ).strip()

        result.append({
            "employee_id": emp.get("id"),
            "full_name": full_name,
            "position_name": pos.get("name")
        })

    df = pd.DataFrame(result)

    if not df.empty:
        df = df.drop_duplicates(subset=["employee_id"]).reset_index(drop=True)
        df = df.sort_values(by=["full_name"], ascending=True).reset_index(drop=True)

    return df

# ===============================
# GET DATA FOR PAGE
# ===============================
def get_employee_data():
    token = get_access_token()
    rows = get_all_shutdown_employees(token, site_id=TARGET_SITE_ID, page_size=PAGE_SIZE)
    df = build_employee_df(rows)
    return df


# ===============================
# PATCH ONE EMPLOYEE BACK TO OPMS
# ===============================
def patch_employee(token, employee_id, shift_value):
    url = f"{API_BASE}/employee/{int(employee_id)}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    payload = {
        "additionalID8": shift_value
    }

    last_error = ""

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            res = requests.patch(url, headers=headers, json=payload, timeout=60)

            if res.status_code in [200, 204]:
                return True, ""

            last_error = f"HTTP {res.status_code}: {res.text}"
            time.sleep(1)

        except Exception as e:
            last_error = str(e)
            time.sleep(1)

    return False, last_error


# ===============================
# HOME PAGE
# ===============================
@app.route("/", methods=["GET"])
def index():
    try:
        df = get_employee_data()
        employees = df.to_dict(orient="records")

        return render_template(
            "shift_form.html",
            employees=employees,
            error=None
        )
    except Exception as e:
        return render_template(
            "shift_form.html",
            employees=[],
            error=str(e)
        )

# ===============================
# SUBMIT AND WRITE BACK TO OPMS
# ===============================
@app.route("/submit", methods=["POST"])
def submit():
    try:
        data = request.get_json()

        if not data or "rows" not in data:
            return jsonify({
                "success": False,
                "message": "No data received."
            }), 400

        rows = data["rows"]
        if not rows:
            return jsonify({
                "success": False,
                "message": "No rows selected."
            }), 400

        token = get_access_token()

        success_count = 0
        failed_count = 0
        failed_rows = []

        for item in rows:
            employee_id = str(item.get("employee_id", "")).strip()
            full_name = str(item.get("full_name", "")).strip()
            position_name = str(item.get("position_name", "")).strip()
            shift = str(item.get("shift", "")).strip().upper()

            if not employee_id:
                failed_count += 1
                failed_rows.append({
                    "employee_id": employee_id,
                    "full_name": full_name,
                    "position_name": position_name,
                    "shift": shift,
                    "error": "employee_id is required"
                })
                continue

            if shift not in ALLOWED_SHIFTS:
                failed_count += 1
                failed_rows.append({
                    "employee_id": employee_id,
                    "full_name": full_name,
                    "position_name": position_name,
                    "shift": shift,
                    "error": "Shift must be DS, NS, or Any"
                })
                continue

            ok, err = patch_employee(token, employee_id, shift)

            if ok:
                success_count += 1
            else:
                failed_count += 1
                failed_rows.append({
                    "employee_id": employee_id,
                    "full_name": full_name,
                    "position_name": position_name,
                    "shift": shift,
                    "error": err
                })

            time.sleep(SLEEP_SECONDS)

        return jsonify({
            "success": True,
            "message": "Submitted successfully.",
            "success_count": success_count,
            "failed_count": failed_count,
            "failed_rows": failed_rows
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


if __name__ == "__main__":
    app.run(debug=True)