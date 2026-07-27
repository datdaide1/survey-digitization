"""Sinh câu văn tiếng Việt cho DOCX theo văn phong §9 docs/implement-plan-statistics-and-client-report.md:

- Ngôn ngữ đời thường gắn với thực tế trồng trọt/gia đình, KHÔNG thuật ngữ thống kê
  trong câu văn (không viết "n=85", "SD=...", "Cronbach's alpha" thẳng vào narrative).
- Trình bày số liệu trung tính, không quy kết/đánh giá thiếu sót (vd không viết
  "phụ nữ dân tộc X có trình độ học vấn thấp" — viết "X% phụ nữ chưa từng đi học").
- Áp dụng nhất quán mọi tầng — riêng Tầng 4/5 (effect size/so sánh nhóm phi tham số,
  thêm ở milestone sau) phải dùng "liên hệ quan sát", không dùng "tác động"/"ảnh hưởng".
"""

from __future__ import annotations

from typing import Any


def _pct(x: float) -> str:
    return f"{x:.0f}%".replace(".0%", "%") if abs(x - round(x)) < 0.05 else f"{x:.1f}%"


def categorical_sentence(freq: dict[str, Any]) -> str:
    rows = [r for r in freq["rows"] if r["n"] > 0]
    if not rows:
        return f"Không có dữ liệu hợp lệ cho mục này."
    rows_sorted = sorted(rows, key=lambda r: r["n"], reverse=True)
    top = rows_sorted[0]
    # 26/07: % tính trên tổng mẫu (total_n=85), không chỉ trên số phiếu trả lời câu này
    # — câu văn đổi theo cho khớp với cách tính %, xem frequency.py.
    sentence = (
        f"Trong tổng {freq['total_n']} phiếu khảo sát, nhóm '{top['label']}' "
        f"chiếm tỷ lệ nhiều nhất với {_pct(top['pct'])} ({top['n']} người)."
    )
    if len(rows_sorted) > 1:
        second = rows_sorted[1]
        sentence += f" Kế đến là '{second['label']}' với {_pct(second['pct'])} ({second['n']} người)."
    if freq["missing_n"]:
        sentence += f" Còn {freq['missing_n']} phiếu chưa ghi rõ câu này."
    return sentence


def continuous_sentence(desc: dict[str, Any]) -> str:
    if desc["n"] == 0:
        return "Không có dữ liệu hợp lệ cho mục này."
    return (
        f"Tính trên {desc['n']} phiếu ghi rõ số liệu, mức phổ biến (trung vị) là "
        f"{desc['median']:.0f}, dao động chủ yếu trong khoảng {desc['q1']:.0f}–{desc['q3']:.0f} "
        f"(thấp nhất {desc['min']:.0f}, cao nhất {desc['max']:.0f})."
    )


def multi_select_sentence(field_label: str, option_rows: list[dict[str, Any]], n_total: int) -> str:
    rows_sorted = sorted(option_rows, key=lambda r: r["pct"], reverse=True)
    top = rows_sorted[:3]
    parts = [f"'{r['label']}' ({_pct(r['pct'])})" for r in top if r["pct"] > 0]
    if not parts:
        return f"Không có phiếu nào chọn phương án nào trong mục '{field_label}'."
    return f"Các lựa chọn được nhiều người chọn nhất trong '{field_label}': " + ", ".join(parts) + "."


def marriage_age_sentence(bracket_freq: dict[str, Any]) -> str:
    early = next((r for r in bracket_freq["rows"] if r["code"] == "<18"), None)
    if not early or early["n"] == 0:
        return "Không ghi nhận trường hợp kết hôn trước 18 tuổi trong số phiếu có ghi rõ tuổi kết hôn."
    return (
        f"Trong tổng {bracket_freq['total_n']} phiếu khảo sát, có {early['n']} người "
        f"({_pct(early['pct'])}) kết hôn trước 18 tuổi."
    )


def experience_sentence(desc: dict[str, Any], bracket_freq: dict[str, Any]) -> str:
    under_1 = next((r for r in bracket_freq["rows"] if r["code"] == "<1"), None)
    base = continuous_sentence(desc)
    if under_1 and bracket_freq["total_n"]:
        base += (
            f" Trong đó {under_1['n']} người ({_pct(under_1['pct'])}) mới gắn bó với cây dược liệu "
            f"dưới 1 năm."
        )
    return base
