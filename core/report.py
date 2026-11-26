"""Exporta los datos y el procedimiento completo a PDF y Excel."""

from dataclasses import dataclass
from fractions import Fraction
from io import BytesIO
from math import isfinite
from textwrap import wrap
from xml.sax.saxutils import escape

from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.chart import BarChart, Reference
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, TableStyle

from . import results
from .models import Cell, Problem, Solution
from .modi import ModiResult

TITLE = "Solucionador del Método de Transporte"
BLUE = "183A60"
LIGHT_BLUE = "DDEBF7"
PALE = "F0F5FA"
SIGN_COLORS = ("FDE4E4", "FFF0C2", "DDF3E6")
PDF_SYMBOLS = str.maketrans({"Δ": "Delta", "θ": "theta", "→": "->", "−": "-",
                            "–": "-", "—": "-", "≤": "<=", "≥": ">="})

Value = str | int | Fraction


@dataclass(frozen=True)
class ReportTable:
    headers: tuple[str, ...]
    rows: list[tuple[Value, ...]]
    widths: tuple[int, ...] = ()
    basis: frozenset[Cell] = frozenset()
    problem: Problem | None = None
    delta_column: int | None = None
    percent_column: int | None = None
    chart: bool = False


@dataclass(frozen=True)
class Section:
    sheet: str
    title: str
    content: list[str | ReportTable]


def _matrix(problem: Problem, solution: Solution | None = None) -> ReportTable:
    labels = results.origin_labels(problem)
    destinations = results.destination_labels(problem)
    matrix = solution.assignments if solution else problem.costs
    rows = [(label, *row, offer) for label, row, offer in zip(labels, matrix, problem.supply)]
    rows.append(("Demanda", *problem.demand, sum(problem.demand)))
    return ReportTable(
        ("Origen", *destinations, "Oferta"), rows, (16, *((8,) * len(destinations)), 8),
        solution.basis if solution else frozenset(), problem if solution else None,
    )


def _method_section(problem: Problem, method: str, solution: Solution, index: int) -> Section:
    rows, cols, valid = results.feasibility(problem, solution)
    expected_basics = sum(problem.shape) - 1
    status = "Factible" if valid else "No factible"
    steps = [results.step_record(step_index, step) for step_index, step in enumerate(solution.steps, 1)]
    return Section(f"Método {index}", method, [
        "Asignaciones paso a paso",
        ReportTable(results.STEP_HEADERS, steps, (5, 8, 19, 13, 13, 21, 21)),
        "Matriz inicial de envíos. Las celdas sombreadas son básicas.",
        _matrix(problem, solution),
        results.cost_expression(problem, solution),
        f"{status}. Variables básicas {len(solution.basis)} de {expected_basics} esperadas.",
        ReportTable(("Origen", "Envíos", "Oferta"), rows),
        ReportTable(("Destino", "Recepciones", "Demanda"), cols),
    ])


def _modi_section(problem: Problem, method: str, result: ModiResult, sheet: str) -> Section:
    content: list[str | ReportTable] = [
        results.STATUS[result.status],
        "Se fija u1 = 0. Una solución de minimización es óptima cuando todas las diferencias Δ son ≤ 0.",
    ]
    for index, iteration in enumerate(result.iterations):
        label = ""
        if index == result.pivots:
            label = " Plan óptimo." if results.optimal(result) else " Último plan factible."
        content.extend([
            f"Iteración {index}. Z = {results.fmt(iteration.solution.total_cost)}.{label}",
            _matrix(problem, iteration.solution),
            ReportTable(("Orden", "Ruta", "Ecuación", "Potencial calculado"),
                        results.equation_records(problem, iteration), (7, 12, 28, 53)),
            ReportTable(("Ruta", "Cálculo de Δ", "Δ"), results.delta_records(problem, iteration),
                        (15, 65, 20), delta_column=2),
        ])
        pivot = iteration.pivot
        if pivot is not None:
            cycle = " → ".join(f"{'+' if k % 2 == 0 else '−'}{results.route(cell)}"
                               for k, cell in enumerate(pivot.cycle))
            content.extend([
                f"Entra {results.route(pivot.entering)} y sale {results.route(pivot.leaving)}.",
                f"Ciclo {cycle}",
                f"θ = {results.fmt(pivot.theta)}. Nuevo Z = {results.fmt(pivot.new_cost)}. "
                f"Reducción = {results.fmt(pivot.reduction)}.",
            ])
            if pivot.bland:
                content.append("Se aplicó la regla anticiclado de Bland.")
    content.append(results.cost_expression(problem, result.solution))
    return Section(sheet, f"MODI · {method}", content)


