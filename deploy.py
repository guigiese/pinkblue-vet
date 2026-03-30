"""
Deploy para Railway — sempre usa o serviço correto.
Uso: python deploy.py
"""
import configparser, subprocess, time, sys
import requests

cfg = configparser.ConfigParser()
cfg.read(".secrets")

RAILWAY_TOKEN = cfg["railway"]["token"]
SERVICE_ID    = cfg["railway"]["service_id"]
ENV_ID        = cfg["railway"]["env_id"]
APP_URL       = cfg["railway"]["url"]
GH_TOKEN      = cfg["github"]["token"]
GH_REPO       = "guigiese/monitor-exames-bitlab"

headers = {"Authorization": f"Bearer {RAILWAY_TOKEN}", "Content-Type": "application/json"}

def gql(query):
    r = requests.post("https://backboard.railway.app/graphql/v2",
                      headers=headers, json={"query": query})
    return r.json()


def push_to_github():
    result = subprocess.run(
        ["git", "push", "origin", "main"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print("Erro no git push:", result.stderr)
        sys.exit(1)
    print("GitHub: push OK")


def get_latest_commit():
    r = requests.get(
        f"https://api.github.com/repos/{GH_REPO}/commits/main",
        headers={"Authorization": f"token {GH_TOKEN}"}
    )
    sha = r.json()["sha"]
    msg = r.json()["commit"]["message"].split("\n")[0]
    return sha, msg


def trigger_redeploy(commit_sha: str):
    """Deploy latest commit by SHA (not a redeploy of old image)."""
    r = gql(f"""mutation {{ serviceInstanceDeploy(
      serviceId: "{SERVICE_ID}"
      environmentId: "{ENV_ID}"
      commitSha: "{commit_sha}"
    ) }}""")
    return r.get("data", {}).get("serviceInstanceDeploy", False)


def wait_for_deploy(timeout=180):
    start = time.time()
    while time.time() - start < timeout:
        r = gql(f"""query {{
          deployments(first: 1, input: {{serviceId: "{SERVICE_ID}"}}) {{
            edges {{ node {{ id status createdAt }} }}
          }}
        }}""")
        edges = r["data"]["deployments"]["edges"]
        if edges:
            d = edges[0]["node"]
            status = d["status"]
            print(f"  [{status}] {d['id'][:8]} {d['createdAt'][11:19]}", end="\r")
            if status == "SUCCESS":
                print()
                return True
            if status in ("FAILED", "CRASHED"):
                print()
                return False
        time.sleep(8)
    return False


if __name__ == "__main__":
    print("=== Deploy Railway ===")

    sha, msg = get_latest_commit()
    print(f"Commit: {sha[:8]} | {msg}")

    print("Disparando redeploy...")
    ok = trigger_redeploy(sha)
    if not ok:
        print("Erro ao disparar redeploy")
        sys.exit(1)

    print("Aguardando build...")
    time.sleep(5)
    success = wait_for_deploy()

    if success:
        print(f"\nDeploy OK — {APP_URL}")
    else:
        print("\nDeploy FALHOU — verifique os logs no Railway")
        sys.exit(1)
