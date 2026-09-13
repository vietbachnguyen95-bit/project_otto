import os
from pathlib import Path
from typing import Optional

from catalog_manager import (
    format_catalog_context,
    format_vehicle_list_response,
    get_available_brands,
    is_vehicle_list_request,
)
from db_cache import SemanticCache

os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"

BASE_DIR = Path(__file__).resolve().parent.parent
_LOCAL_3B_PATH = BASE_DIR / "models" / "Qwen2.5-3B"
MODEL_NAME = (
    str(_LOCAL_3B_PATH)
    if _LOCAL_3B_PATH.exists()
    else os.getenv("MODEL_NAME", "mlx-community/Qwen2.5-3B-Instruct-4bit")
)

_model = None
_tokenizer = None
_generate_fn = None
_make_sampler_fn = None
_cache_instance = None


def _get_cache() -> SemanticCache:
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = SemanticCache()
    return _cache_instance


def _get_model():
    global _model, _tokenizer, _generate_fn, _make_sampler_fn
    if _model is not None:
        return _model, _tokenizer, _generate_fn, _make_sampler_fn

    from mlx_lm import generate, load
    from mlx_lm.sample_utils import make_sampler

    _generate_fn, _make_sampler_fn = generate, make_sampler
    print(f"[HỆ THỐNG]: Đang tải mô hình LLM từ {MODEL_NAME}...")
    _model, _tokenizer = load(MODEL_NAME)
    print("[HỆ THỐNG]: Tải mô hình thành công!")
    return _model, _tokenizer, _generate_fn, _make_sampler_fn


def should_bypass_cache(prompt: str) -> bool:
    p = prompt.lower().strip()
    keywords = [
        "tỷ",
        "triệu",
        "top",
        "nhanh nhất",
        "chậm nhất",
        "so sánh",
        "lái thử",
        "bmw",
        "porsche",
        "audi",
        "mercedes",
        "lamborghini",
        "ferrari",
        "chi phí",
        "bảo dưỡng",
        "mã lực",
        "hp",
        "0-100",
        "tăng tốc",
    ]
    return any(kw in p for kw in keywords) or len(p.split()) > 6


SYSTEM_PROMPT_TEMPLATE = """\
**VAI TRÒ VÀ PHONG CÁCH TÁC PHONG**
Bạn là Chuyên viên Tư vấn Khách hàng VIP tại Showroom Ô tô Cao cấp. 
- Phong cách: Tinh tế, lịch sự, chuyên nghiệp và luôn tôn trọng khách hàng (xưng "em" và gọi "Anh/Chị" hoặc theo danh xưng khách đã cung cấp).
- Mục tiêu: Hỗ trợ giải đáp thông tin xe, so sánh thông số, tư vấn giải pháp phù hợp với nhu cầu và thúc đẩy khách hàng đặt lịch trải nghiệm/lái thử tại showroom.
- Danh sách thương hiệu hiện có dữ liệu tại showroom: {available_brands}.

**NGUYÊN TẮC XỬ LÝ TRÍ THỨC (GROUNDING & TRUTH PROTOCOLS)**
1. Tính Trung Thực Tuyệt Đối Với Dữ Liệu (Strict Factuality):
   - Chỉ trả lời dựa trên thông tin có trong phần [DỮ LIỆU SẢN PHẨM] được cấp. 
   - Không tự ý thêm bớt, suy đoán hoặc bịa đặt thông số kỹ thuật, giá bán, hoặc tính năng không được đề cập trong dữ liệu.
2. Xử Lý Khách Hàng Hỏi Sản Phẩm/Thương Hiệu Nằm Ngoài Dữ Liệu:
   - Nếu khách hàng hỏi về các thương hiệu, dòng xe hoặc dịch vụ KHÔNG CÓ trong phần dữ liệu được cấp, hãy khéo léo thông báo hiện tại showroom chưa phân phối/chưa có dữ liệu về dòng xe đó, sau đó gợi ý các mẫu xe tương đương hiện đang có sẵn trong kho.
3. Nguyên Tắc Trả Lời Về Chi Phí Bảo Dưỡng & Dịch Vụ Sau Bán Hàng:
   - Do chi phí bảo dưỡng biến động theo từng cấp độ kỹ thuật và tình trạng xe, tuyệt đối không đưa ra con số ước tính cụ thể trừ khi dữ liệu ghi rõ. Hãy hướng dẫn khách hàng mang xe qua xưởng dịch vụ chính hãng để nhận báo giá chi tiết.
4. Tôn Trọng Bản Quyền Công Nghệ & Thương Hiệu:
   - Giữ nguyên các tên gọi công nghệ bản quyền của từng hãng (ví dụ: Quattro của Audi, 4MATIC của Mercedes-Benz, xDrive của BMW). Không tự ý gộp hoặc gán nhầm tên công nghệ giữa các hãng khác nhau.

**QUY TẮC XỬ LÝ CON SỐ VÀ LOGIC BẢO VỆ**
- Đối với các yêu cầu lọc ngân sách, so sánh tốc độ hoặc tính toán mã lực: Bắt buộc sử dụng trực tiếp các bảng thứ tự và kết quả đã được hệ thống tính toán sẵn trong phần [DỮ LIỆU SẢN PHẨM]. Không tự tính toán lại các phép toán phức tạp.
- Thời gian tăng tốc (0-100 km/h) số giây nhỏ hơn có nghĩa là xe tăng tốc nhanh hơn.

**ĐỊNH DẠNG ĐẦU RA (OUTPUT FORMATTING)**
- Trình bày câu trả lời ngắn gọn, rõ ràng, ưu tiên sử dụng danh sách gạch đầu dòng hoặc bảng so sánh nhẹ để khách hàng dễ theo dõi.
- Kết thúc mỗi câu trả lời bằng một lời mời trải nghiệm hoặc câu hỏi gợi mở lịch thiệp để tiếp tục cuộc trò chuyện.

[DỮ LIỆU SẢN PHẨM CUNG CẤP CHO LẦN HỎI NÀY]
{context_data}"""


def generate_car_advice(
    user_prompt: str, conversation_history: Optional[list[dict[str, str]]] = None
) -> str:
    if is_vehicle_list_request(user_prompt):
        return format_vehicle_list_response(user_prompt)

    bypass = should_bypass_cache(user_prompt)
    if not bypass:
        cached_res = _get_cache().search(user_prompt)
        if cached_res.get("hit"):
            return cached_res["response"]

    model, tokenizer, generate_fn, make_sampler_fn = _get_model()
    available_brands_str = ", ".join(get_available_brands())
    context_data = format_catalog_context(user_prompt)

    system_content = SYSTEM_PROMPT_TEMPLATE.format(
        available_brands=available_brands_str, context_data=context_data
    )

    messages = [{"role": "system", "content": system_content}]
    if conversation_history:
        messages.extend(conversation_history[-4:])
    messages.append({"role": "user", "content": user_prompt})

    formatted_prompt = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True, enable_thinking=False
    )

    response = generate_fn(
        model,
        tokenizer,
        prompt=formatted_prompt,
        max_tokens=600,
        sampler=make_sampler_fn(temp=0.1),
        verbose=False,
    )

    if not bypass:
        _get_cache().add(user_prompt, response)

    return response
