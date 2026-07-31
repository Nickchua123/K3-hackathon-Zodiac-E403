# AI SPEC - Discord Quality Digest - Nhóm 03

Hướng: [x] B - Trợ lý Học viên (Discord)  [ ] A - VLearn  [ ] C - Làn mở
Loại: [ ] Tối ưu tính năng có sẵn  [x] Tính năng mới

## §1. User & Job

- Job executor + workflow: học viên khóa AI Thực Chiến đang tìm lại bài chia sẻ hữu ích trong Discord. Workflow hiện tại: nhớ lờ mờ chủ đề -> tìm trong Discord bằng keyword hoặc lướt channel/forum -> mở nhiều bài -> tự đánh giá bài nào đáng đọc.
- Core JTBD: Khi cần học lại hoặc xử lý một vấn đề kỹ thuật/sản phẩm, học viên muốn tìm nhanh các bài chia sẻ đáng tin trong Discord để tiết kiệm thời gian và tránh đọc nhầm bài kém liên quan.
- Problem statement: Học viên khó tìm lại bài Discord chất lượng vì bài viết phân tán, tiêu đề không đồng nhất, tìm kiếm theo keyword dễ bỏ sót, và tín hiệu like đơn lẻ không đủ phản ánh giá trị thật của bài.
- Evidence hiện có trong repo:
  - Dữ liệu mock: `codebase/mock_posts.csv` có 12 bài viết mẫu phủ các chủ đề RAG, Prompt Engineering, Evaluation, Product, UX, Search, Frontend.
  - Dữ liệu Discord thật đã sync local: `codebase/discord_posts.csv` hiện có 11 record từ Discord thật; khi chạy app các record được upsert vào SQLite.
  - Tín hiệu thực tế từ Discord chủ yếu gồm nội dung, author, reaction và link gốc. Các trường click/watch-time/completion/save-share trong prototype là proxy/ước tính để demo scoring.
  - Lưu ý cần bổ sung trước khi nộp chính thức: log khảo sát hoặc mining chuẩn A/B theo rubric. Hiện repo chưa có `validation/` hoặc log khảo sát 20 người.
- Ví dụ bài hiện có:
  - `P001` - Checklist prompt RAG trước khi nộp bài.
  - `P005` - Promptfoo golden set cho AI tutor.
  - `P009` - Thiết kế UX khi AI không chắc.
  - `DISC-1532320250299940986` - Công thức tính điểm chất lượng cho bài đăng chuyên môn.
  - `DISC-1532320380281425971` - Cách viết script tự động cào dữ liệu Discord Server.

## §2. Impact & Quyết Định Chọn

| Ứng viên | Người gặp | Tần suất | Tốn gì mỗi lần | Khả thi trong hackathon | Quyết định |
|---|---:|---|---|---|---|
| Tìm bài Discord chất lượng theo chủ đề | Nhiều học viên dùng Discord để học/tra cứu | Khi ôn bài, làm demo, debug | 5-15 phút lướt/tìm, dễ bỏ sót bài tốt | Cao: có dữ liệu Discord + scoring + web chatbot | Chọn |
| Trợ lý trả lời logistics deadline/link nộp bài | Toàn bộ học viên | Cao vào ngày nộp bài | Sai deadline gây hậu quả trực tiếp | Trung bình: cần nguồn chính thức đầy đủ và guardrail mạnh | Loại |
| Tổng hợp bản tin cuối ngày cho TA | TA/mentor | Hàng ngày | Mất thời gian đọc nhiều channel | Trung bình: cần phân cụm câu hỏi và quyền truy cập nhiều channel | Loại |

- Ứng viên chọn: tìm bài Discord chất lượng theo chủ đề.
- Lý do chọn: build được trong thời gian sự kiện, demo rõ trong 5 phút, ít rủi ro hơn trả lời logistics, có thể đo bằng ranking/search và scoring minh bạch.
- Ứng viên loại:
  - Logistics bị loại vì cost-of-error cao: sai deadline/link nộp bài có thể làm học viên mất điểm.
  - Bản tin TA bị loại vì user chính là TA, cần khảo sát riêng và dữ liệu nhiều channel hơn.

## §3. Giải Pháp Tương Tự Đã Nghiên Cứu

- Discord search:
  - Flow: nhập keyword, lọc theo channel/user/date.
  - Đáng học: dùng link gốc và giữ context bài viết thật.
  - Đáng né: chỉ keyword match, không có đánh giá chất lượng bài.
  - Mình khác: kết hợp relevance với quality score và trả top 3 có giải thích.
- Stack Overflow/Reddit ranking:
  - Flow: câu hỏi/bài viết được sắp theo vote, answer, activity.
  - Đáng học: dùng tín hiệu cộng đồng để ưu tiên nội dung hữu ích.
  - Đáng né: vote/like đơn lẻ dễ đẩy bài vui hoặc bài cũ lên cao.
  - Mình khác: scoring dùng nhiều tín hiệu thay vì chỉ like.
