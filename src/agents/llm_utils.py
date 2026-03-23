"""llm_utils.py — Ajan LLM yardımcıları + TIMEOUT + DETAYLI LOGGING.

AGENTS.md kuralları gereği:
- LLM çağrıları için 90 saniyelik zaman sınırı
- Araç (tool) çağrıları için 45 saniyelik zaman sınırı
- Paralel ajan çakışmasını önlemek için asyncio.Semaphore
"""

from __future__ import annotations

import asyncio
import time

from langchain_core.messages import HumanMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from src.mcp_client import MCPConnectionManager

# ── Sabitler (AGENTS.md) ─────────────────────────────────────────────
LLM_TIMEOUT  = 90   # saniye — Gemini çağrısı için maksimum bekleme
TOOL_TIMEOUT = 45   # saniye — MCP araç çağrısı için maksimum bekleme

# Paralel ajan race-condition önleme semaforu (maks 5 eş zamanlı araç çağrısı)
_tool_semaphore = asyncio.Semaphore(5)


def _ts() -> str:
    """Şu anki zamanı [HH:MM:SS.xxx] formatında döndürür."""
    t = time.localtime()
    ms = int((time.time() % 1) * 1000)
    return f"[{t.tm_hour:02d}:{t.tm_min:02d}:{t.tm_sec:02d}.{ms:03d}]"


async def get_agent_llm(max_output_tokens: int = 1024, allowed_tools: list[str] | None = None):
    """Ara ajanlar için daha düşük token limitli LLM (Maliyet Optimizasyonu)."""
    tools = await MCPConnectionManager.get_tools()

    if allowed_tools:
        tools = [t for t in tools if t.name in allowed_tools]

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0,
        max_tokens=max_output_tokens,
    )
    return llm.bind_tools(tools), tools


def create_agent_prompt(
    system_message: str,
    github_owner: str,
    repo_name: str,
    job_description: str,
) -> str:
    """Helper — state bağlamını ve maliyet kısıtlarını prompt'a enjekte eder."""
    return f"""{system_message}

Analiz Edilecek Aday Reposu: {github_owner}/{repo_name}
İK Pozisyon Gereksinimleri: {job_description}

CRITICAL COST INSTRUCTIONS (MALİYET DÜŞÜRME KURALLARI):
1. LLM Token ve API maliyetlerini minimumda tutmak zorundasın!
2. SADECE kendi uzmanlık alanınla ilgili en fazla 1 veya 2 araç (tool) kullan.
3. Gereksiz yere büyük dosyaları okuma, sadece projenin en kilit dosyalarına (örn: README, package.json veya 1 ana kod dosyası) bak.
4. Mümkün olan en az aracı kullanarak analizini bitir ve kararını ver.
"""


async def _invoke_llm_with_timeout(llm_with_tools, messages: list, label: str = "") -> object:
    """LLM çağrısını LLM_TIMEOUT saniye ile sınırlar."""
    t0 = time.time()
    tag = f"[LLM{' ' + label if label else ''}]"
    try:
        result = await asyncio.wait_for(
            llm_with_tools.ainvoke(messages),
            timeout=LLM_TIMEOUT,
        )
        return result
    except asyncio.TimeoutError:
        elapsed = time.time() - t0
        print(f"  {_ts()} {tag} ⏰ ZAMAN AŞIMI! ({elapsed:.1f}s >= {LLM_TIMEOUT}s)", flush=True)
        raise TimeoutError(f"LLM {LLM_TIMEOUT}s içinde yanıt vermedi.")


async def _invoke_tool_with_timeout(tool, tool_call: dict) -> ToolMessage:
    """Araç çağrısını TOOL_TIMEOUT saniye ile sınırlar. Semaforu kullanır."""
    name = tool_call["name"]
    args = {k: str(v)[:60] for k, v in tool_call.get("args", {}).items()}
    async with _tool_semaphore:
        try:
            result = await asyncio.wait_for(
                tool.ainvoke(tool_call),
                timeout=TOOL_TIMEOUT,
            )
            return result
        except asyncio.TimeoutError:
            elapsed = time.time() - t0
            print(f"  {_ts()} [TOOL] ⏰ '{name}' ZAMAN AŞIMI! ({elapsed:.1f}s >= {TOOL_TIMEOUT}s)", flush=True)
            return ToolMessage(
                content=f"[TIMEOUT] '{name}' aracı {TOOL_TIMEOUT}s içinde yanıt vermedi. Atlanıyor.",
                tool_call_id=tool_call["id"],
            )
        except Exception as e:
            elapsed = time.time() - t0
            print(f"  {_ts()} [TOOL] ❌ '{name}' HATA ({elapsed:.1f}s): {repr(e)[:200]}", flush=True)
            return ToolMessage(
                content=f"Error in {name}: {repr(e)[:200]}",
                tool_call_id=tool_call["id"],
            )


