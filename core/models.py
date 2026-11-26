"""Datos y trazas que comparten los algoritmos, la interfaz y los reportes."""

from dataclasses import dataclass
from fractions import Fraction
from numbers import Real

Cell = tuple[int, int]
Quantity = Fraction
Matrix = tuple[tuple[Quantity, ...], ...]


def number(value: object) -> Quantity:
    """Conserva exactamente el valor decimal ingresado."""
    if isinstance(value, bool) or not isinstance(value, (Real, Fraction)):
        raise ValueError("debe ser un número finito y no negativo")
    try:
        result = Fraction(str(value))
    except (ValueError, OverflowError) as error:
        raise ValueError("debe ser un número finito y no negativo") from error
    if result < 0:
        raise ValueError("debe ser un número finito y no negativo")
    return result


@dataclass(frozen=True)
class Problem:
    costs: Matrix
    supply: tuple[Quantity, ...]
    demand: tuple[Quantity, ...]
    origins: tuple[str, ...] = ()
    destinations: tuple[str, ...] = ()
    dummy_origin: int | None = None
    dummy_destination: int | None = None

    def __post_init__(self) -> None:
        m, n = len(self.supply), len(self.demand)
        if not (2 <= m <= 10 + (self.dummy_origin is not None)
                and 2 <= n <= 10 + (self.dummy_destination is not None)):
            raise ValueError("Ingresa de 2 a 10 orígenes y destinos.")
        if len(self.costs) != m or any(len(row) != n for row in self.costs):
            raise ValueError("La matriz de costos debe coincidir con las ofertas y demandas.")
        if (self.origins and len(self.origins) != m) or (
            self.destinations and len(self.destinations) != n
        ):
            raise ValueError("La cantidad de nombres debe coincidir con la dimensión.")

        def read(value: object, label: str) -> Quantity:
            try:
                return number(value)
            except ValueError as error:
                raise ValueError(f"{label} {error}.") from error

        object.__setattr__(self, "costs", tuple(
            tuple(read(value, f"El costo de la ruta O{i + 1}–D{j + 1}")
                  for j, value in enumerate(row))
            for i, row in enumerate(self.costs)
        ))
        for field, values, label in (
            ("supply", self.supply, "La oferta O"), ("demand", self.demand, "La demanda D")
        ):
            object.__setattr__(self, field, tuple(
                read(value, f"{label}{index + 1}") for index, value in enumerate(values)
            ))
        object.__setattr__(self, "origins", tuple(
            str(name).strip() or f"O{i + 1}"
            for i, name in enumerate(self.origins or ("",) * m)
        ))
        object.__setattr__(self, "destinations", tuple(
            str(name).strip() or f"D{j + 1}"
            for j, name in enumerate(self.destinations or ("",) * n)
        ))

    @property
    def shape(self) -> tuple[int, int]:
        return len(self.supply), len(self.demand)


@dataclass(frozen=True)
class Step:
    cell: Cell
    offer: Quantity
    need: Quantity
    quantity: Quantity
    supply_left: tuple[Quantity, ...]
    demand_left: tuple[Quantity, ...]
    observation: str = ""
    row_penalties: tuple[tuple[int, Quantity], ...] = ()
    column_penalties: tuple[tuple[int, Quantity], ...] = ()


@dataclass(frozen=True)
class Solution:
    assignments: Matrix
    steps: tuple[Step, ...]
    total_cost: Quantity
    basis: frozenset[Cell]


def make_solution(
    problem: Problem, assignments: list[list[Quantity]], steps: tuple[Step, ...],
    basis: set[Cell] | frozenset[Cell],
) -> Solution:
    m, n = problem.shape
    cost = sum(
        (assignments[i][j] * problem.costs[i][j] for i in range(m) for j in range(n)),
        Fraction(0),
    )
    return Solution(tuple(map(tuple, assignments)), steps, cost, frozenset(basis))
