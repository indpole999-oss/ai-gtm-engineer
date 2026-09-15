"""
Workflow Engine
GTM Workflow Execution Engine
"""

import logging
from typing import Dict, Any


from agents.manager_agent import ManagerAgent


logger = logging.getLogger(__name__)


class WorkflowEngine:

    def __init__(self):

        self.manager = ManagerAgent()

        self.workflows = {

            "lead_pipeline": [
                "research",
                "enrichment",
                "email",
                "crm",
                "calendar"
            ],

            "email_sequence": [
                "research",
                "email"
            ]
        }

    # ----------------------------------------------------------
    # Safely unwrap nested agent/manager result wrappers
    # ----------------------------------------------------------

    @staticmethod
    def _unwrap_result(value: Any) -> Any:

        current = value

        # Protect against malformed/circular-style nesting.
        for _ in range(5):

            if not isinstance(current, dict):
                return current

            nested = current.get("result")

            if not isinstance(nested, dict):
                return current

            # Stop when this result already looks like the
            # actual agent payload.
            if any(
                key in current
                for key in (
                    "contacts",
                    "contacts_found",
                    "company",
                    "status",
                    "emails",
                    "found_url",
                    "message"
                )
            ) and any(
                key in nested
                for key in (
                    "contacts",
                    "contacts_found",
                    "company",
                    "emails",
                    "found_url"
                )
            ):

                current = nested
                continue

            current = nested

        return current

    async def execute(
        self,
        workflow_name: str,
        context: Dict[str, Any]
    ):

        if workflow_name not in self.workflows:

            return {
                "status": "failed",
                "message": "Workflow not found"
            }

        steps = self.workflows[workflow_name]

        logger.info(
            f"Starting workflow {workflow_name}"
        )

        results = []

        current_context = dict(context)

        for step in steps:

            logger.info(
                f"Running agent {step}"
            )

            result = await self.manager.run(
                task=f"execute {step}",
                target_agent=step,
                context=current_context
            )

            results.append(
                {
                    "agent": step,
                    "result": result
                }
            )

            # --------------------------------------------------
            # Preserve raw agent output
            # --------------------------------------------------

            if step == "email":
                current_context["email_result"] = result
            else:
                current_context[step] = result

            # --------------------------------------------------
            # Get actual agent payload regardless of nested
            # ManagerAgent result wrappers.
            # --------------------------------------------------

            actual_result = self._unwrap_result(result)

            # --------------------------------------------------
            # Research -> Email handoff
            # --------------------------------------------------

            if step == "research":

                current_context["company_research"] = actual_result

            # --------------------------------------------------
            # Enrichment -> Email handoff
            # --------------------------------------------------

            if step == "enrichment":

                enrichment_result = actual_result

                current_context["enrichment"] = enrichment_result

                contacts = []

                if isinstance(enrichment_result, dict):

                    contacts = enrichment_result.get(
                        "contacts",
                        []
                    )

                # --------------------------------------------------
                # Pass first discovered contact to EmailAgent
                # --------------------------------------------------

                if contacts:

                    first_contact = contacts[0]

                    if isinstance(first_contact, dict):

                        contact_email = (
                            first_contact.get("email")
                            or first_contact.get("email_address")
                            or ""
                        )

                        contact_name = (
                            first_contact.get("name")
                            or first_contact.get("full_name")
                            or ""
                        )

                        contact_title = (
                            first_contact.get("title")
                            or first_contact.get("job_title")
                            or ""
                        )

                        contact_linkedin = (
                            first_contact.get("linkedin")
                            or first_contact.get("linkedin_url")
                            or ""
                        )

                        current_context["prospect"] = {
                            "name": contact_name,
                            "title": contact_title,
                            "email": contact_email,
                            "linkedin": contact_linkedin,
                            "company": current_context.get(
                                "company_name",
                                current_context.get(
                                    "company",
                                    ""
                                )
                            )
                        }

                        if contact_email:

                            current_context["email"] = contact_email

                            current_context["to_email"] = contact_email

                            # Additional aliases make the handoff
                            # compatible with different EmailAgent
                            # implementations.

                            current_context["recipient_email"] = (
                                contact_email
                            )

                            current_context["recipient"] = (
                                contact_email
                            )

                            logger.info(
                                "Enrichment -> Email handoff: "
                                f"{contact_email}"
                            )

                else:

                    logger.info(
                        "Enrichment completed without contacts"
                    )

        # ----------------------------------------------------------
        # Determine overall workflow status
        # ----------------------------------------------------------

        stage_statuses = []

        for item in results:

            stage_wrapper = item.get(
                "result",
                {}
            )

            stage_result = self._unwrap_result(
                stage_wrapper
            )

            if isinstance(stage_result, dict):

                stage_statuses.append(
                    stage_result.get("status")
                )

        if any(
            status == "error"
            for status in stage_statuses
        ):

            workflow_status = "partial"

        elif all(
            status in (
                "completed",
                "success",
                "created",
                "updated",
                "generated",
                "skipped"
            )
            for status in stage_statuses
        ):

            workflow_status = "completed"

        else:

            workflow_status = "partial"

        return {

            "workflow": workflow_name,

            "results": results,

            "status": workflow_status,

            "context": current_context
        }