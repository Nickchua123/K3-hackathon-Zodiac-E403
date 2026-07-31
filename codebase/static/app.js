const messagesEl = document.querySelector("#messages");
const formEl = document.querySelector("#chatForm");
const inputEl = document.querySelector("#queryInput");
const submitButtonEl = document.querySelector("#submitButton");
const statusCardEl = document.querySelector("#statusCard");
const statusTextEl = document.querySelector("#statusText");
const topPostsListEl = document.querySelector("#topPostsList");
const hotTopicsEl = document.querySelector("#hotTopics");
const refreshOverviewEl = document.querySelector("#refreshOverview");
const suggestionButtons = document.querySelectorAll("[data-query]");

let isSubmitting = false;
let starterConversationRendered = false;

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function safeExternalUrl(value) {
  try {
    const parsedUrl = new URL(String(value ?? ""), window.location.origin);
    return ["http:", "https:"].includes(parsedUrl.protocol) ? parsedUrl.href : "#";
  } catch {
    return "#";
  }
}

function scoreText(value) {
  const score = Number(value);
  return Number.isFinite(score) ? score.toFixed(1) : "N/A";
}

function addMessage(role, html, variant = "") {
  const article = document.createElement("article");
  article.className = ["message", role, variant].filter(Boolean).join(" ");
  if (variant === "error") {
    article.setAttribute("role", "alert");
  }

  const isUser = role === "user";
  const avatarClass = isUser ? "user-avatar" : "ai-avatar";
  const avatarText = isUser ? "B" : "✦";
  const label = isUser ? "Bạn" : "Quality AI";
  article.innerHTML = `
    <div class="avatar ${avatarClass}" aria-hidden="true">${avatarText}</div>
    <div class="message-content">
      <div class="message-label">${label}</div>
      <div class="bubble">${html}</div>
    </div>
  `;
  messagesEl.appendChild(article);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return article;
}

function addLoadingMessage() {
  return addMessage(
    "assistant",
    `
      <div class="typing-indicator" role="status" aria-label="Đang tìm bài viết">
        <span></span><span></span><span></span>
        <span class="typing-label">Đang đọc, tóm tắt và xếp hạng...</span>
      </div>
    `,
    "loading",
  );
}

function setBusy(busy) {
  isSubmitting = busy;
  messagesEl.setAttribute("aria-busy", String(busy));
  inputEl.disabled = busy;
  submitButtonEl.disabled = busy;
  suggestionButtons.forEach((button) => {
    button.disabled = busy;
  });
  document.querySelectorAll(".topic-button").forEach((button) => {
    button.disabled = busy;
  });
}

function setStatus(text, state = "ready") {
  statusTextEl.textContent = text;
  statusCardEl.dataset.state = state;
}

function renderScoreTable(detail) {
  const safeDetail = Array.isArray(detail) ? detail : [];
  const rows = safeDetail
    .map(
      (item) => `
        <tr>
          <td>${escapeHtml(item.signal)}</td>
          <td>${escapeHtml(item.raw_value)}</td>
          <td>${escapeHtml(item.score)}</td>
          <td>${escapeHtml(item.weight)}</td>
          <td>${escapeHtml(item.contribution)}</td>
        </tr>
      `,
    )
    .join("");

  return `
    <div class="score-table-wrap">
      <table class="score-table">
        <thead>
          <tr>
            <th>Tín hiệu</th>
            <th>Dữ liệu gốc</th>
            <th>Điểm</th>
            <th>Trọng số</th>
            <th>Đóng góp</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
    <p class="formula">Điểm tổng hợp từ click, like, tim, thời lượng xem, tỷ lệ xem hết và lưu/chia sẻ.</p>
  `;
}

