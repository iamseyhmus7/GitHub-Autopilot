from langchain_core.messages import SystemMessage, HumanMessage
from src.state import HRGraphState
from src.agents.llm_utils import get_agent_llm, create_agent_prompt, run_agent_loop

async def git_historian_node(state: HRGraphState):
    """Ajan 6: Dedektif (Git Historian)"""
    print("🤖 [Ajan 6] Git Historian (Dedektif) devrede...")
    llm_with_tools, tools = await get_agent_llm(allowed_tools=["list_commits"])
    sys_prompt = create_agent_prompt(
        "Sen 'Git Historian' (Dedektif) ajanısın. Adayın projeye emek verip vermediğini anlamak için SADECE 1 kere list_commits kullan. Fazla arama yapma.",
        state["github_owner"], state["repo_name"], state["job_description"]
    )
    messages = [SystemMessage(content=sys_prompt), HumanMessage(content="Commit geçmişini incele ve 'Kopya Mı, Gerçek Emek Mi?' sorusuna yanıt ver.")]
    res, tokens, tool_calls = await run_agent_loop(llm_with_tools, tools, messages)
    return {
        "commit_history_analysis": res, 
        "total_tokens": tokens,
        "total_tool_calls": tool_calls,
        "current_agent": "Git Historian"
    }

async def devops_evaluator_node(state: HRGraphState):
    """Ajan 7: DevOps & Testing Evaluator"""
    print("🤖 [Ajan 7] DevOps & Testing Evaluator devrede...")
    llm_with_tools, tools = await get_agent_llm(allowed_tools=["list_repo_files", "get_file_content"])
    sys_prompt = create_agent_prompt(
        "Sen 'DevOps & Testing Evaluator' ajanısın. Aday Unit Test yazmış mı veya GitHub Actions/CI-CD kullanmış mı diye sadece 1 kere root dosyaları kontrol et.",
        state["github_owner"], state["repo_name"], state["job_description"]
    )
    messages = [SystemMessage(content=sys_prompt), HumanMessage(content="Lütfen testlerin (Unit tests) varlığını ve GitHub Actions/CI-CD iş akışlarını kontrol et.")]
    res, tokens, tool_calls = await run_agent_loop(llm_with_tools, tools, messages)
    return {
        "ci_cd_testing_status": res, 
        "total_tokens": tokens,
        "total_tool_calls": tool_calls,
        "current_agent": "DevOps Evaluator"
    }

async def pr_manager_node(state: HRGraphState):
    """Ajan 8: Issue & PR Manager"""
    print("🤖 [Ajan 8] Issue & PR Manager devrede...")
    llm_with_tools, tools = await get_agent_llm(allowed_tools=["list_pull_requests", "list_issues"])
    sys_prompt = create_agent_prompt(
        "Sen 'Issue & PR Manager' ajanısın. Aday PR veya Issue kullanmış mı diye maksimum 1 araç kullan ve hızlıca çık.",
        state["github_owner"], state["repo_name"], state["job_description"]
    )
    messages = [SystemMessage(content=sys_prompt), HumanMessage(content="Issue ve Pull Request geçmişini inceleyerek projenin yönetim standartlarını analiz et.")]
    res, tokens, tool_calls = await run_agent_loop(llm_with_tools, tools, messages)
    return {
        "teamwork_pr_analysis": res, 
        "total_tokens": tokens,
        "total_tool_calls": tool_calls,
        "current_agent": "PR Manager"
    }
