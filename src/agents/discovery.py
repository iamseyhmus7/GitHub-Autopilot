from langchain_core.messages import SystemMessage, HumanMessage
from src.state import HRGraphState
from src.agents.llm_utils import get_agent_llm, create_agent_prompt, run_agent_loop

async def repo_explorer_node(state: HRGraphState):
    """Ajan 1: Sistem Haritacısı (Repository Mapper)"""
    print(f"🤖 [Ajan 1] Repo Explorer {state['relevant_repos']} projelerini inceliyor...")
    
    llm_with_tools, tools = await get_agent_llm(allowed_tools=["get_repo_info", "list_repo_files", "get_file_content"])
    
    overviews = []
    for repo in state["relevant_repos"]:
        sys_prompt = create_agent_prompt(
            f"Sen 'Repository Mapper' ajanısın. Görevin {repo} projesini inceleyip projenin genel amacını anlatan bir özet çıkarmaktır.",
            state["github_owner"], repo, state["job_description"]
        )
        messages = [SystemMessage(content=sys_prompt), HumanMessage(content=f"{repo} reposunu haritala.")]
        res, _, _ = await run_agent_loop(llm_with_tools, tools, messages)
        overviews.append(f"--- {repo} Özeti ---\n{res}")

    return {
        "repo_overview": "\n\n".join(overviews),
        "current_agent": "Repo Explorer"
    }

async def dependency_analyst_node(state: HRGraphState):
    """Ajan 2: Dependency Analyst (Teknoloji & Kütüphane Analisti)"""
    print(f"🤖 [Ajan 2] Dependency Analyst {state['relevant_repos']} için tech-stack çıkarıyor...")
    
    llm_with_tools, tools = await get_agent_llm(allowed_tools=["list_repo_files", "get_file_content"])
    
    stacks = []
    for repo in state["relevant_repos"]:
        sys_prompt = create_agent_prompt(
            f"Sen 'Dependency Analyst' ajanısın. Görevin {repo} projesindeki bağımlılık dosyalarını bulup teknoloji yığınını çıkarmaktır.",
            state["github_owner"], repo, state["job_description"]
        )
        messages = [SystemMessage(content=sys_prompt), HumanMessage(content=f"{repo} teknolojilerini listele.")]
        res, _, _ = await run_agent_loop(llm_with_tools, tools, messages)
        stacks.append(f"--- {repo} Teknolojileri ---\n{res}")

    return {
        "tech_stack": "\n\n".join(stacks),
        "current_agent": "Dependency Analyst"
    }

