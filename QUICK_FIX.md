# Quick Fix for Login Issues

## Problem
- CORS error: "No 'Access-Control-Allow-Origin' header"
- HTTP 500 Internal Server Error

## Solution Steps

### 1. Make sure backend is running
```bash
cd d:\HRMS\hrms-backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Test the backend directly
Open in browser: `http://localhost:8000/docs`

Or test login endpoint:
```bash
cd d:\HRMS\hrms-backend
python test_login.py
```

### 3. Verify CORS is working
The backend should now:
- Allow all origins (`*`)
- Include CORS headers in all responses (including errors)
- Handle password verification for both bcrypt formats

### 4. Check frontend .env.local
Make sure `hrms-admin/.env.local` has:
```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

### 5. Restart both servers
1. **Backend**: Stop (Ctrl+C) and restart uvicorn
2. **Frontend**: Stop (Ctrl+C) and restart `npm run dev`

### 6. Clear browser cache
- Hard refresh: Ctrl+Shift+R (Windows) or Cmd+Shift+R (Mac)
- Or clear browser cache and reload

## If still not working:

1. **Check backend logs** - Look at the terminal running uvicorn for the actual error
2. **Check browser Network tab** - See the actual request/response
3. **Test backend directly** - Use `test_login.py` or Postman/curl

## Expected Behavior

After fixes:
- ✅ No CORS errors
- ✅ Login returns 200 with access_token
- ✅ Frontend redirects to /dashboard
