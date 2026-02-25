# Admin attendance location metadata – verification

Ensure `GET /api/v1/admin/attendance/today` and `GET /api/v1/admin/attendance` return production-level punch metadata: `punch_in_geo`, `punch_out_geo`, `punch_in_ip`, `punch_out_ip`, `punch_in_device_id`, `punch_out_device_id`, `punch_in_source`, `punch_out_source`.

## 1. Punch-in with geo (as employee)

```bash
TOKEN_EMP=$(curl -s -X POST "http://localhost:8001/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"emp_code":"YOUR_EMP_CODE","password":"YOUR_PASSWORD"}' | jq -r '.access_token')

curl -s -X POST "http://localhost:8001/api/v1/attendance/punch-in" \
  -H "Authorization: Bearer $TOKEN_EMP" \
  -H "Content-Type: application/json" \
  -d '{
    "lat": 28.6139,
    "lng": 77.209,
    "accuracy": 12.5,
    "address": "Office Tower",
    "device_id": "device-001",
    "source": "MOBILE"
  }' | jq '{ punch_in_geo, punch_in_device_id, punch_in_source, punch_in_ip }'
```

**Expected:** `punch_in_geo` has `lat`, `lng`, `accuracy`, `address`, `source`; `punch_in_device_id`, `punch_in_source` set; `punch_in_ip` from client.

## 2. Admin today returns location

```bash
TOKEN_HR=$(curl -s -X POST "http://localhost:8001/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"emp_code":"HR_EMP_CODE","password":"HR_PASSWORD"}' | jq -r '.access_token')

curl -s "http://localhost:8001/api/v1/admin/attendance/today" \
  -H "Authorization: Bearer $TOKEN_HR" | jq '.[0] | {
    punch_in_geo,
    punch_out_geo,
    punch_in_ip,
    punch_out_ip,
    punch_in_device_id,
    punch_out_device_id,
    punch_in_source,
    punch_out_source
  }'
```

**Expected:** Same session includes all fields above; geo objects when punch was done with location; null for punch_out_* until punch-out.

## 3. Punch-out with geo then re-check admin

```bash
curl -s -X POST "http://localhost:8001/api/v1/attendance/punch-out" \
  -H "Authorization: Bearer $TOKEN_EMP" \
  -H "Content-Type: application/json" \
  -d '{"lat": 28.614, "lng": 77.21, "accuracy": 10, "source": "MOBILE", "device_id": "device-001"}' | jq '{ punch_out_geo, punch_out_device_id, punch_out_source }'

curl -s "http://localhost:8001/api/v1/admin/attendance/today" -H "Authorization: Bearer $TOKEN_HR" | jq '.[0] | { punch_in_geo, punch_out_geo }'
```

**Expected:** First response has `punch_out_geo` with lat/lng; second response shows both `punch_in_geo` and `punch_out_geo` on the session.

## 4. Automated tests

```bash
cd hrms-backend
python -m pytest app/tests/test_admin_attendance_geo_response.py -v
```

Expect: `test_punch_in_with_geo_then_admin_today_returns_geo`, `test_punch_out_with_geo_then_admin_returns_punch_out_geo`, `test_admin_today_null_geo_returns_null` all PASSED.
