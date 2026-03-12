from langchain_core.messages import SystemMessage, HumanMessage
from src.state import HRGraphState
from src.agents.llm_utils import get_agent_llm, create_agent_prompt, run_agent_loop

async def repo_explorer_node(state: HRGraphState):
    """Ajan 1: Sistem Haritacısı (Repository Mapper)"""
    print("🤖 [Ajan 1] Repo Explorer (Sistem Haritacısı) devrede...")
    
    llm_with_tools, tools = await get_agent_llm(allowed_tools=["get_repo_info", "list_repo_files", "get_file_content"])
    
    sys_prompt = create_agent_prompt(
        "Sen 'Repository Mapper' ajanısın. Görevin projenin klasör yapısını, ana dosyalarını ve README'sini (get_repo_info, list_repo_files, get_file_content) inceleyip projenin genel amacını anlatan 2-3 paragraflık bir özet çıkarmaktır.",
        state["github_owner"], state["repo_name"], state["job_description"]
    )
    
    messages = [
        SystemMessage(content=sys_prompt),
        HumanMessage(content="Lütfen repoyu haritala ve projenin genel özetini çıkar.")
    ]
    
    res, tokens, tool_calls = await run_agent_loop(llm_with_tools, tools, messages)
    return {
        "repo_overview": res, 
        "total_tokens": tokens,
        "total_tool_calls": tool_calls,
        "current_agent": "Repo Explorer"
    }

async def dependency_analyst_node(state: HRGraphState):
    """Ajan 2: Dependency Analyst (Teknoloji & Kütüphane Analisti)"""
    print("🤖 [Ajan 2] Dependency Analyst (Kütüphane Analisti) devrede...")
    
    llm_with_tools, tools = await get_agent_llm(allowed_tools=["list_repo_files", "get_file_content"])
    
    sys_prompt = create_agent_prompt(
        "Sen 'Dependency Analyst' ajanısın. Görevin package.json, pom.xml, requirements.txt gibi dosyaları bulup okumak ve adayın kullandığı teknoloji yığınını, frameworkleri ve kütüphaneleri net bir liste halinde çıkarmaktır.",
        state["github_owner"], state["repo_name"], state["job_description"]
    )
    
    messages = [
        SystemMessage(content=sys_prompt),
        HumanMessage(content="Hangi teknolojiler ve kütüphaneler kullanılmış? Lütfen listele.")
    ]
    
    res, tokens, tool_calls = await run_agent_loop(llm_with_tools, tools, messages)
    return {
        "tech_stack": res, 
        "total_tokens": tokens,
        "total_tool_calls": tool_calls,
        "current_agent": "Dependency Analyst"
    }