function renderChatPost(post, index, mode = "search") {
  const tags = (Array.isArray(post.tags) ? post.tags : [])
    .slice(0, 4)
    .map((tag) => `<span class="tag">#${escapeHtml(tag)}</span>`)
    .join("");
  const sourceUrl = safeExternalUrl(post.url);
  const fallbackRankLabel =
    mode === "quality_lowest" || mode === "ranking_quality_lowest"
      ? "Điểm chất lượng thấp nhất"
      : mode === "quality_highest" || mode === "ranking_quality_highest"
        ? "Điểm chất lượng cao nhất"
        : `Recommended ${String(index + 1).padStart(2, "0")}`;
  const rankLabel =
    typeof post.ranking_label === "string" && post.ranking_label
      ? post.ranking_label
      : fallbackRankLabel;
  const rankingValue =
    typeof post.ranking_value_display === "string" && post.ranking_metric !== "quality"
      ? `<span class="ranking-value">${escapeHtml(post.ranking_value_display)}</span>`
      : "";
  return `
    <article class="result-card">
      <div class="result-card-top">
        <div>
          <div class="result-rank">${escapeHtml(rankLabel)}${rankingValue}</div>
          <h2 class="result-title">${escapeHtml(post.title)}</h2>
        </div>
        <span class="quality-badge" title="Điểm chất lượng">
          <span class="star" aria-hidden="true">★</span>
          ${escapeHtml(scoreText(post.quality_score))}/100
        </span>
      </div>
      <p class="result-summary">${escapeHtml(post.summary)}</p>
      <div class="result-footer">
        <div class="tags">${tags}</div>
        <a
          class="source-link"
          href="${escapeHtml(sourceUrl)}"
          target="_blank"
          rel="noopener noreferrer"
        >
          Mở trên Discord
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M14 5h5v5M13 11l6-6M19 14v5H5V5h5" />
          </svg>
        </a>
      </div>
      <details>
        <summary>Xem cách tính điểm</summary>
        ${renderScoreTable(post.score_detail)}
      </details>
    </article>
  `;
}

function renderResults(answer, results, mode = "search") {
  if (!results.length) {
    addMessage("assistant", `<p>${escapeHtml(answer)}</p>`);
    return;
  }

  const cards = results.map((post, index) => renderChatPost(post, index, mode)).join("");
  addMessage(
    "assistant",
    `
      <p class="assistant-answer">${escapeHtml(answer)}</p>
      <div class="chat-results">${cards}</div>
    `,
    "result-message",
  );
}

async function readJsonResponse(response) {
  const responseText = await response.text();
  let data = {};

  if (responseText) {
    try {
      data = JSON.parse(responseText);
    } catch {
      throw new Error("Máy chủ trả về dữ liệu không hợp lệ.");
    }
  }

  if (!response.ok) {
    const detail =
      typeof data.detail === "string"
        ? data.detail
        : `Máy chủ báo lỗi HTTP ${response.status}.`;
    throw new Error(detail);
  }

  return data;
}

async function submitQuery(query, options = {}) {
  const cleanQuery = String(query ?? "").trim();
  if (!cleanQuery || isSubmitting) return;

  setBusy(true);
  addMessage("user", `<p>${escapeHtml(cleanQuery)}</p>`);
  inputEl.value = "";
  const loadingMessage = addLoadingMessage();
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), 45000);

  const requestBody = { query: cleanQuery };
  if (options.topic) {
    requestBody.topic = String(options.topic);
  }
  if (Number.isFinite(options.topK)) {
    requestBody.top_k = Math.min(10, Math.max(1, Math.trunc(options.topK)));
  }

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody),
      signal: controller.signal,
    });
    const data = await readJsonResponse(response);
    loadingMessage.remove();
    renderResults(
      String(data.answer ?? ""),
      Array.isArray(data.results) ? data.results : [],
      String(data.mode ?? "search"),
    );
    await refreshStatus();
  } catch (error) {
    loadingMessage.remove();
    const message =
      error?.name === "AbortError"
        ? "Yêu cầu mất quá nhiều thời gian. Hãy thử lại với một chủ đề ngắn hơn."
        : `Không thể hoàn tất tìm kiếm: ${error?.message || "lỗi không xác định"}`;
    addMessage("assistant", `<p>${escapeHtml(message)}</p>`, "error");
  } finally {
    window.clearTimeout(timeoutId);
    setBusy(false);
    inputEl.focus();
  }
}