- NotebookLM/ChatGPT search over sources:
  - Flow: hỏi tự nhiên, hệ thống trả câu trả lời/tài liệu liên quan.
  - Đáng học: user không cần nhớ đúng từ khóa.
  - Đáng né: nếu thiếu citation/link gốc, user khó kiểm chứng.
  - Mình khác: mỗi kết quả có link Discord gốc và bảng chi tiết điểm.

## §4. Thiết Kế

- Lát cắt MỘT CÂU: Một học viên đang tìm bài Discord về một chủ đề học tập, hệ thống quyết định top 3 bài liên quan có điểm chất lượng cao nhất, để học viên mở đúng bài đáng đọc trong vài giây.
- Non-goals:
  - Không trả lời thay nội dung bài như tutor.
  - Không chấm đúng/sai kiến thức chuyên môn trong bài.
  - Không tự đăng/xóa/sửa nội dung trên Discord.
  - Không dùng dữ liệu cá nhân ngoài dữ liệu đã được phép hoặc dữ liệu giả.
- Mức prototype: Working prototype.
  - Thật: web FastAPI chạy được; SQLite lưu bài viết, embedding và lịch sử sync; background worker tự lấy bài Discord mới; hybrid search/ranking trả link gốc và chi tiết điểm.
  - Mock/proxy: click, watch time, completion rate, save/share cho dữ liệu Discord là proxy vì Discord API không cung cấp trực tiếp các trường này.
  - AI thật: `ai_analyzer.py` và `discord_bot.py --with-ai` hỗ trợ gọi Gemini/OpenAI để tạo summary/topic/tag. Mặc định không bật để tránh tốn API và tránh đưa dữ liệu thật lên API ngoài khi chưa cần.
- Automation: Conditional.
  - Hệ thống tự lấy dữ liệu và xếp hạng khi có đủ config.
  - Nếu không có config Discord, hệ thống fallback sang mock data.
  - Nếu không tìm thấy bài phù hợp, hệ thống nói rõ chưa tìm thấy thay vì bịa kết quả.
- Công thức scoring:
  - Click 20% + Like 15% + Tim 20% + Thời lượng xem 25% + Tỷ lệ xem hết 10% + Lưu/Chia sẻ 10%.
  - Mỗi tín hiệu được chuẩn hóa về 0-100 trước khi tính điểm tổng.

### §4b. Nguyên Tắc HAX/PAIR Áp Dụng

| Nguyên tắc | Áp cụ thể vào prototype |
|---|---|
| G1 - Làm rõ hệ thống làm được gì | Header và ô chat nói rõ: hỏi một chủ đề, bot trả top 3 bài liên quan có điểm chất lượng cao. |
| G2 - Làm rõ mức độ tin cậy | Mỗi kết quả hiển thị điểm chất lượng, tag và link gốc để user tự kiểm chứng. |
| G10 - Thu hẹp phạm vi khi nghi ngờ | Nếu không có match, chatbot trả "chưa tìm thấy bài phù hợp" thay vì tạo bài giả. |
| G11 - Giải thích vì sao | Có bảng "Xem chi tiết chấm điểm" nêu tín hiệu, dữ liệu gốc, trọng số, đóng góp. |
| PAIR - Feedback + Control | User luôn có thể bỏ qua kết quả, đổi query, hoặc mở bài gốc để tự kiểm chứng. |

## §5. Kiểu Lỗi - 4 Lớp Chỗ Khó + Kịch Bản

| Tình huống | Lớp | Hành vi mong muốn | Nguyên tắc |
|---|---|---|---|
| User hỏi "deadline nộp bài hôm nay là mấy giờ?" | Ngoài phạm vi/thẩm quyền | Không trả lời logistics; gợi ý tìm kênh/thông báo chính thức. | G10 |
| User hỏi "bài nào chắc chắn đúng nhất về fine-tune?" | Đặc thù domain | Trả bài liên quan và nói điểm là tín hiệu chất lượng, không phải kiểm chứng đúng/sai kiến thức. | G2 |
| Query quá chung: "AI" | Mơ hồ/thiếu thông tin | Trả top bài chất lượng cao nhất hoặc khuyến khích hỏi rõ hơn như RAG/prompt/eval. | G10 |
| Query có từ khóa không tồn tại | Nguồn sự thật | Báo chưa tìm thấy bài phù hợp, không bịa bài. | G10 |
| Discord API không có token hoặc lỗi quyền | Nguồn sự thật | Fallback mock data, hiển thị trạng thái chưa cấu hình/không đồng bộ được. | G1 |
| Message Discord chứa code block dài | Đặc thù domain | Lược bỏ code block dài khi sync để tránh nhiễu chatbot. | G2 |
| Bài có nhiều like nhưng nội dung ngắn/rác | Đặc thù domain | Scoring không chỉ dùng like; kết hợp nhiều tín hiệu và min content filter. | G11 |
| Dữ liệu Discord thiếu click/watch time | Nguồn sự thật | Ghi rõ đây là proxy/ước tính, không trình bày như số liệu thật. | G2 |

