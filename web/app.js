/*
定位：前端展示层。
职责：处理页面交互，调用查询 API，并渲染答案、Prompt 和检索证据。
依赖：/api/status、/api/answer、/api/rebuild 和页面 DOM。
*/

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

const els = {
  statusPulse: $("#statusPulse"),
  statusText: $("#statusText"),
  chunkCount: $("#chunkCount"),
  nodeCount: $("#nodeCount"),
  graphEdgeCount: $("#graphEdgeCount"),
  compiledAt: $("#compiledAt"),
  rebuildBtn: $("#rebuildBtn"),
  form: $("#questionForm"),
  query: $("#query"),
  askBtn: $("#askBtn"),
  model: $("#model"),
  answer: $("#answer"),
  confidenceLabel: $("#confidenceLabel"),
  confidenceBar: $("#confidenceBar"),
  confidenceScore: $("#confidenceScore"),
  usedModel: $("#usedModel"),
  intentType: $("#intentType"),
  retrievalStrategy: $("#retrievalStrategy"),
  resultSummary: $("#resultSummary"),
  matchedNodes: $("#matchedNodes"),
  relatedDocs: $("#relatedDocs"),
  promptToggle: $("#promptToggle"),
  promptView: $("#promptView"),
  evidenceList: $("#evidenceList"),
  toast: $("#toast"),
};

const intentLabels = {
  source_lookup: "原文定位",
  entity_profile: "实体画像",
  concept_summary: "概念归纳",
  comparison: "对比综合",
  project_fact: "项目事实",
  general: "普通问答",
};

const strategyLabels = {
  vector_first_source_lookup: "向量优先 · 原文定位",
  entity_graph_first: "实体图谱优先",
  concept_graph_first: "概念图谱优先",
  multi_node_hybrid: "多节点混合检索",
  hybrid_with_doc_type_boost: "混合检索 · 文档类型增强",
  vector_with_graph_supplement: "向量检索 · 图谱补充",
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function showToast(message, isError = false) {
  els.toast.textContent = message;
  els.toast.classList.toggle("error", isError);
  els.toast.hidden = false;
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    els.toast.hidden = true;
  }, 3600);
}

async function requestJson(url, options = {}) {
  // 统一处理 API 请求和错误透传，避免每个交互入口重复写 fetch 分支。
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "请求失败。");
  }
  return payload;
}

function renderConfig(payload) {
  // 模型选项来自后端白名单，避免页面和服务端配置各维护一份。
  const defaultModel = payload.default_model || "";
  els.model.innerHTML = (payload.models || [])
    .map((model) => {
      const selected = model === defaultModel ? " selected" : "";
      return `<option value="${escapeHtml(model)}"${selected}>${escapeHtml(model)}</option>`;
    })
    .join("");
}

function renderStatus(payload) {
  els.statusPulse.classList.toggle("ready", payload.index_loaded);
  els.statusText.textContent = payload.index_loaded ? "索引已加载" : "索引未构建";
  els.chunkCount.textContent = payload.chunk_count ?? 0;
  els.nodeCount.textContent = payload.node_count ?? 0;
  els.graphEdgeCount.textContent = payload.graph_edge_count ?? 0;
  els.compiledAt.textContent = payload.compiled_at ? payload.compiled_at.slice(0, 10) : "--";
}

function clearQuestionInput() {
  // 页面刷新或从浏览器缓存返回时，不保留上一次问题，避免误提交旧问题。
  els.query.value = "";
}

async function loadConfig() {
  try {
    renderConfig(await requestJson("/api/config"));
  } catch (error) {
    showToast(error.message, true);
  }
}

async function loadStatus() {
  try {
    renderStatus(await requestJson("/api/status"));
  } catch (error) {
    els.statusText.textContent = "状态读取失败";
    showToast(error.message, true);
  }
}

function renderList(values, className = "") {
  if (!values || values.length === 0) return "无";
  const classAttribute = className ? ` class="${className}"` : "";
  return values.map((item) => `<span${classAttribute}>${escapeHtml(item)}</span>`).join("");
}

function asList(values) {
  if (Array.isArray(values)) return values.filter(Boolean);
  if (values === null || values === undefined || values === "") return [];
  return [values];
}

