# archive/md_20261113 — 封存說明

封存日期：2026-11-13（使用者指示：刪除過時、用不到的 .md；為可還原，改為移入此資料夾而非永久刪除）

## 移入的檔案（原位置 → 此處）

- DEBUG_RESEARCH_REPORT.md（2026-11-08 除錯研究報告）
- DEBUG_RESEARCH_VERIFICATION.md（2026-11-09 修正驗證報告）
- OPTIMIZATION_AUDIT.md（2026-11-04 優化審查，snapshot 2026-11-03）
- tradebot0_arena_audit_and_remediation_plan.md（2026-11-04 驗證報告與修復計畫，v2.0.0）
- babeubugging.md（AI agent 除錯 skills 選集清單；skills 已裝在 .agent/skills/，此清單已無用）
- memory/arena_report.md（2026-11-03 Generation 2 戰後報告，$500,000 資本已過時）
- macro_commander_omniroute_workflow_plan.md（2026-11-04 Macro Commander 工作計畫 v2，五階段皆已實作完成）
- omniroute_ai_agent_installation_playbook.md（2026-11-07 OmniRoute 安裝手冊；gateway 已裝好）
- omniroute_deployment_guide.md（2026-11-04 OmniRoute 部署指南；安裝已完成）

## 封存前已做的事

- 2026-11-09 DEBUG 驗證報告的剩餘問題已對照現行程式核對：restore→bootstrap→start、snapshot 歷史、breakeven 計數皆已修；仍有效的三項（世代柵欄缺失、靜默 except 約 40 處、進場動畫 blur 濾鏡）已併入程式審查報告維修清單第 9 項。
- 保留未動：README.md（已重寫）、requirements.txt（已更新）、OptimizationFullGuide.md（設計參考，Phase 3／5／6 尚未照設計實作）、graphify-out/GRAPH_REPORT.md（graphify 生成物）、.agent/ 與 .agents/（skills 與規則）。

## 2026-11-13 程式瘦身（維修清單第 11 項）

上面列出的 9 個舊報告已於 2026-11-13 移除（使用者指示：移除用不到的檔案與之前的除錯報告）。本資料夾只留本 README 作為紀錄。

還原方式：這些檔案的內容仍在 git 歷史裡，HEAD commit 5b6b7d5 的原始位置（專案根目錄、memory/arena_report.md 在 memory/），用 `git show 5b6b7d5:<原路徑>` 可找回。
