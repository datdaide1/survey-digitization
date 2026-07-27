"""Vẽ biểu đồ PNG tĩnh (matplotlib, backend Agg) để chèn vào DOCX — python-docx không
nhúng được biểu đồ Excel "sống", nên DOCX dùng ảnh tĩnh riêng, khác hẳn "Biểu đồ" sheet
trong XLSX (native Excel chart, khách copy/phóng to được — xem xlsx_writer.py).

26/07: đổi từ palette toàn các sắc xanh (khó phân biệt khi >2-3 lát/cột cùng biểu đồ,
phản hồi của khách) sang palette định tính (qualitative) — mỗi màu khác hẳn nhau về tông,
vẫn đủ trung tính/in ấn được. `_BAR_COLOR` (1 màu, dùng cho biểu đồ 1 chuỗi số liệu) và
`_QUALITATIVE_COLORS` (nhiều màu phân biệt, dùng cho pie/stacked/grouped/scatter/radar —
nhiều lát/chuỗi trong cùng 1 biểu đồ) đều lấy từ cùng 1 bảng màu, màu đầu tiên trùng nhau
để nhất quán khi 1 loại biểu đồ vừa có bản 1-chuỗi vừa có bản nhiều-chuỗi.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

_BAR_COLOR = "#4C72B0"
_QUALITATIVE_COLORS = [
    "#4C72B0",  # xanh dương
    "#DD8452",  # cam
    "#55A868",  # xanh lá
    "#C44E52",  # đỏ
    "#8172B2",  # tím
    "#937860",  # nâu
    "#DA8BC3",  # hồng
    "#8C8C8C",  # xám
    "#CCB974",  # vàng/olive
    "#64B5CD",  # xanh cyan nhạt
]
# Tên cũ, giữ alias để không phải sửa chỗ khác lỡ còn tham chiếu trực tiếp.
_PIE_COLORS = _QUALITATIVE_COLORS

plt.rcParams.update({
    "font.size": 11,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.dpi": 150,
})


def _save(fig, out_path: str | Path) -> str:
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    return str(out_path)


def _label_bars(ax, bars, values, horizontal: bool = True) -> None:
    """Ghi % ngay cạnh mỗi cột — biểu đồ chỉ có độ dài cột không đủ để đọc số chính xác,
    khách phải đưa chuột/đo bằng mắt mới ước lượng được (phản hồi của khách)."""
    labels = [f"{v:.1f}%".replace(".0%", "%") for v in values]
    ax.bar_label(bars, labels=labels, padding=3, fontsize=9)


def bar_chart(freq: dict[str, Any], out_path: str | Path, horizontal: bool = True) -> str:
    rows = [r for r in freq["rows"] if r["n"] > 0] or freq["rows"]
    labels = [r["label"] for r in rows]
    values = [r["pct"] for r in rows]

    fig, ax = plt.subplots(figsize=(7, max(2, 0.45 * len(labels) + 1)))
    if horizontal:
        bars = ax.barh(labels, values, color=_BAR_COLOR)
        ax.invert_yaxis()
        ax.set_xlabel("%")
        ax.set_xlim(0, max(values, default=0) * 1.15 + 5)
    else:
        bars = ax.bar(labels, values, color=_BAR_COLOR)
        ax.set_ylabel("%")
        ax.set_ylim(0, max(values, default=0) * 1.15 + 5)
        plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
    _label_bars(ax, bars, values, horizontal)
    ax.set_title(f"{freq['label']} (n={freq['valid_n']})")
    return _save(fig, out_path)


def pie_chart(freq: dict[str, Any], out_path: str | Path) -> str:
    """Pie + chú giải (legend) đặt riêng bên phải — KHÔNG in nhãn thẳng lên từng lát cắt.
    Nhãn trên lát cắt (mặc định của matplotlib) không tự tránh chồng lấn, với >4-5 lát
    hoặc lát nhỏ (case thường gặp khi có thêm hạng mục multi-mark) chữ đè lên nhau, khó
    đọc trên bản in/Word. Chỉ hiện % ngay trên lát đủ lớn (>=5%), tên đầy đủ nằm ở legend."""
    rows = [r for r in freq["rows"] if r["n"] > 0]
    labels = [r["label"] for r in rows]
    values = [r["n"] for r in rows]
    colors = [_PIE_COLORS[i % len(_PIE_COLORS)] for i in range(len(values))]

    fig, ax = plt.subplots(figsize=(8.5, 5))
    wedges, _texts, _autotexts = ax.pie(
        values,
        colors=colors,
        startangle=90,
        autopct=lambda pct: f"{pct:.0f}%" if pct >= 5 else "",
        pctdistance=0.75,
        textprops={"color": "white", "fontsize": 9, "fontweight": "bold"},
    )
    ax.legend(
        wedges, labels,
        loc="center left", bbox_to_anchor=(1.02, 0.5),
        fontsize=9, frameon=False,
    )
    ax.set_title(f"{freq['label']} (n={freq['valid_n']})")
    return _save(fig, out_path)


def histogram(desc: dict[str, Any], series, out_path: str | Path, bins: int = 12) -> str:
    valid = series.dropna()
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(valid, bins=bins, color=_BAR_COLOR, edgecolor="white")
    ax.set_title(f"{desc['label']} (n={desc['n']})")
    ax.set_ylabel("Số phiếu")
    return _save(fig, out_path)


def multi_select_bar(title: str, option_labels: list[str], pct_values: list[float], n_total: int, out_path: str | Path) -> str:
    """1 thanh ngang / lựa chọn — dùng cho multi_select (Q7, Q11, Q18, Q19, Q21b, Q22a, Q22b, Q28, Q33...)."""
    fig, ax = plt.subplots(figsize=(7, max(2, 0.45 * len(option_labels) + 1)))
    bars = ax.barh(option_labels, pct_values, color=_BAR_COLOR)
    ax.invert_yaxis()
    ax.set_xlabel("%")
    ax.set_xlim(0, max(pct_values, default=0) * 1.15 + 5)
    _label_bars(ax, bars, pct_values)
    ax.set_title(f"{title} (n={n_total}, có thể chọn nhiều phương án)")
    return _save(fig, out_path)


def stacked_matrix_bar(title: str, row_labels: list[str], col_labels: list[str], pct_matrix, out_path: str | Path) -> str:
    """Stacked bar ngang cho matrix (Q14/Q32) — mỗi dòng 1 thanh, chia theo cột (vợ/chồng/cả hai...).

    pct_matrix: list các dict {col_label: pct} theo đúng thứ tự row_labels.
    """
    fig, ax = plt.subplots(figsize=(8, max(2.5, 0.5 * len(row_labels) + 1)))
    left = [0.0] * len(row_labels)
    colors = _QUALITATIVE_COLORS
    for i, col_label in enumerate(col_labels):
        values = [row.get(col_label, 0.0) for row in pct_matrix]
        bars = ax.barh(row_labels, values, left=left, label=col_label, color=colors[i % len(colors)])
        # Chỉ in % ngay trên đoạn đủ lớn (>=8%) — đoạn nhỏ hơn chữ đè lên nhau, khó đọc.
        seg_labels = [f"{v:.0f}%" if v >= 8 else "" for v in values]
        ax.bar_label(bars, labels=seg_labels, label_type="center", color="white", fontsize=8, fontweight="bold")
        left = [l + v for l, v in zip(left, values)]
    ax.invert_yaxis()
    ax.set_xlabel("%")
    ax.set_title(title)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=min(len(col_labels), 5))
    return _save(fig, out_path)


def grouped_bar(title: str, row_labels: list[str], series_labels: list[str], values_matrix, out_path: str | Path) -> str:
    """Grouped bar (Q17 thiết bị x vợ/chồng) — values_matrix: list[dict[series_label, pct]] theo row_labels."""
    import numpy as np

    n_rows = len(row_labels)
    n_series = len(series_labels)
    x = np.arange(n_rows)
    width = 0.8 / max(n_series, 1)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    for i, s_label in enumerate(series_labels):
        values = [row.get(s_label, 0.0) for row in values_matrix]
        bars = ax.bar(x + i * width, values, width, label=s_label, color=_QUALITATIVE_COLORS[i % len(_QUALITATIVE_COLORS)])
        ax.bar_label(bars, labels=[f"{v:.0f}%" for v in values], padding=2, fontsize=7, rotation=90)
    ax.set_xticks(x + width * (n_series - 1) / 2)
    ax.set_xticklabels(row_labels, rotation=20, ha="right")
    ax.set_ylabel("%")
    ax.set_ylim(0, 115)
    ax.set_title(title)
    ax.legend()
    return _save(fig, out_path)


def scree_plot(eigenvalues, out_path: str | Path, title: str) -> str:
    """Scree plot cho factor analysis (Tầng 7, §8) — cột eigenvalue giảm dần + đường
    tham chiếu ngang y=1 (Kaiser criterion, số nhân tố giữ lại = số cột vượt qua đường này)."""
    values = list(eigenvalues)
    x = list(range(1, len(values) + 1))
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(x, values, color=_BAR_COLOR)
    ax.axhline(1.0, color="#C0504D", linestyle="--", linewidth=1.2, label="Mốc Kaiser (eigenvalue = 1)")
    ax.set_xticks(x)
    ax.set_xlabel("Nhân tố thứ")
    ax.set_ylabel("Eigenvalue")
    ax.set_title(title)
    ax.legend()
    return _save(fig, out_path)


def cluster_scatter(coords_2d, labels, out_path: str | Path, title: str) -> str:
    """Scatter 2D (sau giảm chiều PCA) cho cluster analysis (Tầng 7, §8) — mỗi màu 1 cụm."""
    import numpy as np

    labels = np.asarray(labels)
    fig, ax = plt.subplots(figsize=(7, 5.5))
    for i, cluster_id in enumerate(sorted(set(labels))):
        mask = labels == cluster_id
        ax.scatter(
            coords_2d[mask, 0], coords_2d[mask, 1],
            color=_PIE_COLORS[i % len(_PIE_COLORS)], label=f"Cụm {cluster_id + 1}",
            s=50, edgecolor="white", linewidth=0.5,
        )
    ax.set_xlabel("Trục tổng hợp 1")
    ax.set_ylabel("Trục tổng hợp 2")
    ax.set_title(title)
    ax.legend()
    return _save(fig, out_path)


def radar_chart(categories: list[str], series: dict[str, list[float]], out_path: str | Path, title: str) -> str:
    """Radar chart (§11 "Đa chiều") — mỗi trục 1 hạng mục, mỗi đường 1 nhóm so sánh
    (vd tỉnh). Dùng cho ảnh tĩnh trong DOCX — bản "sống" trong XLSX dùng
    openpyxl.chart.RadarChart riêng (xem xlsx_writer.write_q32_radar)."""
    import numpy as np

    n = len(categories)
    angles = [i / n * 2 * np.pi for i in range(n)]
    angles += angles[:1]
    fig, ax = plt.subplots(figsize=(7.5, 7.5), subplot_kw={"polar": True})
    for i, (name, values) in enumerate(series.items()):
        vals = list(values) + [values[0]]
        color = _PIE_COLORS[i % len(_PIE_COLORS)]
        ax.plot(angles, vals, color=color, linewidth=2, label=name)
        ax.fill(angles, vals, color=color, alpha=0.15)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, fontsize=8)
    ax.set_title(title, y=1.1)
    ax.legend(loc="upper right", bbox_to_anchor=(1.35, 1.1), fontsize=9)
    return _save(fig, out_path)


def _wrap_labels(labels: list[str], width: int = 42) -> list[str]:
    import textwrap
    return ["\n".join(textwrap.wrap(label, width)) or label for label in labels]


def odds_ratio_forest(title: str, labels: list[str], values: list[float], out_path: str | Path) -> str:
    """Forest plot cho các cặp odds ratio ở Tầng 4 (DOCX — bản xlsx đã có ở
    effect_size_sheet.py, đây là bản ảnh tĩnh tương ứng cho Word). Mốc trung lập = 1
    (đường đứt nét); xanh = khả năng cao hơn, đỏ = khả năng thấp hơn.

    26/07 (phản hồi khách — bản cũ "dài ngoằng bé tý xấu"): dữ liệu thực tế các cặp odds
    ratio ở đây đều trong khoảng 1-3 lần, dùng trục log (cách cũ) chỉ hợp khi có cả tỷ lệ
    rất lớn LẪN rất nhỏ (vd 0.1 và 10) — với khoảng hẹp, log làm biểu đồ trông rỗng/lệch và
    nhãn trục ra dạng khoa học khó đọc (1.2×10^0). Giờ tự chọn: log CHỈ khi khoảng giá trị
    thật sự rộng (max/min > 8), còn lại dùng trục thường — đồng thời wrap nhãn dài + tăng
    khoảng cách dòng để không còn dẹt."""
    wrapped = _wrap_labels(labels)
    n = len(labels)
    fig, ax = plt.subplots(figsize=(9.5, max(3, 0.7 * n + 1)))
    y = list(range(n))
    colors = ["#55A868" if v >= 1 else "#C44E52" for v in values]
    ax.hlines(y, [1] * len(values), values, color=colors, linewidth=2.5)
    ax.scatter(values, y, color=colors, s=70, zorder=3)
    for yi, v in zip(y, values):
        ax.annotate(f"{v:.2f}", (v, yi), textcoords="offset points", xytext=(8, 0), fontsize=9, va="center", fontweight="bold")
    ax.axvline(1.0, color="#666666", linestyle="--", linewidth=1, label="Mốc trung lập (=1)")

    finite_pos = [v for v in values if v > 0]
    value_range = (max(finite_pos) / min(finite_pos)) if finite_pos and min(finite_pos) > 0 else 1
    if value_range > 8:
        ax.set_xscale("log")
        from matplotlib.ticker import ScalarFormatter
        ax.xaxis.set_major_formatter(ScalarFormatter())
        ax.set_xlabel("Odds ratio (thang log)")
    else:
        lo = min(0.5, min(values) * 0.8) if values else 0
        hi = max(values) * 1.35 if values else 2
        ax.set_xlim(lo, hi)
        ax.set_xlabel("Odds ratio")
    ax.set_yticks(y)
    ax.set_yticklabels(wrapped, fontsize=9)
    ax.set_ylim(-0.7, n - 0.3)
    ax.invert_yaxis()
    ax.set_title(title)
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    return _save(fig, out_path)


def eta_squared_bar(title: str, labels: list[str], values_pct: list[float], out_path: str | Path) -> str:
    """Bar % biến thiên giải thích được (eta-squared*100) cho các cặp categorical<->số ở
    Tầng 4 — cùng thang 0-100% nên so sánh trực tiếp được giữa các cặp, khác odds ratio
    (thang log, không gộp chung biểu đồ được)."""
    wrapped = _wrap_labels(labels)
    n = len(labels)
    fig, ax = plt.subplots(figsize=(9.5, max(3, 0.55 * n + 1)))
    bars = ax.barh(wrapped, values_pct, color=_QUALITATIVE_COLORS[2])
    ax.invert_yaxis()
    ax.set_xlabel("% biến thiên giải thích được")
    ax.set_xlim(0, max(values_pct, default=0) * 1.2 + 5)
    ax.tick_params(axis="y", labelsize=9)
    _label_bars(ax, bars, values_pct)
    ax.set_title(title)
    fig.tight_layout()
    return _save(fig, out_path)


def composite_distribution(title: str, values, out_path: str | Path) -> str:
    """Histogram phân bố chỉ số tổng hợp (Tầng 6, thang 0-100) trên toàn bộ phiếu, kèm
    đường trung bình — thay cho chỉ mô tả bằng chữ (min/max/trung vị) như bản cũ."""
    values = list(values)
    mean_v = sum(values) / len(values) if values else 0
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(values, bins=12, color=_BAR_COLOR, edgecolor="white", range=(0, 100))
    ax.axvline(mean_v, color="#C44E52", linestyle="--", linewidth=1.5, label=f"Trung bình = {mean_v:.0f}")
    ax.set_xlabel("Chỉ số (0-100)")
    ax.set_ylabel("Số phiếu")
    ax.set_title(title)
    ax.legend()
    return _save(fig, out_path)


def box_whisker(title: str, groups: list[dict[str, Any]], out_path: str | Path) -> str:
    """Box-and-whisker (§11) cho so sánh nhóm phi tham số (Tầng 5) — mỗi group là
    {"label": str, "values": list[float]}. openpyxl KHÔNG hỗ trợ chart Box-and-Whisker
    gốc Excel (chỉ có ở Office 2016+, ngoài phạm vi chart type openpyxl.chart hỗ trợ) —
    dùng ảnh tĩnh matplotlib cho cả DOCX lẫn XLSX (xem lib/report/effect_size_sheet.py)."""
    labels = [g["label"] for g in groups]
    data = [g["values"] for g in groups]
    fig, ax = plt.subplots(figsize=(7, max(3, 0.8 * len(labels) + 1.5)))
    ax.boxplot(data, tick_labels=labels, orientation="horizontal", patch_artist=True,
               boxprops={"facecolor": _PIE_COLORS[2], "alpha": 0.6})
    ax.set_title(title)
    return _save(fig, out_path)


