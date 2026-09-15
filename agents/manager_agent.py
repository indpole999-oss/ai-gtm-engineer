
"""
Manager Agent - Main GTM Agent Orchestrator

Routes tasks to specialist agents.

Stage 9 Compatible
"""

import logging
from typing import Optional, Dict, Any

from agents.research_agent import ResearchAgent
from agents.enrichment_agent import EnrichmentAgent
from agents.email_agent import EmailAgent
from agents.crm_agent import CRMAgent
from agents.calendar_agent import CalendarAgent


logger = logging.getLogger(__name__)


class ManagerAgent:
    """
    Main AI GTM Orchestrator.

    Responsibilities:
    - Receive GTM tasks
    - Route tasks
    - Execute specialist agents
    - Manage workflow execution
    """

    def __init__(self):

        self.agents = {
            "research": ResearchAgent(),
            "enrichment": EnrichmentAgent(),
            "email": EmailAgent(),
            "crm": CRMAgent(),
            "calendar": CalendarAgent(),
        }

    # ========================================================
    # Main Agent Entry Point
    # ========================================================

    async def run(
        self,
        task: str,
        target_agent: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:

        logger.info(
            "Manager received task: %s",
            task,
        )

        context = context or {}

        try:

            # ------------------------------------------------
            # Determine target
            # ------------------------------------------------

            if target_agent:
                agent_name = target_agent
            else:
                agent_name = self.route_task(task)

            # ------------------------------------------------
            # Pipeline execution
            # ------------------------------------------------
            # "pipeline" is not a specialist agent.
            # It must be handled by run_pipeline().
            # ------------------------------------------------

            if agent_name == "pipeline":

                pipeline_result = await self.run_pipeline(
                    context=context
                )

                return {
                    "status": "completed",
                    "agent_used": "pipeline",
                    "task": task,
                    "result": pipeline_result,
                }

            # ------------------------------------------------
            # Validate specialist agent
            # ------------------------------------------------

            if agent_name not in self.agents:

                return {
                    "status": "error",
                    "reason": (
                        f"Agent {agent_name} not available"
                    ),
                }

            # ------------------------------------------------
            # Execute specialist agent
            # ------------------------------------------------

            agent = self.agents[agent_name]

            result = await agent.run(
                task=task,
                context=context,
            )

            return {
                "status": "completed",
                "agent_used": agent_name,
                "task": task,
                "result": result,
            }

        except Exception as e:

            logger.exception(
                "Manager execution failed"
            )

            return {
                "status": "error",
                "reason": str(e),
            }

    # ========================================================
    # Full GTM Pipeline
    # ========================================================

    async def run_pipeline(
        self,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:

        """
        Full GTM Pipeline

        Research
            |
            v
        Enrichment
            |
            v
        Email
            |
            v
        CRM
            |
            v
        Calendar
        """

        context = context or {}

        results: Dict[str, Any] = {}

        # ----------------------------------------------------
        # Research
        # ----------------------------------------------------

        results["research"] = await self.agents[
            "research"
        ].run(
            task="research company",
            context=context,
        )

        # ----------------------------------------------------
        # Enrichment
        # ----------------------------------------------------

        results["enrichment"] = await self.agents[
            "enrichment"
        ].run(
            task="enrich company",
            context=context,
        )

        # ----------------------------------------------------
        # Add enrichment data to shared context
        # ----------------------------------------------------

        context["enrichment"] = results[
            "enrichment"
        ]

        # ----------------------------------------------------
        # Email
        # ----------------------------------------------------

        results["email"] = await self.agents[
            "email"
        ].run(
            task="generate outreach email",
            context=context,
        )

        # ----------------------------------------------------
        # CRM
        # ----------------------------------------------------

        results["crm"] = await self.agents[
            "crm"
        ].run(
            task="create crm record",
            context=context,
        )

        # ----------------------------------------------------
        # Calendar
        # ----------------------------------------------------

        results["calendar"] = await self.agents[
            "calendar"
        ].run(
            task="schedule follow up",
            context=context,
        )

        # ----------------------------------------------------
        # Final pipeline result
        # ----------------------------------------------------

        return {
            "status": "completed",
            "pipeline": results,
        }

    # ========================================================
    # Task Router
    # ========================================================

    def route_task(
        self,
        task: str,
    ) -> str:

        task = (task or "").lower().strip()

        # Pipeline must be checked first because
        # pipeline tasks may also contain words such as
        # research, email, crm, etc.

        if "pipeline" in task:

            return "pipeline"

        if "research" in task:

            return "research"

        if "enrich" in task:

            return "enrichment"

        if (
            "email" in task
            or "outreach" in task
        ):

            return "email"

        if "crm" in task:

            return "crm"

        if (
            "meeting" in task
            or "calendar" in task
        ):

            return "calendar"

        return "research"
