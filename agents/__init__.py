"""
Agents package - AI GTM Engineer specialist agents
All agents follow the same interface: async run(task, context) -> Dict
"""
from .manager_agent import ManagerAgent
from .research_agent import ResearchAgent
from .browser_agent import BrowserAgent
from .enrichment_agent import EnrichmentAgent
from .email_agent import EmailAgent
from .crm_agent import CRMAgent
from .calendar_agent import CalendarAgent
from .memory_agent import MemoryAgent

__all__ = [
  "ManagerAgent",
  "ResearchAgent",
  "BrowserAgent",
  "EnrichmentAgent",
  "EmailAgent",
  "CRMAgent",
  "CalendarAgent",
  "MemoryAgent",
]
