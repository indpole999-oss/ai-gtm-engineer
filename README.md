# AI GTM Engineer

> Autonomous AI-powered Go-To-Market Engineer platform that researches companies, finds leads, personalizes outreach, sends emails, updates CRM, and books meetings with minimal human intervention.

---

## Product Definition

**"I am building an autonomous AI GTM Engineer that can research companies, find leads, personalize outreach, send emails, update the CRM, and book meetings with minimal human intervention."**

---

## Tech Stack

| Layer | Technology |
|---|---|
| AI Models | NVIDIA NIM API (nemotron, llama) |
| Backend | Python + FastAPI |
| Frontend | React / Next.js |
| Database | PostgreSQL (Supabase) |
| Vector Memory | pgvector + Pinecone |
| Email | Resend API |
| CRM | HubSpot |
| Calendar | Google Calendar API |
| Enrichment | Apollo.io |
| Search | Serper / Tavily |
| Workflows | n8n |
| Notifications | Slack |
| Containerization | Docker |
| Deployment | Railway / Render |

---

## Agent Architecture

```
User
 └── Frontend Dashboard (React/Next.js)
       └── Backend API (FastAPI)
             └── Manager Agent (NVIDIA NIM)
                   ├── Research Agent (web search only)
                   ├── Browser Agent (Playwright)
                   ├── Enrichment Agent (Apollo API)
                   ├── Email Agent (Resend)
                   ├── CRM Agent (HubSpot)
                   ├── Calendar Agent (Google Calendar)
                   └── Memory Agent (pgvector + Pinecone)
                         └── n8n Workflow Engine
```

---

## Project Structure

```
ai-gtm-engineer/
├── agents/          # All AI specialist agents
├── backend/         # FastAPI server
├── frontend/        # React/Next.js dashboard
├── database/        # SQL schemas and migrations
├── memory/          # Short-term, long-term, vector memory
├── workflows/       # n8n workflow JSON exports
├── prompts/         # Reusable prompt templates
├── config/          # App configuration
├── scripts/         # Setup and utility scripts
├── tests/           # Agent and integration tests
├── docs/            # Architecture documentation
├── logs/            # Application logs
├── uploads/         # File uploads (PDF, CSV)
├── deployment/      # Docker and deployment files
├── .env.example     # All required environment variables
├── requirements.txt # Python dependencies
└── docker-compose.yml
```

---

## Infrastructure Setup Status

- [x] NVIDIA NIM API Key generated
- [x] GitHub repository created with full folder structure
- [x] Supabase database created (8 tables with RLS enabled)
- [x] Resend email API key created
- [ ] n8n workflow engine (requires account setup)
- [ ] Google Calendar OAuth
- [ ] HubSpot CRM sandbox
- [ ] Apollo.io enrichment
- [ ] Pinecone vector store

---

## Database Tables (Supabase)

- `users` - Platform users
- `companies` - Target companies
- `contacts` - Leads and contacts
- `emails` - Email sequences and tracking
- `activities` - CRM activities log
- `workflows` - Automation workflow configs
- `conversations` - AI memory / chat history
- `logs` - System and agent logs

---

## Quick Start

```bash
# Clone the repo
git clone https://github.com/indpole999-oss/ai-gtm-engineer.git
cd ai-gtm-engineer

# Copy environment file
cp .env.example .env
# Fill in your API keys in .env

# Install Python dependencies
pip install -r requirements.txt

# Run with Docker
docker-compose up -d
```

---

## Build Roadmap (100 Steps)

### Phase 1: Foundation (Steps 1-15) DONE
### Phase 2: Core App (Steps 16-33) IN PROGRESS
### Phase 3: Agent Layer (Steps 34-51)
### Phase 4: Intelligence Layer (Steps 52-60)
### Phase 5: Automation Layer (Steps 61-76)
### Phase 6: Business Features (Steps 77-86)
### Phase 7: Production (Steps 87-100)

---

## License

MIT License - see LICENSE file
