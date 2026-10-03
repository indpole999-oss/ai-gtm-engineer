"""HTTP routers are imported explicitly by the application.

Avoid eager imports here: standalone workers use authentication dependencies
through tenancy without initializing every HTTP router.
"""