function renderOverviewPosts(posts) {
  if (!posts.length) {
    topPostsListEl.innerHTML =
      '<p class="empty-overview">Chưa có bài viết phù hợp để hiển thị.</p>';
    return;
  }

  topPostsListEl.innerHTML = posts
    .map((post, index) => {
      const sourceUrl = safeExternalUrl(post.url);
      return `
        <a
          class="overview-post"
          href="${escapeHtml(sourceUrl)}"
          target="_blank"
          rel="noopener noreferrer"
          title="${escapeHtml(post.title)}"
        >
          <span class="overview-rank">${String(index + 1).padStart(2, "0")}</span>
          <span class="overview-post-copy">
            <strong>${escapeHtml(post.title)}</strong>
            <span>${escapeHtml(post.topic)} · ${escapeHtml(post.author)}</span>
          </span>
          <span class="overview-score"><b>★</b> ${escapeHtml(scoreText(post.quality_score))}</span>
        </a>
      `;
    })
    .join("");
}

function renderHotTopics(topics) {
  if (!topics.length) {
    hotTopicsEl.innerHTML = '<span class="topic-placeholder">Chưa có chủ đề nổi bật.</span>';
    return;
  }

  hotTopicsEl.innerHTML = topics
    .map(
      (topic) => `
        <button
          class="topic-button"
          type="button"
          data-topic="${escapeHtml(topic.name)}"
          data-topic-count="${escapeHtml(topic.count)}"
        >
          #${escapeHtml(topic.name)}
          <strong>${escapeHtml(topic.count)}</strong>
        </button>
      `,
    )
    .join("");
}

function renderStarterConversation(posts) {
  if (starterConversationRendered || !posts.length) return;
  starterConversationRendered = true;
  addMessage("user", "<p>Có bài kỹ thuật nào nổi bật tuần này?</p>");
  renderResults(
    "Mình đã chọn các bài có điểm chất lượng cao và vẫn giữ link nguồn để bạn kiểm chứng.",
    posts.slice(0, 2),
  );
}

async function loadOverview(showLoading = true) {
  if (showLoading) {
    refreshOverviewEl.dataset.loading = "true";
    topPostsListEl.innerHTML =
      '<div class="skeleton-row"></div><div class="skeleton-row"></div><div class="skeleton-row"></div>';
  }

  try {
    const response = await fetch("/api/overview");
    const data = await readJsonResponse(response);
    const posts = Array.isArray(data.top_posts) ? data.top_posts : [];
    const topics = Array.isArray(data.hot_topics) ? data.hot_topics : [];
    renderOverviewPosts(posts);
    renderHotTopics(topics);
    renderStarterConversation(posts);
  } catch {
    topPostsListEl.innerHTML =
      '<p class="empty-overview">Không tải được bài nổi bật. Hãy thử làm mới.</p>';
    hotTopicsEl.innerHTML =
      '<span class="topic-placeholder">Không tải được chủ đề.</span>';
  } finally {
    refreshOverviewEl.dataset.loading = "false";
  }
}

async function refreshStatus(showLoading = false) {
  if (showLoading) {
    setStatus("Đang kết nối kho tri thức...", "loading");
  }

  try {
    const response = await fetch("/api/status");
    const data = await readJsonResponse(response);
    const storageText = data.storage === "sqlite" ? "SQLite" : "Dữ liệu local";
    const embeddingText = Number.isFinite(Number(data.embedding_count))
      ? `${data.embedding_count} vectors`
      : "Hybrid search";
    setStatus(`${data.post_count} bài · ${storageText} · ${embeddingText}`, "ready");
  } catch {
    setStatus("Không đọc được trạng thái dữ liệu", "error");
  }
}

formEl.addEventListener("submit", (event) => {
  event.preventDefault();
  submitQuery(inputEl.value);
});

suggestionButtons.forEach((button) => {
  button.addEventListener("click", () => {
    submitQuery(button.dataset.query || "");
  });
});

hotTopicsEl.addEventListener("click", (event) => {
  const button = event.target.closest("[data-topic]");
  if (!button) return;
  const topic = button.dataset.topic || "";
  const topicCount = Number(button.dataset.topicCount);
  submitQuery(`Tìm bài chất lượng về ${topic}`, {
    topic,
    topK: Number.isFinite(topicCount) ? topicCount : 3,
  });
});

refreshOverviewEl.addEventListener("click", async () => {
  await Promise.all([loadOverview(true), refreshStatus(true)]);
});

Promise.all([refreshStatus(true), loadOverview(true)]);
window.setInterval(() => refreshStatus(), 30000);
