const messagesEl = document.querySelector("#messages");
const formEl = document.querySelector("#chatForm");
const inputEl = document.querySelector("#queryInput");
const statusTextEl = document.querySelector("#statusText");
const suggestionButtons = document.querySelectorAll("[data-query]");

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function addMessage(role, html) {
  const article = document.createElement("article");
  article.className = `message ${role}`;
  article.innerHTML = `<div class="bubble">${html}</div>`;
  messagesEl.appendChild(article);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function renderScoreTable(detail) {
  const rows = detail
    .map(
      (item) => `
        <tr>
          <td>${escapeHtml(item.signal)}</td>
          <td>${escapeHtml(item.raw_value)}</td>
          <td>${escapeHtml(item.score)}</td>
          <td>${escapeHtml(item.weight)}</td>
          <td>${escapeHtml(item.contribution)}</td>
          <td>${escapeHtml(item.description)}</td>
        </tr>
      `,
    )
    .join("");

  return `
    <table class="score-table">
      <thead>
        <tr>
          <th>Tín hiệu</th>
          <th>Dữ liệu gốc</th>
          <th>Điểm 0-100</th>
          <th>Trọng số</th>
          <th>Đóng góp</th>
          <th>Ý nghĩa</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
    <p class="formula">Công thức: Click 20% + Like 15% + Tim 20% + Thời lượng xem 25% + Tỷ lệ xem hết 10% + Lưu/Chia sẻ 10%.</p>
  `;
}

function renderResults(answer, results) {
  if (!results.length) {
    addMessage("assistant", `<p class="answer-text">${escapeHtml(answer)}</p>`);
    return;
  }

  const cards = results
    .map((post, index) => {
      const tags = post.tags.map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`).join("");
      return `
        <section class="result-card">
          <h2 class="result-title">${index + 1}. ${escapeHtml(post.title)}</h2>
          <p class="meta">${escapeHtml(post.post_id)} | ${escapeHtml(post.topic)} | Điểm chất lượng: ${escapeHtml(post.quality_score.toFixed(1))}/100</p>
          <p class="summary">${escapeHtml(post.summary)}</p>
          <p class="reason"><strong>Lý do nên đọc:</strong> ${escapeHtml(post.quality_reason)}</p>
          <div class="tags">${tags}</div>
          <a class="source-link" href="${escapeHtml(post.url)}" target="_blank" rel="noreferrer">Mở bài gốc</a>
          <details>
            <summary>Xem chi tiết chấm điểm</summary>
            ${renderScoreTable(post.score_detail)}
          </details>
        </section>
      `;
    })
    .join("");

  addMessage("assistant", `<p class="answer-text">${escapeHtml(answer)}</p>${cards}`);
}

async function submitQuery(query) {
  const cleanQuery = query.trim();
  if (!cleanQuery) return;

  addMessage("user", escapeHtml(cleanQuery));
  inputEl.value = "";
  formEl.querySelector("button").disabled = true;

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: cleanQuery }),
    });
    const data = await response.json();
    renderResults(data.answer, data.results || []);
    await refreshStatus();
  } catch (error) {
    addMessage("assistant", "Không gọi được chatbot. Kiểm tra server FastAPI rồi thử lại.");
  } finally {
    formEl.querySelector("button").disabled = false;
    inputEl.focus();
  }
}

async function refreshStatus() {
  try {
    const response = await fetch("/api/status");
    const data = await response.json();
    const syncText = data.discord_configured ? data.last_sync_message : "Chưa cấu hình Discord bot.";
    statusTextEl.textContent = `${data.post_count} bài trong dữ liệu | ${syncText}`;
  } catch {
    statusTextEl.textContent = "Không đọc được trạng thái dữ liệu.";
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

refreshStatus();
setInterval(refreshStatus, 30000);