function renderCollapsibleList(values, className = "metadata-tag", limit = 3) {
  const items = asList(values);
  if (items.length === 0) return "无";
  const visible = items.slice(0, limit);
  const hidden = items.slice(limit);
  const summary = visible.map((item) => `<span class="${className}">${escapeHtml(item)}</span>`).join("");
  if (hidden.length === 0) return `<div class="metadata-tags">${summary}</div>`;
  const details = hidden.map((item) => `<span class="${className}">${escapeHtml(item)}</span>`).join("");
  return `<div class="metadata-detail"><div class="metadata-tags">${summary}</div><details><summary>查看其余 ${hidden.length} 项</summary><div class="metadata-tags">${details}</div></details></div>`;
}

function renderRetrievalMethods(labels) {
  if (!labels || labels.length === 0) return '<span class="retrieval-badge neutral">召回候选</span>';
  return labels.map((label) => `<span class="retrieval-badge">${escapeHtml(label)}</span>`).join("");
}

function categoryLabel(category) {
  if (category === "raw") return "原始文档";
  if (category === "concept") return "概念词条";
  return "实体词条";
}

function renderInlineMarkdown(value) {
  return escapeHtml(value)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`(.+?)`/g, "<code>$1</code>");
}

function renderAnswerMarkdown(markdown) {
  const lines = String(markdown || "")
    .replace(/\*\*答案依据：\*\*/g, "## 证据依据")
    .replace(/\*\*答案：\*\*/g, "## 结论")
    .split(/\r?\n/);
  const html = [];
  let inList = false;
  const closeList = () => {
    if (inList) {
      html.push("</ul>");
      inList = false;
    }
  };

  lines.forEach((line) => {
    const trimmed = line.trim();
    if (!trimmed) {
      closeList();
      return;
    }
    if (/^---+$/.test(trimmed)) {
      closeList();
      html.push("<hr>");
      return;
    }
    const heading = trimmed.match(/^#{1,3}\s+(.+)$/);
    if (heading) {
      closeList();
      html.push(`<h3>${renderInlineMarkdown(heading[1])}</h3>`);
      return;
    }
    const bullet = trimmed.match(/^[-*]\s+(.+)$/);
    if (bullet) {
      if (!inList) {
        html.push("<ul>");
        inList = true;
      }
      html.push(`<li>${renderInlineMarkdown(bullet[1])}</li>`);
      return;
    }
    closeList();
    html.push(`<p>${renderInlineMarkdown(trimmed)}</p>`);
  });
  closeList();
  return html.join("") || "<p>没有生成回答。</p>";
}

function renderEvidence(items) {
  // 证据链渲染必须保留来源、召回依据和分数，不能只展示大模型答案。
  if (!items || items.length === 0) {
    els.evidenceList.innerHTML = '<div class="empty-state">没有检索到切片。可以换一个更具体的问题。</div>';
    return;
  }

  els.evidenceList.innerHTML = items
    .map((item, index) => {
      const chunk = item.chunk || {};
      const category = chunk.category || "entity";
      const recallLabels = [];
      if (item.vector_score > 0) recallLabels.push("语义召回");
      if (item.keyword_hit) recallLabels.push("BM25 关键词");
      if (item.graph_hit) recallLabels.push("图谱命中");
      if (item.direct_match_score > 0.7) recallLabels.unshift("直接事实命中");
      return `
        <article class="evidence-item">
          <div class="rail-mark">
            <span class="rank">${String(index + 1).padStart(2, "0")}</span>
            <span class="badge ${escapeHtml(category)}">${categoryLabel(category)}</span>
          </div>
          <div class="evidence-body">
            <h3>${escapeHtml(chunk.doc_name || "未知来源")}</h3>
            <div class="score-row">
              <div class="retrieval-methods">${renderRetrievalMethods(recallLabels)}</div>
              <span>综合分 ${Number(item.score || 0).toFixed(3)}</span>
              <span>语义分 ${Number(item.vector_score || 0).toFixed(3)}</span>
              <span>关键词分 ${Number(item.keyword_score || 0).toFixed(3)}</span>
            </div>
            <details class="evidence-details" open>
              <summary>查看证据详情</summary>
              <div class="evidence-text">${escapeHtml(chunk.text || "")}</div>
              <div class="detail-row"><span>双链</span><strong>${chunk.mentions && chunk.mentions.length ? escapeHtml(chunk.mentions.join("、")) : "无"}</strong></div>
              <div class="detail-row"><span>排序依据</span><strong>${item.rerank_reasons && item.rerank_reasons.length ? escapeHtml(item.rerank_reasons.join("；")) : "语义召回"}</strong></div>
            </details>
          </div>
        </article>
      `;
    })
    .join("");
}

function renderConfidence(score, label) {
  const normalized = Math.max(0, Math.min(1, Number(score || 0)));
  els.confidenceLabel.textContent = label || "未返回";
  els.confidenceScore.textContent = `分数 ${normalized.toFixed(3)}`;
  els.confidenceBar.style.width = `${normalized * 100}%`;
  els.confidenceBar.dataset.level = normalized >= 0.75 ? "high" : normalized >= 0.35 ? "medium" : "low";
}

function renderAnswer(payload) {
  // 后端返回的是完整问答结果，这里只负责把答案和证据同步到页面。
  els.answer.classList.remove("empty");
  els.answer.innerHTML = renderAnswerMarkdown(payload.answer);
  els.usedModel.textContent = payload.used_model ? `模型：${payload.used_model}` : "模型未返回";
  els.intentType.textContent = intentLabels[payload.intent_type] || payload.intent_type || "未识别";
  els.retrievalStrategy.textContent = strategyLabels[payload.retrieval_strategy] || payload.retrieval_strategy || "未返回";
  if (payload.result_mode === "entity_full" || payload.result_mode === "project_full") {
    const count = Number(payload.total_related_projects || 0);
    els.resultSummary.textContent = count ? `共找到 ${count} 个项目` : "全量关联项目";
  } else {
    els.resultSummary.textContent = `展示 ${Number(payload.evidence_limit || 5)} 条证据`;
  }
  els.matchedNodes.innerHTML = renderCollapsibleList(payload.keywords || payload.matched_nodes);
  els.relatedDocs.innerHTML = renderCollapsibleList(payload.related_docs, "metadata-tag document-tag");
  els.promptView.textContent = payload.prompt || "";
  renderConfidence(payload.confidence_score, payload.confidence_label);
  renderEvidence(payload.retrieved_results);

  const warnings = [];
  if (payload.embedding_failed) {
    warnings.push("向量服务不可用，已使用 BM25 关键词和图谱关系继续检索。");
  }
  if (payload.llm_failed) {
    warnings.push("模型生成失败，页面保留检索证据和 Prompt。");
  }
  if (payload.evidence_status && payload.evidence_status !== "ok") {
    warnings.push(`证据状态：${payload.evidence_status}`);
  }
  if (warnings.length > 0) {
    showToast(warnings.join(" "), payload.llm_failed);
  }
}

async function answerQuestion(query) {
  // 问答请求期间锁定按钮，避免用户连续提交造成状态交叉。
  els.askBtn.disabled = true;
  els.askBtn.textContent = "编译证据中";
  try {
    const payload = await requestJson("/api/answer", {
      method: "POST",
      body: JSON.stringify({ query, model: els.model.value }),
    });
    renderAnswer(payload);
  } catch (error) {
    showToast(error.message, true);
  } finally {
    els.askBtn.disabled = false;
    els.askBtn.textContent = "基于 Wiki 证据回答";
  }
}

els.form.addEventListener("submit", (event) => {
  event.preventDefault();
  const query = els.query.value.trim();
  if (!query) {
    showToast("请输入问题后再检索。", true);
    return;
  }
  answerQuestion(query);
});

els.rebuildBtn.addEventListener("click", async () => {
  els.rebuildBtn.disabled = true;
  els.rebuildBtn.textContent = "正在编译";
  try {
    const payload = await requestJson("/api/rebuild", { method: "POST", body: "{}" });
    renderStatus(payload);
    showToast("知识编译成功。");
  } catch (error) {
    showToast(error.message, true);
  } finally {
    els.rebuildBtn.disabled = false;
    els.rebuildBtn.textContent = "重新编译知识";
  }
});

els.promptToggle.addEventListener("click", () => {
  const nextHidden = !els.promptView.hidden;
  els.promptView.hidden = nextHidden;
  els.promptToggle.textContent = nextHidden ? "查看 Prompt" : "收起 Prompt";
});

$$(".prompt-chip").forEach((button) => {
  button.addEventListener("click", () => {
    els.query.value = (button.dataset.query || button.textContent).trim();
    els.query.focus();
  });
});

clearQuestionInput();
window.addEventListener("pageshow", clearQuestionInput);
loadConfig();
loadStatus();
