import os
import json
import logging
from typing import List

try:
    from groq import Groq
except ImportError:
    pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("LLMService")

class NewsGeneratorService:
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        if not self.api_key:
            logger.warning("GROQ_API_KEY is not set. Responses will fail.")
        
        self.client = Groq()
        self.model = "openai/gpt-oss-120b"
    
    def generate_match_bulletin(self, home_team: str, away_team: str, home_score: int, away_score: int, events: List[str], stats: List[dict] = None) -> str:
        events_text = "\n".join(events) if events else "Không có diễn biến nổi bật."
        
        stats_text = ""
        if stats:
            stats_lines = []
            for stat in stats:
                if stat.get("group") == "Top stats":
                    title = stat.get("stat_title")
                    hv = stat.get("home_value")
                    av = stat.get("away_value")
                    stats_lines.append(f"- {title}: {hv} (Home) vs {av} (Away)")
            if stats_lines:
                stats_text = "\nTHỐNG KÊ TRẬN ĐẤU:\n" + "\n".join(stats_lines)
        
        prompt = f"""
Bạn là một bình luận viên bóng đá chuyên nghiệp. Hãy viết một bản tin tổng hợp BẰNG TIẾNG VIỆT về trận đấu dưới đây.

THÔNG TIN TRẬN ĐẤU:
- {home_team} {home_score} - {away_score} {away_team}
- Các sự kiện (đã được chia rõ theo từng hiệp):
{events_text}{stats_text}

YÊU CẦU:
1. Mở đầu bằng kết quả chung cuộc của trận đấu.
2. Tường thuật bắt buộc các BÀN THẮNG. 
3. ĐỐI VỚI THẺ ĐỎ: Nếu có thẻ đỏ, bắt buộc tường thuật. Nếu KHÔNG CÓ thẻ đỏ, TUYỆT ĐỐI KHÔNG báo cáo là "không có thẻ đỏ nào" (hãy lờ đi hoàn toàn).
4. ĐỐI VỚI TRẬN HÒA 0-0: Hãy viết khoảng 2 câu mô tả thế trận chặt chẽ, bế tắc và cả hai đội đành chấp nhận chia điểm mà không thể xuyên thủng mành lưới đối phương. TUYỆT ĐỐI KHÔNG tự bịa ra các pha bóng "nguy hiểm", "cú sút", "cản phá" hay nhắc đến "người hâm mộ". 
5. ĐỐI VỚI THẺ VÀNG VÀ THAY NGƯỜI: Do dữ liệu không ghi rõ cầu thủ thuộc đội nào, NGUYÊN TẮC LÀ BỎ QUA HOÀN TOÀN để tránh sai lệch kiến thức. TUYỆT ĐỐI KHÔNG TƯỜNG THUẬT THAY NGƯỜI.
6. THỐNG KÊ (nếu có): Chỉ nhắc tới 1-2 con số nổi bật nhất nếu chúng giúp mô tả thế trận (ví dụ: kiểm soát bóng áp đảo, số cú sút chênh lệch lớn). KHÔNG liệt kê hết các chỉ số. Với trận có nhiều bàn thắng, ưu tiên tường thuật bàn thắng, stats chỉ là gia vị.
7. Viết thành 1 đoạn văn liền mạch, ngắn gọn, văn phong bóng đá hấp dẫn, kịch tính nhưng PHẢI DỰA TRÊN SỰ THẬT.
8. KHÔNG tổng kết lại người ghi bàn ở cuối bài. KHÔNG SỬ DỤNG EMOJI. KHÔNG dùng gạch đầu dòng.
"""
        
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.6,
                max_completion_tokens=2048,
                top_p=1,
                reasoning_effort="medium",
                stream=False
            )
            
            content = completion.choices[0].message.content
            return content.strip() if content else f"🚨 LỖI LLM TRẢ VỀ RỖNG: {home_team} {home_score} - {away_score} {away_team}\n{events_text}"
            
        except Exception as e:
            logger.error("Error calling Groq SDK: %s", e)
            return f"🚨 LỖI CALL API: {home_team} {home_score} - {away_score} {away_team}\n{events_text}"
