"""llm_utils.py — Ajan LLM yardımcıları + TIMEOUT + maliyet koruması.

AGENTS.md kuralları gereği:
- LLM çağrıları için 90 saniyelik zaman sınırı
- Araç (tool) çağrıları için 45 saniyelik zaman sınırı
- Paralel ajan çakışmasını önlemek için asyncio.Semaphore
"""

from __future__ import annotations

import asyncio

from langchain_core.messages import HumanMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from src.mcp_client import MCPConnectionManager

# ── Sabitler (AGENTS.md) ─────────────────────────────────────────────
LLM_TIMEOUT  = 90   # saniye — Gemini çağrısı için maksimum bekleme
TOOL_TIMEOUT = 45   # saniye — MCP araç çağrısı için maksimum bekleme

# Paralel ajan race-condition önleme semaforu (maks 5 eş zamanlı araç çağrısı)
_tool_semaphore = asyncio.Semaphore(5)


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


async def _invoke_llm_with_timeout(llm_with_tools, messages: list) -> object:
    """LLM çağrısını LLM_TIMEOUT saniye ile sınırlar. Aşılırsa TimeoutError."""
    try:
        return await asyncio.wait_for(
            llm_with_tools.ainvoke(messages),
            timeout=LLM_TIMEOUT,
        )
    except asyncio.TimeoutError:
        raise TimeoutError(
            f"[TIMEOUT] LLM yanıt vermedi ({LLM_TIMEOUT}s). "
            "Eldeki verilerle rapor üretiliyor..."
        )


async def _invoke_tool_with_timeout(tool, tool_call: dict) -> ToolMessage:
    """Araç çağrısını TOOL_TIMEOUT saniye ile sınırlar. Semaforu kullanır."""
    async with _tool_semaphore:
        try:
            return await asyncio.wait_for(
                tool.ainvoke(tool_call),
                timeout=TOOL_TIMEOUT,
            )
        except asyncio.TimeoutError:
            return ToolMessage(
                content=f"[TIMEOUT] {tool_call['name']} aracı {TOOL_TIMEOUT}s içinde yanıt vermedi. Atlanıyor.",
                tool_call_id=tool_call["id"],
            )


async def run_agent_loop(
    llm_with_tools,
    tools: list,
    messages: list,
    max_iterations: int = 2,
) -> tuple[str, int, int]:
    """
    Ajan döngüsünü çalıştırır.
    Her LLM çağrısı max 90s, her araç çağrısı max 45s ile sınırlıdır.
    Returns: (rapor_metni, toplam_token, toplam_araç_çağrısı)
    """
    iterations = 0
    node_tokens = 0
    node_tool_calls = 0

    while iterations < max_iterations:
        # ── LLM Çağrısı (timeout korumalı) ──────────────────────────
        try:
            response = await _invoke_llm_with_timeout(llm_with_tools, messages)
        except TimeoutError as e:
            print(f"  ⏰ {e}")
            break

        messages.append(response)

        # Token takibi (Gemini metadata)
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            node_tokens += response.usage_metadata.get("total_tokens", 0)

        # Araç çağrısı yoksa ajan kendi sonucunu üretmiş demektir
        if not response.tool_calls:
            return response.content, node_tokens, node_tool_calls

        # ── Araç Çağrıları (max 5, timeout korumalı) ─────────────────
        limited_tool_calls = response.tool_calls[:5]
        if len(response.tool_calls) > 5:
            print(f"  [!] Çok fazla araç çağrısı ({len(response.tool_calls)}), ilk 5'i işleniyor...")

        for tool_call in limited_tool_calls:
            node_tool_calls += 1
            print(f"  [Ajan Araç Kullanıyor] {tool_call['name']}")
            try:
                tool = next(t for t in tools if t.name == tool_call["name"])
                tool_msg = await _invoke_tool_with_timeout(tool, tool_call)

                # Token Bloat Koruması — araç çıktısını kırp
                MAX_CHARS = 15_000
                if len(tool_msg.content) > MAX_CHARS:
                    print(f"  [!] Araç çıktısı çok büyük ({len(tool_msg.content)} karakter), kırpılıyor...")
                    tool_msg.content = (
                        tool_msg.content[:MAX_CHARS]
                        + "\n\n[ÇIKTI ÇOK UZUN OLDUĞU İÇİN KIRPILDI.]"
                    )

                messages.append(tool_msg)

            except Exception as e:
                error_msg = repr(e)
                print(f"  [!] KRİTİK ARAÇ HATASI ({tool_call['name']}): {error_msg}")
                messages.append(
                    ToolMessage(
                        content=f"Error in {tool_call['name']}: {error_msg}",
                        tool_call_id=tool_call["id"],
                    )
                )

        iterations += 1

    # ── İterasyon / Timeout limiti aşıldı — final yanıt üret ─────────
    messages.append(
        HumanMessage(
            content=(
                "Maliyet ve zaman limiti doldu. "
                "Eldeki verilerle en iyi analizini yap ve bitir."
            )
        )
    )

    try:
        final_resp = await _invoke_llm_with_timeout(llm_with_tools, messages)
    except TimeoutError as e:
        print(f"  ⏰ Final LLM: {e}")
        return (
            "Analiz tamamlanamadı — LLM zaman aşımına uğradı. "
            "Lütfen tekrar deneyin.",
            node_tokens,
            node_tool_calls,
        )

    if hasattr(final_resp, "usage_metadata") and final_resp.usage_metadata:
        node_tokens += final_resp.usage_metadata.get("total_tokens", 0)

    return final_resp.content, node_tokens, node_tool_calls
