# Sprint Roadmap

| Sprint(s) | Area | Why this many |
|---|---|---|
| 10 *(in progress)* | Summarization — backend | Map-reduce pipeline, caching |
| 11 | Summarization — frontend | UI for viewing/generating summaries |
| 12–13 | Cross-channel/cross-file search | Backend (union-of-memberships query, real permission-model extension) + frontend |
| 14 | More file types & richer ingestion (docx, pptx, OCR) | Mostly parser extension work on Sprint 3's existing pipeline |
| 15–16 | Notifications, mentions, threads | A genuinely new feature area (real-time infra + data model) — backend + frontend |
| 17–18 | Integrations (Slack/Notion import) | OAuth flows + import pipelines per integration |
| 19 | Usage analytics per channel | Aggregation queries + a dashboard |
| 20 | Background job infra & advanced ingestion retry | Real job queue (e.g. Celery/RQ) replacing the naive retry from Sprint 3 |
| 21–22 | Production hosting, backups, monitoring, ops | A different skill set entirely (DevOps) — deployment, alerting, admin tooling |
