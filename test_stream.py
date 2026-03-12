import requests
import json

url = "http://localhost:8000/api/v1/analyze-stream"
payload = {
    "github_owner": "Ahmetgrkm",
    "repo_name": "automationexercise-ui-test-framework",
    "job_description": "Clean Code ve SOLID prensiplerine hakim otomasyon uzmanı arayışı"
}

print(f"Baglaniliyor: {url}...")
try:
    with requests.post(url, json=payload, stream=True) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith("data: "):
                    data_str = decoded_line[6:]
                    try:
                        data_json = json.loads(data_str)
                        if data_json.get('type') == 'agent_update':
                            print(f"[AJAN BİLDİRİMİ] >> {data_json.get('agent')} taranan kod: {data_json.get('tokens_so_far')} token, istek: {data_json.get('tool_calls_so_far')}")
                        elif data_json.get('type') == 'final_report':
                            print(f"\n[NİHAİ RAPOR HAZIR] =========================\n{data_json.get('final_report')}\n=============================================\n")
                        elif data_json.get('type') == 'system':
                            print(f"[SİSTEM] {data_json.get('status')}")
                        else:
                            print(data_json)
                    except json.JSONDecodeError:
                        print("JSON parse hatasi:", data_str)
except Exception as e:
    print("Hata olustu:", e)
