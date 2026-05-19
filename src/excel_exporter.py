from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from typing import List, Dict
import config


def export_to_excel(movies: List[Dict], filepath: str = None):
    if not filepath:
        filepath = config.EXCEL_PATH

    wb = Workbook()
    ws = wb.active
    ws.title = "电影下载列表"

    headers = ["电影名", "上映年份", "电影分类", "下载链接", "文件大小", "来源网站", "链接类型"]
    ws.append(headers)

    # Header style
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for movie in movies:
        ws.append([
            movie.get("name", ""),
            movie.get("year", ""),
            movie.get("genre", ""),
            movie.get("link", ""),
            movie.get("size", ""),
            movie.get("source", ""),
            movie.get("link_type", ""),
        ])

    # Auto-adjust column widths
    column_widths = [25, 12, 15, 60, 12, 12, 12]
    for i, width in enumerate(column_widths, 1):
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = width

    # Link column should be wrapped
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=4, max_col=4):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")

    wb.save(filepath)
    print(f"[Excel] Exported {len(movies)} movies to {filepath}")