def _sections(
    problem: Problem, solutions: dict[str, Solution], checks: dict[str, ModiResult],
    batch: dict[str, ModiResult],
) -> list[Section]:
    objective, supply, demand = results.model(problem)
    sections = [
        Section("Datos", "Datos balanceados", [results.balance_message(problem), _matrix(problem)]),
        Section("Modelo", "Modelo matemático", [
            "Cada x[i,j] representa las unidades enviadas del origen i al destino j.",
            "Minimizar Z = " + " + ".join(objective),
            "Restricciones de oferta",
            ReportTable(("Origen", "Restricción"), list(zip(results.origin_labels(problem), supply)), (21, 79)),
            "Restricciones de demanda",
            ReportTable(("Destino", "Restricción"), list(zip(results.destination_labels(problem), demand)), (21, 79)),
            "x[i,j] ≥ 0 para todas las rutas.",
        ]),
    ]
    sections.extend(_method_section(problem, name, solution, index)
                    for index, (name, solution) in enumerate(solutions.items(), 1))
    if len(solutions) > 1:
        rows, formulas, analysis = results.comparison(solutions, checks | batch)
        numeric_rows = [
            (name, cost, gap, gap / cost if cost else percent, basis, status)
            for name, cost, gap, percent, basis, status in rows
        ]
        sections.append(Section("Comparación", "Resumen comparativo", [
            ReportTable(results.COMPARISON_HEADERS, numeric_rows, (21, 14, 18, 12, 10, 25),
                        percent_column=3, chart=True),
            ReportTable(("Método", "Cálculo del ahorro"), formulas, (28, 72)),
            analysis,
            results.COMPARISON_NOTE,
            "Plan para la gerencia",
            *results.management(problem, solutions),
        ]))
    if batch:
        sections.append(Section("Verificación conjunta", "Verificación conjunta con MODI", [
            ReportTable(results.MODI_HEADERS, results.batch_records(solutions, batch), (25, 15, 20, 20, 20)),
        ]))
    for index, (name, check) in enumerate((checks | batch).items(), 1):
        sections.append(_modi_section(problem, name, check, f"MODI {index}"))
    return sections


def _clean(text: str) -> str:
    return ILLEGAL_CHARACTERS_RE.sub("", text)


def _plain(value: Value, percent: bool = False) -> str:
    if isinstance(value, str):
        return _clean(value)
    if percent:
        return f"{results.fmt(value * 100, 2)} %"
    return results.fmt(value)


def _sign_color(value: Value) -> str:
    return SIGN_COLORS[0 if value > 0 else 1 if value == 0 else 2]


def _pdf_markup(text: str) -> str:
    return escape(_clean(text).translate(PDF_SYMBOLS)).replace("\n", "<br/>")


