import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

_BASE_DIR_PARENT = Path(__file__).resolve().parent.parent / "dataset" / "brand_car"
_BASE_DIR_LOCAL = Path(__file__).resolve().parent / "dataset" / "brand_car"
CATALOG_DIR = _BASE_DIR_PARENT if _BASE_DIR_PARENT.exists() else _BASE_DIR_LOCAL


@lru_cache(maxsize=1)
def load_all_catalogs() -> list[dict[str, Any]]:
    all_vehicles = []
    if not CATALOG_DIR.exists():
        return []

    for json_file in CATALOG_DIR.glob("*.json"):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            brand_from_file = json_file.stem.capitalize()
            for v in data.get("vehicles", []):
                v_copy = dict(v)
                if "brand" not in v_copy or not v_copy["brand"]:
                    v_copy["brand"] = brand_from_file
                all_vehicles.append(v_copy)
        except Exception as error:
            print(f"[Cảnh báo]: Lỗi đọc dataset {json_file.name}: {error}")

    return all_vehicles


def get_available_brands() -> list[str]:
    vehicles = load_all_catalogs()
    return sorted(
        list(
            {
                v.get("brand", "").strip().capitalize()
                for v in vehicles
                if v.get("brand")
            }
        )
    )


def parse_budget_range(prompt: str) -> Optional[tuple[float, float]]:
    p = prompt.lower()
    range_match = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:đến|-|tới)\s*(\d+(?:\.\d+)?)\s*tỷ", p
    )
    if range_match:
        return (
            float(range_match.group(1)) * 1_000_000_000,
            float(range_match.group(2)) * 1_000_000_000,
        )

    single_match = re.search(r"(?:tầm|khoảng|mức|dưới)\s*(\d+(?:\.\d+)?)\s*tỷ", p)
    if single_match:
        val = float(single_match.group(1)) * 1_000_000_000
        return (0.0, val) if "dưới" in p else (val * 0.8, val * 1.2)

    return None


def parse_acc_time(acc_val: Any) -> float:
    if isinstance(acc_val, (int, float)):
        return float(acc_val)
    if isinstance(acc_val, str):
        match = re.search(r"(\d+(?:\.\d+)?)", acc_val)
        if match:
            return float(match.group(1))
    return 999.0


def format_catalog_context(user_prompt: str) -> str:
    p = user_prompt.lower()
    vehicles = load_all_catalogs()
    available_brands = get_available_brands()

    unsupported_requested = []
    common_brands = [
        "bmw",
        "porsche",
        "ferrari",
        "mclaren",
        "bentley",
        "lexus",
        "lamborghini",
    ]
    for b in common_brands:
        if (
            b in p
            and b.capitalize() not in available_brands
            and b.upper() not in available_brands
        ):
            unsupported_requested.append(b.capitalize())

    brand_warning = ""
    if unsupported_requested:
        brand_warning = f"[LƯU Ý HỆ THỐNG]: Khách hỏi hãng {', '.join(unsupported_requested)} -> Showroom KHÔNG CÓ sẵn hãng này.\n\n"

    candidate_vehicles = vehicles
    budget_range = parse_budget_range(user_prompt)

    if budget_range:
        min_b, max_b = budget_range
        candidate_vehicles = [
            v
            for v in candidate_vehicles
            if isinstance(v.get("price_vnd"), (int, float))
            and min_b <= v.get("price_vnd") <= max_b
        ]

    mentioned_brands = [b for b in available_brands if b.lower() in p]
    if mentioned_brands:
        candidate_vehicles = [
            v
            for v in candidate_vehicles
            if v.get("brand", "").capitalize() in mentioned_brands
        ]

    if any(
        kw in p
        for kw in [
            "nhanh nhất",
            "chậm nhất",
            "tăng tốc",
            "top",
            "chênh lệch",
            "mã lực",
            "hp",
        ]
    ):
        target_list = candidate_vehicles if candidate_vehicles else vehicles
        sorted_list = sorted(
            target_list, key=lambda x: parse_acc_time(x.get("acceleration_0_100_kmh"))
        )

        lines = [brand_warning + "KẾT QUẢ TÍNH TOÁN VÀ SẮP XẾP BỞI PYTHON:"]
        for idx, v in enumerate(sorted_list[:5], 1):
            lines.append(
                f"{idx}. {v.get('brand').upper()} {v.get('name')}: Giá {v.get('price_vnd', 0):,} VNĐ | "
                f"Tăng tốc 0-100km/h: {parse_acc_time(v.get('acceleration_0_100_kmh'))}s | "
                f"Công suất: {v.get('power_hp', 'N/A')} HP | Số chỗ: {v.get('seats', 'N/A')} chỗ | Dẫn động: {v.get('drivetrain', 'N/A')}"
            )
        return "\n".join(lines)

    if not candidate_vehicles:
        return (
            brand_warning
            + "HỆ THỐNG: Không tìm thấy mẫu xe phù hợp với yêu cầu cụ thể."
        )

    lines = [brand_warning + "DỮ LIỆU XE PHÙ HỢP:"]
    for v in candidate_vehicles[:6]:
        price = v.get("price_vnd")
        price_str = f"{price:,}" if isinstance(price, (int, float)) else "Liên hệ"
        lines.append(
            f"- {v.get('brand', '').upper()} {v.get('name', '')}: Giá {price_str} VNĐ | "
            f"Động cơ: {v.get('powertrain', 'N/A')} | Công suất: {v.get('power_hp', 'N/A')} HP | "
            f"Số chỗ: {v.get('seats', 'N/A')} | Dẫn động: {v.get('drivetrain', 'N/A')}"
        )
    return "\n".join(lines)


def is_vehicle_list_request(text: str) -> bool:
    kws = [
        "danh sách xe",
        "xem danh sách",
        "showroom có những xe gì",
        "có các mẫu xe nào",
    ]
    return any(kw in text.lower() for kw in kws)


def format_vehicle_list_response(user_prompt: str) -> str:
    vehicles = load_all_catalogs()
    if not vehicles:
        return "Dạ, hiện tại showroom bên em chưa cập nhật dữ liệu xe ạ."

    lines = ["Dạ, em gửi danh sách các mẫu xe hiện có tại showroom ạ:\n"]
    for idx, v in enumerate(vehicles, 1):
        price = v.get("price_vnd")
        price_str = f"{price:,}" if isinstance(price, (int, float)) else "Liên hệ"
        lines.append(
            f"{idx}. **{v.get('brand', '').upper()} {v.get('name', '')}** — **{price_str} VNĐ**"
        )

    lines.append("\nAnh/Chị muốn tư vấn chi tiết mẫu xe nào trên đây ạ?")
    return "\n".join(lines)
