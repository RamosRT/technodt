---
name: technokonvert-design
description: Use this skill to generate well-branded interfaces and assets for ТехноКонверт (Konvert-Trek) — an internal accounting-document envelope-tracking system in the Технониколь / Техноавиа brand lineage. Covers an Android handheld TSD app and a PC web operator app. Contains essential design guidelines, colors, type, fonts, assets, and UI kit components for prototyping.
user-invocable: true
---

Read the README.md file within this skill, and explore the other available files.

If creating visual artifacts (slides, mocks, throwaway prototypes, etc), copy assets out and create static HTML files for the user to view. Always include `colors_and_type.css` and pull components from `ui_kits/tsd_android/`. If working on production code, you can copy assets and read the rules here to become an expert in designing with this brand.

If the user invokes this skill without any other guidance, ask them what they want to build or design — TSD screen? web operator surface? print/ZPL label? — ask some questions, and act as an expert designer who outputs HTML artifacts _or_ production code, depending on the need.

Key constraints to respect:
- All UI strings are Russian (ru-RU). No emoji. No exclamation points.
- Roboto + Roboto Condensed only. Never use 90° gradients.
- Lucide icons (CDN) — never substitute emoji or hand-rolled SVG.
- TSD CTAs are bottom-anchored, 56px tall, full-width.
- Status vocabulary: Черновик / Запечатан / Сверен / С расхождением.
