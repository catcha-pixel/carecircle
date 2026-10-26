"""Quick tests for the scam check API.  Run:  python3 test_api.py"""

import json

from fastapi.testclient import TestClient

from api import app

client = TestClient(app)

CASES = [
    ("en", "scam", "Grandpa it's me, I wrecked the car and I'm at the police station. "
                    "I need $1500 for bail, please send Apple gift cards and don't tell mom"),
    ("en", "scam", "FasTrak: Unpaid toll of $5.40. Pay within 12 hours to avoid a $75 fine: fastrak-ca-pay.info"),
    ("es", "scam", "Aviso: su cuenta de Zelle fue bloqueada. Envie su contrasena para desbloquearla inmediatamente"),
    ("en", "safe", "Hi Grandma, I'll swing by Sunday after church to fix your TV"),
    ("en", "safe", "CVS Pharmacy: Your prescription is ready for pickup. Reply STOP to opt out"),
]

assert client.get("/health").json() == {"status": "ok"}
assert client.post("/check-message", json={"text": ""}).status_code == 422  # empty text rejected

passed = 0
for lang, expected, text in CASES:
    r = client.post("/check-message", json={"text": text, "lang": lang})
    assert r.status_code == 200
    body = r.json()
    ok = (body["verdict"] == "safe") == (expected == "safe")
    passed += ok
    print(f"{'PASS' if ok else 'FAIL'}  {body['icon']} {body['verdict']:8} {text[:60]}")

print(f"\n{passed}/{len(CASES)} passed\n")
print("Example full response:")
print(json.dumps(client.post("/check-message", json={"text": CASES[0][2]}).json(),
                 indent=2, ensure_ascii=False))
