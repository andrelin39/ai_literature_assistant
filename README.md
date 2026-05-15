# AI 文獻助理 (ai-literature-assistant)

協助學術研究者進行系統性文獻回顧的 AI 工具，整合多個學術資料庫與 Claude AI 分析能力。

## 功能

- **多資料庫搜尋**：Semantic Scholar、PubMed、Crossref、OpenAlex
- **文獻庫管理**：收藏、標記、篩選文獻，本地 SQLite 儲存
- **AI 輔助評估**：透過 Claude 評估文獻相關性、摘要重點
- **匯出報告**：PRISMA 流程、BibTeX、CSV 格式匯出

## 安裝

```bash
# 安裝依賴
uv sync

# 複製環境變數範本
cp .env.example .env
# 編輯 .env，填入 API keys
```

## 執行

```bash
streamlit run app.py
```

## 所需 API Keys

| Key | 必要性 | 取得方式 |
|-----|--------|----------|
| `ANTHROPIC_API_KEY` | 必要 | [console.anthropic.com](https://console.anthropic.com) |
| `SEMANTIC_SCHOLAR_API_KEY` | 建議 | [api.semanticscholar.org](https://api.semanticscholar.org) |
| `CONTACT_EMAIL` | 建議 | 自填，用於 Crossref/OpenAlex polite pool |

> Semantic Scholar 免費方案有速率限制，建議申請 API key 以提高配額。

## Phase 1 實作狀態

### 已完成 ✅
- Semantic Scholar 分層搜尋策略（relevance / recent / highly_cited / review）
- Claude 深度分析，grounded 事實與 inferred 推論分離
- 跨文獻比較（共通主題、對立觀點、研究缺口、綜述建議）
- 專案管理（CRUD、多專案切換）
- 文獻庫管理（篩選、標籤、備註、狀態管理）
- Streamlit 端到端 UI 整合

### Phase 2/3 計畫實作 ❌
- Crossref / OpenAlex 整合
- 使用者上傳段落評估引用適切性
- 引用網絡探索（references / citations）
- BibTeX / RIS 匯出
- Zotero 整合
- DOI 驗證（透過 Crossref 反查）
- 多輪對話追問

## 手動測試清單（Smoke Test）

1. 啟動 app：`streamlit run app.py`，確認首頁正常載入
2. 至「📋 專案管理」，建立第一個專案（名稱必填）
3. 確認左側專案選擇器自動切換到新專案
4. 至「🔍 搜尋文獻」，輸入 `nursing burnout COVID-19`，點「🔍 搜尋」
5. 確認顯示 5 篇結果，其中有 abstract 的篇目 checkbox 可勾選
6. 勾選至少 2 篇有 abstract 的文獻，確認出現「⚡ 分析」按鈕
7. 點「分析」，確認 progress bar 依序更新，完成後顯示跨文獻比較與個別分析卡片
8. 對 1 篇點「✅ 確認加入專案」，確認按鈕變為「✅ 已加入專案」
9. 切換至「📚 文獻庫管理」，確認剛才加入的文獻出現
10. 展開該文獻的「✏️ 編輯」，修改 user_notes 並「💾 儲存變更」
11. 重新整理頁面（F5），確認備註仍存在於文獻庫
