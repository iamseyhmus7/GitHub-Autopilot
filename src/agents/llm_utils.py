from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from src.mcp_client import MCPConnectionManager

async def get_agent_llm(max_output_tokens=1024, allowed_tools: list[str] = None):
    """Ara ajanlar için daha düşük token limitli LLM (Maliyet Optimizasyonu)."""
    tools = await MCPConnectionManager.get_tools()
    
    if allowed_tools:
        tools = [t for t in tools if t.name in allowed_tools]
        
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0, 
        max_tokens=max_output_tokens
    )
    return llm.bind_tools(tools), tools

def create_agent_prompt(system_message: str, github_owner: str, repo_name: str, job_description: str) -> str:
    """Helper to inject state context and strict cost constraints."""
    return f"""{system_message}
    
Analiz Edilecek Aday Reposu: {github_owner}/{repo_name}
İK Pozisyon Gereksinimleri: {job_description}

CRITICAL COST INSTRUCTIONS (MALİYET DÜŞÜRME KURALLARI):
1. LLM Token ve API maliyetlerini minimumda tutmak zorundasın!
2. SADECE kendi uzmanlık alanınla ilgili en fazla 1 veya 2 araç (tool) kullan.
3. Gereksiz yere büyük dosyaları okuma, sadece projenin en kilit dosyalarına (örn: README, package.json veya 1 ana kod dosyası) bak.
4. Mümkün olan en az aracı kullanarak analizini bitir ve kararını ver.
"""

async def run_agent_loop(llm_with_tools, tools, messages, max_iterations=2):
    iterations = 0
    node_tokens = 0
    node_tool_calls = 0
    
    while iterations < max_iterations:
        response = await llm_with_tools.ainvoke(messages)
        messages.append(response)
        
        # Token takibi (Gemini metadata'dan)
        if response.usage_metadata:
            node_tokens += response.usage_metadata.get("total_tokens", 0)
            
        if not response.tool_calls:
            return response.content, node_tokens, node_tool_calls
            
        for tool_call in response.tool_calls:
            node_tool_calls += 1
            print(f"  [Ajan Araç Kullanıyor] {tool_call['name']}")
            tool = next(t for t in tools if t.name == tool_call["name"])
            tool_msg = await tool.ainvoke(tool_call)
            messages.append(tool_msg)
            
        iterations += 1
        
    messages.append(HumanMessage(content="Maliyet limiti aşıldı! Şu ana kadar bulduğun verilerle analizini tamamla."))
    final_resp = await llm_with_tools.ainvoke(messages)
    
    if final_resp.usage_metadata:
        node_tokens += final_resp.usage_metadata.get("total_tokens", 0)
        
    return final_resp.content, node_tokens, node_tool_calls