def _pdf_table(block: ReportTable, width: float, styles) -> LongTable:
    def paragraph(text: str, style: str = "Cell") -> Paragraph:
        return Paragraph(_pdf_markup(text), styles[style])

    values = [[paragraph(name, "HeaderCell") for name in block.headers]]
    for row_index, row in enumerate(block.rows):
        cells = []
        for column, value in enumerate(row):
            text = _plain(value, column == block.percent_column)
            if block.problem and row_index < len(block.problem.supply) and 0 < column <= len(block.problem.demand):
                cost = results.fmt(block.problem.costs[row_index][column - 1])
                cells.append(Paragraph(f"<font size='7'>Costo {cost}</font><br/>{text}", styles["Cell"]))
            else:
                cells.append(paragraph(text))
        values.append(cells)

    sizes = block.widths or (1,) * len(block.headers)
    table = LongTable(values, colWidths=[width * size / sum(sizes) for size in sizes],
                      repeatRows=1, splitByRow=1, splitInRow=1, hAlign="LEFT")
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(f"#{BLUE}")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), (colors.white, colors.HexColor(f"#{PALE}"))),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor(f"#{BLUE}")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]
    for i, j in sorted(block.basis):
        commands.append(("BACKGROUND", (j + 1, i + 1), (j + 1, i + 1), colors.HexColor(f"#{LIGHT_BLUE}")))
    if block.delta_column is not None:
        column = block.delta_column
        for i, row in enumerate(block.rows, 1):
            color = colors.HexColor(f"#{_sign_color(row[column])}")
            commands.append(("BACKGROUND", (column, i), (column, i), color))
    table.setStyle(TableStyle(commands))
    return table


def _pdf_chart(block: ReportTable, width: float) -> Drawing:
    drawing = Drawing(width, 29 + len(block.rows) * 24)
    drawing.add(String(0, drawing.height - 14, "Costos de las soluciones iniciales", fontName="Helvetica-Bold", fontSize=10))
    largest = max((row[1] for row in block.rows), default=0)
    for index, row in enumerate(block.rows):
        name, cost = row[:2]
        y = drawing.height - 40 - index * 24
        drawing.add(String(0, y + 2, name, fontName="Helvetica", fontSize=8))
        length = (width - 240) * float(cost / largest) if largest else 0
        drawing.add(Rect(130, y, length, 11, strokeColor=None, fillColor=colors.HexColor(f"#{BLUE}")))
        drawing.add(String(134 + length, y + 2, _plain(cost), fontName="Helvetica", fontSize=8))
    return drawing


def pdf_report(
    problem: Problem, solutions: dict[str, Solution], checks: dict[str, ModiResult] | None = None,
    batch: dict[str, ModiResult] | None = None,
) -> bytes:
    output = BytesIO()
    document = SimpleDocTemplate(output, pagesize=landscape(A4), title=TITLE,
                                 leftMargin=30, rightMargin=30, topMargin=36, bottomMargin=32)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("ReportBody", parent=styles["BodyText"], leading=14, spaceAfter=7))
    styles.add(ParagraphStyle("Cell", fontName="Helvetica", fontSize=8, leading=10))
    styles.add(ParagraphStyle("HeaderCell", parent=styles["Cell"], fontName="Helvetica-Bold", textColor=colors.white))
    styles["Heading1"].textColor = colors.HexColor(f"#{BLUE}")
    styles["Heading1"].spaceAfter = 12

    styles["Heading1"].spaceBefore = 12
    styles["Heading1"].keepWithNext = True
    styles["Title"].textColor = colors.HexColor(f"#{BLUE}")
    story = [Paragraph(TITLE, styles["Title"])]
    for section in _sections(problem, solutions, checks or {}, batch or {}):
        story.append(Paragraph(_pdf_markup(section.title), styles["Heading1"]))
        for block in section.content:
            if isinstance(block, str):
                story.append(Paragraph(_pdf_markup(block), styles["ReportBody"]))
            else:
                story.extend([_pdf_table(block, document.width - 12, styles), Spacer(1, 8)])
                if block.chart:
                    story.extend([_pdf_chart(block, document.width - 12), Spacer(1, 8)])

    def page(canvas, doc) -> None:
        canvas.saveState()
        canvas.setFillColor(colors.HexColor(f"#{BLUE}"))
        canvas.setFont("Helvetica", 8)
        canvas.drawString(doc.leftMargin, 18, f"{TITLE} · Programación Lineal")
        canvas.drawRightString(doc.pagesize[0] - doc.rightMargin, 18, f"Página {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=page, onLaterPages=page)
    return output.getvalue()


def _excel_cell(sheet, row: int, column: int, value: Value, percent: bool = False):
    cell = sheet.cell(row, column)
    if isinstance(value, str):
        cell.value = _clean(value)[:32767]
        cell.data_type = "s"
    else:
        try:
            numeric = float(value)
        except OverflowError:
            numeric = float("inf")
        if isfinite(numeric):
            cell.value = value.numerator if isinstance(value, Fraction) and value.denominator == 1 else numeric
            if percent:
                cell.number_format = "0.00%"
        else:
            cell.value = _plain(value, percent)
            cell.data_type = "s"
    cell.alignment = Alignment(vertical="top", wrap_text=True)
    return cell


def _excel_table(sheet, first: int, block: ReportTable, widths: dict[int, int]) -> int:
    for column, header in enumerate(block.headers, 1):
        cell = _excel_cell(sheet, first, column, header)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor=BLUE)
        widths[column] = max(widths.get(column, 12), min(38, len(header) + 4))
    for offset, row in enumerate(block.rows):
        for column, value in enumerate(row, 1):
            percentage = column - 1 == block.percent_column
            cell = _excel_cell(sheet, first + offset + 1, column, value, percentage)
            widths[column] = max(widths[column], min(38, len(_plain(value, percentage)) + 3))
            if offset % 2:
                cell.fill = PatternFill("solid", fgColor=PALE)
            if block.problem and offset < len(block.problem.supply) and 1 < column <= len(block.problem.demand) + 1:
                cost = results.fmt(block.problem.costs[offset][column - 2])
                cell.comment = Comment(f"Costo unitario {cost}", "Método de Transporte")
                if (offset, column - 2) in block.basis:
                    cell.fill = PatternFill("solid", fgColor=LIGHT_BLUE)
            if column - 1 == block.delta_column:
                cell.fill = PatternFill("solid", fgColor=_sign_color(value))
    if block.chart:
        chart = BarChart()
        chart.title = "Costos de las soluciones iniciales"
        chart.y_axis.title = "Costo Z"
        chart.legend = None
        chart.add_data(Reference(sheet, min_col=2, min_row=first, max_row=first + len(block.rows)),
                       titles_from_data=True)
        chart.set_categories(Reference(sheet, min_col=1, min_row=first + 1, max_row=first + len(block.rows)))
        sheet.add_chart(chart, f"{get_column_letter(len(block.headers) + 2)}{first}")
    return first + len(block.rows) + 2