## §6. Bốn Đường Đi Của Trải Nghiệm

- Happy path:
  - User hỏi "tìm bài hay về RAG và prompt".
  - Bot trả top 3 bài, mỗi bài có title, summary, tags, điểm chất lượng, link gốc, chi tiết chấm điểm.
- Low-confidence/mơ hồ:
  - User hỏi "AI".
  - Bot vẫn trả kết quả rộng nhưng user có thể hỏi lại hẹp hơn bằng nút gợi ý hoặc input.
- Failure/không căn cứ:
  - User hỏi chủ đề không có trong dữ liệu.
  - Bot trả "Mình chưa tìm thấy bài phù hợp với câu hỏi này."
- Correction:
  - User nhập lại query khác; hệ thống không khóa flow và trả kết quả mới.
- Ngoài phạm vi:
  - Hỏi logistics/deadline/link nộp bài. Đây không phải mục tiêu prototype; cần guardrail tốt hơn ở phiên sau.
- Case đặc thù domain:
  - Hỏi nội dung có rủi ro học sai. Hệ thống chỉ recommend bài, không xác nhận kiến thức đúng tuyệt đối.

## §7. Kiểm Thử

- Chiều chất lượng cần đo:
  - Relevance: kết quả có liên quan chủ đề query.
  - Usefulness: bài có nội dung đủ dài/có tín hiệu chất lượng.
  - Groundedness: kết quả phải đến từ SQLite đã nhập từ nguồn mock/Discord hợp lệ và có link gốc.
  - Transparency: user xem được lý do/chi tiết điểm.
  - Safety: không bịa bài và không trả lời logistics ngoài phạm vi.
- Định nghĩa pass/fail:
  - Pass relevance nếu ít nhất 2/3 kết quả top 3 liên quan rõ với query.
  - Pass groundedness nếu 100% kết quả có `post_id` và `url`.
  - Pass transparency nếu 100% kết quả có quality score và bảng chi tiết điểm.
  - Pass failure handling nếu query không có dữ liệu trả thông báo không tìm thấy.
- Golden set hiện có trong `eval/golden_set.csv`:
  - 8-10 case thường: RAG, prompt, evaluation, UX, search, Streamlit, demo, security.
  - Ít nhất 2 case cho mỗi lớp chỗ khó: nguồn sự thật, mơ hồ, ngoài phạm vi, đặc thù domain.
  - 2-4 case hiếm: query trộn tiếng Việt/Anh, typo, query quá ngắn, query có từ khóa code.
- Quality bar đề xuất:
  - Đạt khi >=80% case pass relevance.
  - 100% case phải pass groundedness.
  - 100% kết quả hiển thị được chi tiết chấm điểm.
  - 0 case bịa bài ngoài dữ liệu nguồn đã lưu trong SQLite.
- Kết quả chạy hiện tại:
  - Đã chạy 26/26 case bằng `eval/run_eval.py`; relevance, groundedness, transparency và response behavior đều đạt 100%.
  - Kết quả chi tiết nằm trong `eval/results.csv`, bản tóm tắt nằm trong `eval/summary.json`.

## §8. Phân Công & Kế Hoạch

| Phần việc | Người phụ trách | Trạng thái |
|---|---|---|
| Product idea & problem framing | Phạm Thế Dũng | Đã có trong README, cần bổ sung evidence thật |
| Backend + Data | Nguyễn Huy Nghĩa | Đã có SQLite schema, migration CSV, embedding, hybrid search và background sync Discord |
| AI logic / mock AI output | Phạm Thế Dũng | Đã có mock summary/tag và module AI optional |
| Frontend Web | Phạm Văn Lưu | Đã có giao diện split-screen FastAPI + HTML/CSS/JS |
| Demo flow | Phạm Văn Lưu, Phạm Thế Dũng | Đã có `demo-script.md` và ảnh backup |
| Eval/Golden set | Cả nhóm | Đã có 26 case, strict eval đạt 26/26 |
| Validation user | Cả nhóm | Đã có 5 tên dự kiến; chờ log sử dụng thử và quote nguyên văn |

- Danh sách người dùng dự kiến: Nguyễn Thế Anh, Hà Duy Anh, Nguyễ Đức Sơn,
  Nguyễn Sỹ Đức và Vũ Văn Phong. Cần xác nhận chính tả, vai trò và việc họ đồng ý
  tham gia trước khi tính là willing users.
