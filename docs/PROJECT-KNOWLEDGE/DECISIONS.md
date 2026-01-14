# Technical Decisions Log

## 2026-01-14: Version Control Platform
**Decision**: GitHub (cloud-hosted)
**Reasoning**: Free private repos, built-in Projects feature, industry standard, automatic backups
**Alternatives Considered**: Self-hosted GitLab
**Consequences**: Code lives on GitHub's servers, one less thing to maintain

## 2026-01-14: Project Organization
**Decision**: Use living documentation in PROJECT-KNOWLEDGE directory
**Reasoning**: Maintain context across multiple conversations, avoid token limits
**Alternatives Considered**: Keep everything in chat history
**Consequences**: 15 min overhead per sprint to update docs, but saves hours of re-explaining

## 2026-01-14: Development Approach
**Decision**: Start with Statement Generator proof of concept
**Reasoning**: Low risk, immediate value, proves we can build business software
**Alternatives Considered**: Jump straight to full FSM system
**Consequences**: 6 weeks before first production feature, but validates approach

## Technical Stack Decisions (Tentative - to be finalized)

### Backend
**Decision**: Python + FastAPI
**Reasoning**: Chris comfortable with Python, FastAPI is modern and fast
**Status**: To be confirmed in Sprint 0.1

### Database  
**Decision**: PostgreSQL
**Reasoning**: Mature, excellent JSON support, handles complex queries well
**Status**: To be confirmed in Sprint 0.1

### Frontend
**Decision**: React + Tailwind CSS + Shadcn/ui
**Reasoning**: Modern, professional UI components, good developer experience
**Status**: To be confirmed in Sprint 0.3

### PDF Generation
**Decision**: TBD (ReportLab or WeasyPrint)
**Reasoning**: Need to evaluate during Sprint 0.2
**Status**: Research needed
