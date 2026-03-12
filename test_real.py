"""Basit gercek API testi — sonuclari JSON olarak dosyaya yazar."""
import asyncio
import json
import sys
import os
import logging

# Loglari kapat
logging.disable(logging.CRITICAL)

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from dotenv import load_dotenv
load_dotenv()

from mcp_github_advanced.auth import AuthManager, AuthSettings, validate_token
from mcp_github_advanced.github import GitHubClient

OWNER = "iamseyhmus7"
REPO = "GitHub-Autopilot"


async def test():
    results = {}
    s = AuthSettings()
    a = AuthManager(s)
    c = GitHubClient(auth=a, cache=None)
    await c.start()

    try:
        # 0. Token dogrulama
        u = await validate_token(s.github_token)
        results["0_token_dogrulama"] = f"BASARILI - kullanici: {u['login']}"

        # 1. Repo bilgisi
        r = await c.get_repo_info(OWNER, REPO)
        results["1_get_repo_info"] = f"BASARILI - {r['name']}, {r['stargazers_count']} yildiz, dil: {r['language']}"

        # 2. Dosya listesi
        f = await c.list_repo_files(OWNER, REPO)
        results["2_list_repo_files"] = f"BASARILI - {len(f)} dosya bulundu"

        # 3. Dosya icerigi
        fc = await c.get_file_content(OWNER, REPO, "README.md")
        results["3_get_file_content"] = f"BASARILI - {fc['name']} ({fc['size']} byte)"

        # 4. Kod arama
        try:
            sr = await c.search_code(OWNER, REPO, "MCP")
            results["4_search_code"] = f"BASARILI - {len(sr)} sonuc"
        except Exception as e:
            results["4_search_code"] = f"HATA - {e}"

        # 5. Commit listesi
        cm = await c.list_commits(OWNER, REPO, per_page=3)
        results["5_list_commits"] = f"BASARILI - {len(cm)} commit"

        # 6. Commit diff
        if cm:
            d = await c.get_commit_diff(OWNER, REPO, cm[0]["full_sha"])
            results["6_get_commit_diff"] = f"BASARILI - {d['sha'][:7]}: {len(d['files'])} dosya degisti"

        # 7. Katki yapanlar
        st = await c.get_contributor_stats(OWNER, REPO)
        results["7_get_contributor_stats"] = f"BASARILI - {len(st)} katki yapan"

        # 8. PR listesi
        pr = await c.list_pull_requests(OWNER, REPO, state="all")
        results["8_list_pull_requests"] = f"BASARILI - {len(pr)} PR"

        # 9. Issue listesi
        iss = await c.list_issues(OWNER, REPO, state="all")
        results["9_list_issues"] = f"BASARILI - {len(iss)} issue"

        # 10. Workflow runs
        try:
            wr = await c.get_workflow_runs(OWNER, REPO)
            results["10_get_workflow_runs"] = f"BASARILI - {len(wr)} run"
        except Exception as e:
            results["10_get_workflow_runs"] = f"HATA - {e}"

    except Exception as e:
        results["GENEL_HATA"] = str(e)
    finally:
        await c.close()

    # Sonuclari dosyaya yaz
    with open("test_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Ekrana da yazdir
    for k, v in results.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    asyncio.run(test())