- Validation CP5 đề xuất hỏi 3 câu:
  - Điều gì khó hiểu hoặc khó chịu nhất khi dùng chatbot?
  - Kết quả top 3 này bạn có tin không, vì sao?
  - Bạn có dùng thật để tìm lại bài Discord không, vì sao/chưa vì sao?
- Multi-prototype đã cân nhắc:
  - Phương án A: Streamlit tab-based gồm Chatbot/Knowledge/Admin.
  - Phương án B: FastAPI + HTML/CSS/JS chỉ tập trung chatbot.
  - Chọn B vì giao diện demo gọn hơn, đúng flow chính, ít nhiễu hơn cho người dùng.

## §9. Changelog

| Thời điểm | Đổi gì | Vì sao |
|---|---|---|
| 2026-07-30 | Bỏ Knowledge base và Admin khỏi UI chính | Flow demo cần tập trung vào chatbot |
| 2026-07-30 | Chuyển mock data sang tiếng Việt có dấu | Tăng độ tự nhiên khi demo cho học viên Việt Nam |
| 2026-07-30 | Thêm sync Discord thật vào `discord_bot.py` | Cần dữ liệu thật thay vì chỉ mock |
| 2026-07-30 | Thêm tự động sync Discord theo interval | Không muốn phải chạy lệnh sync thủ công |
| 2026-07-30 | Thêm chi tiết chấm điểm từng bài | Tăng minh bạch và giải thích vì sao bài được xếp hạng |
| 2026-07-30 | Chuyển giao diện chính sang FastAPI + HTML/CSS/JS | Tránh phụ thuộc giao diện Streamlit, tạo trải nghiệm web thật hơn |
| 2026-07-30 | Thiết kế lại frontend thành AI Chat + Content Overview | Kết nối liền mạch giữa hỏi đáp, bài nổi bật và khám phá chủ đề |
| 2026-07-31 | Chuyển nguồn dữ liệu runtime từ CSV sang SQLite | Có transaction, upsert chống trùng, lịch sử sync và dễ mở rộng |
| 2026-07-31 | Thêm local embedding và hybrid search | Tìm được bài theo ngữ nghĩa nhưng vẫn giữ match từ khóa và quality score |
| 2026-07-31 | Chuyển Discord sync sang background workflow | Bài mới được xử lý độc lập với request của người dùng |
| 2026-07-31 | Tạo slide nháp, demo script, ảnh backup và template artifact nộp bài | Chuẩn bị trước toàn bộ phần không cần dữ liệu người dùng thật |
| 2026-07-31 | Viết bản nháp reflection cho 3 thành viên và thêm danh sách 5 người validation | Hoàn thiện hồ sơ có thể chuẩn bị trước nhưng không tạo feedback giả |
| 2026-07-31 | Tạo `canvas.md` và script sinh AI trace an toàn từ bài mock | Hoàn thiện artifact CP1 và chuẩn bị bằng chứng AI thật mà không dùng dữ liệu Discord |
| 2026-07-31 | Sửa false positive khi hỏi “Ai đá bóng giỏi nhất” | Không hiểu đại từ “Ai” thành acronym AI; từ chối câu hỏi thể thao ngoài phạm vi |

## Tình Trạng Artifact

- Đã có:
  - `codebase/main.py`
  - `codebase/templates/index.html`
  - `codebase/static/style.css`
  - `codebase/static/app.js`
  - `codebase/discord_bot.py`
  - `codebase/embedding_index.py`
  - `codebase/sqlite_storage.py`
  - `codebase/manage_data.py`
  - `codebase/mock_posts.csv`
  - `codebase/discord_posts.csv`
  - `codebase/README.md`
  - `eval/golden_set.csv`
  - `eval/run_eval.py`
  - `eval/results.csv`
  - `eval/summary.json`
  - `eval/case-sources.md`
  - `validation/feedback-log.md` (đã có template)
  - `evidence/mining-log.md` (đã có template)
  - `reflection/` (đã có 3 bản nháp, chờ từng thành viên xác nhận)
  - `traces/ai-call.template.json`
  - `traces/ai-call-20260731.json` (Gemini thật, chỉ dùng bài mock P001)
  - `codebase/run_ai_trace.py`
  - `canvas.md`
  - `demo-script.md`
  - `demo-backup/`
  - `demo-slides.pptx`
  - `demo-slides.pdf`
- Còn thiếu dữ liệu trước khi nộp:
  - Feedback nguyên văn từ ít nhất 5 người trong `validation/feedback-log.md`.
  - Evidence khảo sát/mining thật trong `evidence/mining-log.md`.
  - Ba thành viên đọc, sửa và xác nhận reflection đúng với trải nghiệm cá nhân.
  - Mapping nguồn cho ít nhất 10 case eval phát triển từ chatlog thật.