def excel_report(
    problem: Problem, solutions: dict[str, Solution], checks: dict[str, ModiResult] | None = None,
    batch: dict[str, ModiResult] | None = None,
) -> bytes:
    workbook = Workbook()
    workbook.remove(workbook.active)
    workbook.properties.title = TITLE
    for section in _sections(problem, solutions, checks or {}, batch or {}):
        sheet = workbook.create_sheet(section.sheet)
        sheet.freeze_panes = "A2"
        sheet.sheet_view.showGridLines = False
        sheet.sheet_properties.pageSetUpPr.fitToPage = True
        sheet.page_setup.orientation = "landscape"
        sheet.page_setup.fitToWidth = 1
        sheet.page_setup.fitToHeight = 0
        widths = {1: 24, 2: 18, 3: 18, 4: 18}
        narrative = {1: section.title}
        row = 3
        for block in section.content:
            if isinstance(block, str):
                narrative[row] = block
                row += 1
            else:
                row = _excel_table(sheet, row, block, widths)
        merged_columns = min(6, len(widths))
        for row, value in narrative.items():
            sheet.merge_cells(start_row=row, start_column=1, end_row=row, end_column=merged_columns)
            cell = _excel_cell(sheet, row, 1, value)
            if row == 1:
                cell.font = Font(bold=True, size=15, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor=BLUE)
        for column, width in widths.items():
            sheet.column_dimensions[get_column_letter(column)].width = width
        for row in sheet.iter_rows():
            lines = 1
            for cell in row:
                if not isinstance(cell.value, str):
                    continue
                width = (sum(widths[k] for k in range(1, merged_columns + 1)) if cell.row in narrative
                         else widths[cell.column])
                lines = max(lines, sum(max(1, len(wrap(line, max(1, int(width * 0.86)))))
                                       for line in cell.value.splitlines()))
            sheet.row_dimensions[row[0].row].height = min(409, max(18, 14 * lines + 4))
        sheet.row_dimensions[1].height = 26
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()