async def run_agent_loop(
    llm_with_tools,
    tools: list,
    messages: list,
    max_iterations: int = 2,
    agent_name: str = "?",
) -> tuple[str, int, int]:
    """
    Ajan döngüsünü çalıştırır.
    Her LLM çağrısı max 90s, her araç çağrısı max 45s ile sınırlıdır.
    Returns: (rapor_metni, toplam_token, toplam_araç_çağrısı)
    """
    iterations = 0
    node_tokens = 0
    node_tool_calls = 0
    t_start = time.time()

    while iterations < max_iterations:
        iter_label = f"iter={iterations+1}/{max_iterations}"

        # ── LLM Çağrısı (timeout korumalı) ──────────────────────────
        try:
            response = await _invoke_llm_with_timeout(
                llm_with_tools, messages, label=f"{agent_name} {iter_label}"
            )
        except TimeoutError as e:
            print(f"  {_ts()} [{agent_name}] ⏰ LLM timeout, döngü sonlandırılıyor: {e}", flush=True)
            break

        messages.append(response)

        # Token takibi (Gemini metadata)
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            node_tokens += response.usage_metadata.get("total_tokens", 0)

        # Araç çağrısı yoksa ajan kendi sonucunu üretmiş demektir
        if not response.tool_calls:
            total_elapsed = time.time() - t_start
            print(f"  {_ts()} [{agent_name}] ✅ BİTTİ — tool_call yok, yanıt döndürülüyor ({total_elapsed:.1f}s, token={node_tokens})", flush=True)
            return response.content, node_tokens, node_tool_calls

        # ── Araç Çağrıları (max 5, timeout korumalı) ─────────────────
        limited_tool_calls = response.tool_calls[:5]
        for tc in limited_tool_calls:
            node_tool_calls += 1
            tool_obj = next((t for t in tools if t.name == tc["name"]), None)
            if tool_obj is None:
                print(f"  {_ts()} [{agent_name}] ❌ Araç bulunamadı: '{tc['name']}'", flush=True)
                messages.append(
                    ToolMessage(content=f"Tool '{tc['name']}' not found.", tool_call_id=tc["id"])
                )
                continue

            tool_msg = await _invoke_tool_with_timeout(tool_obj, tc)

            # Token Bloat Koruması
            MAX_CHARS = 15_000
            if len(tool_msg.content) > MAX_CHARS:
                print(f"  {_ts()} [{agent_name}] [!] Araç çıktısı kırpılıyor: {len(tool_msg.content)} → {MAX_CHARS} karakter", flush=True)
                tool_msg.content = (
                    tool_msg.content[:MAX_CHARS]
                    + "\n\n[ÇIKTI ÇOK UZUN OLDUĞU İÇİN KIRPILDI.]"
                )

            messages.append(tool_msg)

        iterations += 1

    # ── İterasyon limiti aşıldı — final yanıt üret ───────────────────
    elapsed_so_far = time.time() - t_start
    print(f"  {_ts()} [{agent_name}] İterasyon limiti doldu ({elapsed_so_far:.1f}s). Final LLM çağrısı yapılıyor...", flush=True)

    messages.append(
        HumanMessage(
            content=(
                "Maliyet ve zaman limiti doldu. "
                "Eldeki verilerle en iyi analizini yap ve bitir."
            )
        )
    )

    try:
        final_resp = await _invoke_llm_with_timeout(
            llm_with_tools, messages, label=f"{agent_name} final"
        )
    except TimeoutError as e:
        print(f"  {_ts()} [{agent_name}] ⏰ Final LLM timeout: {e}", flush=True)
        return (
            "Analiz tamamlanamadı — LLM zaman aşımına uğradı. Lütfen tekrar deneyin.",
            node_tokens,
            node_tool_calls,
        )

    if hasattr(final_resp, "usage_metadata") and final_resp.usage_metadata:
        node_tokens += final_resp.usage_metadata.get("total_tokens", 0)

    total_elapsed = time.time() - t_start
    print(f"  {_ts()} [{agent_name}] ✅ TAMAMEN BİTTİ ({total_elapsed:.1f}s, token={node_tokens}, tool_call={node_tool_calls})", flush=True)
    return final_resp.content, node_tokens, node_tool_calls
