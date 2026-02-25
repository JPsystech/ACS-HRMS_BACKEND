import sys, os, json, urllib.request, urllib.error
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.db.session import SessionLocal
from app.models.employee import Employee
from app.core.security import create_access_token

BASE = "http://127.0.0.1:8001"

def get_token():
    db = SessionLocal()
    try:
        emp = db.query(Employee).filter(Employee.emp_code == "ADM-001").first()
        if not emp:
            print("Employee ADM-001 not found")
            return None
        return create_access_token({"sub": str(emp.id), "emp_code": emp.emp_code, "role": emp.role, "role_rank": 1})
    finally:
        db.close()

def call(path, token):
    url = f"{BASE}{path}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req) as resp:
            data = resp.read()
            content_type = resp.headers.get("Content-Type", "")
            print(path, resp.status, content_type)
            try:
                print(json.dumps(json.loads(data.decode()), indent=2)[:4000])
            except Exception:
                print(data[:4000])
    except urllib.error.HTTPError as e:
        print(path, "HTTPError", e.code)
        body = e.read()
        try:
            print(body.decode())
        except Exception:
            print(body)
    except Exception as e:
        print(path, "Error", repr(e))

if __name__ == "__main__":
    token = get_token()
    if not token:
        raise SystemExit(1)
    for p in ("/api/v1/employees", "/api/v1/departments", "/api/v1/roles"):
        call(p, token)
