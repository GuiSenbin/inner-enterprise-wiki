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
  activeQuestion: $("#activeQuestion"),
  warningList: $("#warningList"),
  confidenceLabel: $("#confidenceLabel"),
  confidenceBar: $("#confidenceBar"),
  confidenceScore: $("#confidenceScore"),
  usedModel: $("#usedModel"),
  intentType: $("#intentType"),
  retrievalStrategy: $("#retrievalStrategy"),
  rerankExplanation: $("#rerankExplanation"),
  matchedNodes: $("#matchedNodes"),
  relatedDocs: $("#relatedDocs"),
  promptToggle: $("#promptToggle"),
  promptView: $("#promptView"),
  evidenceList: $("#evidenceList"),
  toast: $("#toast"),
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

function renderList(values) {
  if (!values || values.length === 0) return "无";
  return values.map((item) => `<span>${escapeHtml(item)}</span>`).join("、");
}

function categoryLabel(category) {
  if (category === "raw") return "原始文档";
  if (category === "concept") return "概念词条";
  return "实体词条";
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
      if (item.keyword_hit) recallLabels.push("BM25关键词");
      if (item.graph_hit) recallLabels.push("图谱命中");
      const recallText = recallLabels.length ? recallLabels.join(" / ") : "召回候选";
      return `
        <article class="evidence-item">
          <div class="rail-mark">
            <span class="rank">${String(index + 1).padStart(2, "0")}</span>
            <span class="badge ${escapeHtml(category)}">${categoryLabel(category)}</span>
          </div>
          <div class="evidence-body">
            <h3>${escapeHtml(chunk.doc_name || "未知来源")}</h3>
            <div class="score-row">
              <span>${recallText}</span>
              <span>综合分 ${Number(item.score || 0).toFixed(3)}</span>
              <span>语义分 ${Number(item.vector_score || 0).toFixed(3)}</span>
              <span>关键词分 ${Number(item.keyword_score || 0).toFixed(3)}</span>
            </div>
            <div class="evidence-text">${escapeHtml(chunk.text || "")}</div>
            <div class="score-row">
              <span>双链：${chunk.mentions && chunk.mentions.length ? escapeHtml(chunk.mentions.join("、")) : "无"}</span>
              <span>排序依据：${item.rerank_reasons && item.rerank_reasons.length ? escapeHtml(item.rerank_reasons.join("；")) : "语义召回"}</span>
            </div>
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
  els.activeQuestion.textContent = payload.query || "未返回问题";
  els.answer.textContent = payload.answer || "没有生成回答。";
  els.usedModel.textContent = payload.used_model ? `模型：${payload.used_model}` : "模型未返回";
  els.intentType.textContent = payload.intent_type || "未识别";
  els.retrievalStrategy.textContent = payload.retrieval_strategy || "未返回";
  els.rerankExplanation.innerHTML = renderList(payload.rerank_explanation);
  els.matchedNodes.innerHTML = renderList(payload.matched_nodes);
  els.relatedDocs.innerHTML = renderList(payload.related_docs);
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
    els.warningList.classList.add("has-warning");
    els.warningList.innerHTML = `<span>运行提示</span><strong>${escapeHtml(warnings.join(" "))}</strong>`;
    showToast(warnings.join(" "), payload.llm_failed);
  } else {
    els.warningList.classList.remove("has-warning");
    els.warningList.innerHTML = "<span>运行提示</span><strong>暂无异常提示</strong>";
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

loadConfig();
loadStatus();
