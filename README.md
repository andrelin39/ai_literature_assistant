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
