import json
import sys
import urllib.request
import urllib.parse

BASE_URL = "http://localhost:8500/api"

def make_request(url, method="GET", data=None):
    req = urllib.request.Request(url, method=method)
    if data:
        req.data = json.dumps(data).encode('utf-8')
        req.add_header('Content-Type', 'application/json')
    
    try:
        with urllib.request.urlopen(req) as res:
            return {
                "status_code": res.getcode(),
                "json": json.loads(res.read().decode('utf-8'))
            }
    except urllib.error.HTTPError as e:
        return {
            "status_code": e.code,
            "error": str(e)
        }
    except Exception as e:
        return {"error": str(e)}

def test_list_skills():
    print("Testing GET /api/skills...")
    res = make_request(f"{BASE_URL}/skills")
    
    if res.get("status_code") != 200:
        print(f"FAILED: Status {res.get('status_code')}")
        return False
    
    data = res["json"]
    print(f"Skills found: {len(data.get('skills', []))}")
    
    for skill in data.get('skills', []):
        print(f"  - {skill['name']}")
        if 'files' in skill:
            print(f"    Files: {len(skill['files'])}")
            for f in skill['files'][:3]:
                print(f"      - {f['path']} ({f['type']})")
        else:
            print("    FAILED: No 'files' key found!")
            return False
            
    return True

def test_get_file(skill_name, file_path):
    print(f"\nTesting GET file content for {skill_name}/{file_path}...")
    params = urllib.parse.urlencode({"path": file_path})
    res = make_request(f"{BASE_URL}/skills/{skill_name}/files?{params}")
    
    if res.get("status_code") != 200:
        print(f"FAILED: Status {res.get('status_code')}: {res.get('error')}")
        return False
        
    data = res["json"]
    content_len = len(data.get('content', ''))
    print(f"Content length: {content_len}")
    return True

if __name__ == "__main__":
    if not test_list_skills():
        sys.exit(1)
        
    if test_get_file("pptx", "SKILL.md"):
        print("SUCCESS")
    else:
        print("PARTIAL FAILURE")
