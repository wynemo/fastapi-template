python fastapi_main.py

统一用fstring
日志统一用log.py

为前端设置的cors 仅供开发用
```
curl -H "Origin:  http://10.10.1.211:8000" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: X-Requested-With" \
  -X OPTIONS --verbose \
  http://10.10.1.211:8000/api/v1/users/?limit=100
```
