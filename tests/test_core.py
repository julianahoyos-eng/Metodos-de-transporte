import random
from collections.abc import Callable

import pytest
from scipy.optimize import linprog

from core import least_cost, northwest, vogel
from core.balance import balance
from core.models import Problem, Solution
from core.modi import analyze


SOLVERS = (northwest.solve, least_cost.solve, vogel.solve)
Solver = Callable[[Problem], Solution]


@pytest.fixture
def caso_a() -> Problem:
    return Problem(((4, 6, 8), (5, 3, 4), (6, 4, 7)), (20, 30, 25), (30, 25, 20))


@pytest.fixture
def caso_b() -> Problem:
    return Problem(
        (
            (18, 31, 37, 38, 85),
            (17, 30, 44, 40, 86),
            (17, 26, 37, 45, 90),
            (24, 37, 47, 33, 80),
        ),
        (50, 85, 125, 90),
        (35, 40, 115, 125, 35),
    )


def verificar_factibilidad(problem: Problem, solution: Solution) -> None:
    m, n = len(problem.supply), len(problem.demand)
    assert len(solution.assignments) == m
    assert all(len(row) == n for row in solution.assignments)
    assert tuple(map(sum, solution.assignments)) == pytest.approx(problem.supply)
    assert tuple(map(sum, zip(*solution.assignments))) == pytest.approx(problem.demand)

    basis = set(solution.basis)
    assert len(solution.basis) == len(basis) == m + n - 1
    assert all(0 <= i < m and 0 <= j < n for i, j in basis)
    for i, row in enumerate(solution.assignments):
        for j, quantity in enumerate(row):
            assert quantity >= 0
            if quantity > 0:
                assert (i, j) in basis

    # Cada ruta básica une el nodo del origen con el nodo del destino.
    connected = {0}
    for _ in range(m + n - 1):
        for i, j in basis:
            if i in connected or m + j in connected:
                connected.update((i, m + j))
    assert len(connected) == m + n

    cost = sum(
        problem.costs[i][j] * quantity
        for i, row in enumerate(solution.assignments)
        for j, quantity in enumerate(row)
    )
    assert solution.total_cost == pytest.approx(cost)


@pytest.mark.parametrize(
    ("solve", "cost_a", "cost_b"),
    [(northwest.solve, 350, 14285), (least_cost.solve, 340, 13350), (vogel.solve, 310, 13230)],
    ids=["noroeste", "costo-minimo", "vogel"],
)
def test_ejemplos_del_enunciado(
    solve: Solver, cost_a: int, cost_b: int, caso_a: Problem, caso_b: Problem
) -> None:
    for problem, initial_cost, optimum in ((caso_a, cost_a, 310), (caso_b, cost_b, 13230)):
        initial = solve(problem)
        verificar_factibilidad(problem, initial)
        assert initial.steps
        assert initial.total_cost == initial_cost

        check = analyze(problem, initial)
        if initial_cost > optimum:
            assert check.status == "nonoptimal"
            assert check.solution.assignments == initial.assignments

        improved = analyze(problem, initial, improve=True)
        verificar_factibilidad(problem, improved.solution)
        assert improved.solution.total_cost == optimum
        assert improved.status == ("alternate" if problem is caso_a else "unique")
        if initial_cost > optimum:
            assert improved.pivots > 0


def test_plan_de_vogel_del_caso_a(caso_a: Problem) -> None:
    solution = vogel.solve(caso_a)
    assert solution.assignments == ((20, 0, 0), (0, 10, 20), (10, 15, 0))


def test_traza_modi_de_los_ejemplos(caso_a: Problem, caso_b: Problem) -> None:
    initial_a = vogel.solve(caso_a)
    result_a = analyze(caso_a, initial_a)
    snapshot_a = result_a.iterations[0]
    assert snapshot_a.u == (0, 1, 2)
    assert snapshot_a.v == (4, 2, 3)
    assert snapshot_a.deltas == {(0, 1): -4, (0, 2): -5, (1, 0): 0, (2, 2): -2}
    assert {equation[0] for equation in snapshot_a.equations} == initial_a.basis
    assert result_a.pivots == 0

    initial_b = vogel.solve(caso_b)
    result_b = analyze(caso_b, initial_b)
    snapshot_b = result_b.iterations[0]
    assert snapshot_b.u == (0, 2, 0, -5)
    assert snapshot_b.v == (15, 26, 37, 38, 84)
    assert len(snapshot_b.deltas) == 12
    assert all(delta < 0 for delta in snapshot_b.deltas.values())
    assert {equation[0] for equation in snapshot_b.equations} == initial_b.basis
    assert result_b.pivots == 0


def test_modi_registra_el_pivote_y_respeta_el_limite(caso_a: Problem) -> None:
    initial = northwest.solve(caso_a)
    limited = analyze(caso_a, initial, improve=True, max_iterations=0)
    assert limited.status == "limit"
    assert limited.solution == initial
    assert limited.pivots == 0

    improved = analyze(caso_a, initial, improve=True)
    pivot = improved.iterations[0].pivot
    assert pivot is not None
    assert pivot.entering == (1, 2)
    assert pivot.leaving == (1, 1)
    assert pivot.cycle == ((1, 2), (2, 2), (2, 1), (1, 1))
    assert pivot.theta == 20
    assert pivot.new_cost == improved.solution.total_cost == 310
    assert pivot.reduction == 40


@pytest.mark.parametrize(
    ("supply", "demand", "expected_origin", "expected_destination"),
    [((4, 3), (2, 3), None, 2), ((2, 3), (4, 3), 2, None)],
    ids=["destino-ficticio", "origen-ficticio"],
)
def test_caso_c_agrega_el_ficticio_con_costo_cero(
    supply: tuple[int, ...],
    demand: tuple[int, ...],
    expected_origin: int | None,
    expected_destination: int | None,
) -> None:
    original = Problem(((2, 5), (4, 1)), supply, demand)
    problem = balance(original)
    assert problem.dummy_origin == expected_origin
    assert problem.dummy_destination == expected_destination
    assert original.supply == supply
    assert original.demand == demand
    assert sum(problem.supply) == sum(problem.demand) == 7
    if expected_origin is not None:
        assert problem.costs[expected_origin] == (0, 0)
        assert problem.supply[expected_origin] == 2
    if expected_destination is not None:
        assert all(row[expected_destination] == 0 for row in problem.costs)
        assert problem.demand[expected_destination] == 2
    for solve in SOLVERS:
        result = analyze(problem, solve(problem), improve=True)
        verificar_factibilidad(problem, result.solution)
        assert result.solution.total_cost == 7
        real_cost = sum(
            original.costs[i][j] * result.solution.assignments[i][j]
            for i in range(2)
            for j in range(2)
        )
        assert real_cost == result.solution.total_cost


@pytest.mark.parametrize("solve", SOLVERS, ids=["noroeste", "costo-minimo", "vogel"])
def test_caso_d_conserva_una_basica_degenerada(solve: Solver) -> None:
    problem = Problem(((1, 9, 9), (9, 1, 9), (9, 9, 1)), (2, 3, 4), (2, 3, 4))
    initial = solve(problem)
    verificar_factibilidad(problem, initial)
    assert sum(initial.assignments[i][j] == 0 for i, j in initial.basis) == 2
    assert analyze(problem, initial, improve=True).status == "unique"


def test_costos_reducidos_cero_con_demanda_y_oferta_nulas() -> None:
    problem = Problem(((0, 0), (0, 0)), (0, 0), (0, 0))
    for solve in SOLVERS:
        result = analyze(problem, solve(problem), improve=True)
        verificar_factibilidad(problem, result.solution)
        assert result.solution.total_cost == 0
        assert result.status == "unique"


def test_totales_decimales_balanceados() -> None:
    problem = balance(Problem(((1.25, 9.5), (8.5, 2.5)), (0.1, 0.2), (0.15, 0.15)))
    assert problem.dummy_origin is None
    assert problem.dummy_destination is None
    for solve in SOLVERS:
        result = analyze(problem, solve(problem), improve=True)
        verificar_factibilidad(problem, result.solution)
        assert result.status == "unique"
        assert result.solution.total_cost == pytest.approx(0.925)


def test_entrada_maxima_con_destino_ficticio() -> None:
    costs = tuple(tuple(1 if i == j else 20 for j in range(10)) for i in range(10))
    problem = balance(Problem(costs, (3,) * 10, (2,) * 10))
    assert problem.dummy_destination == 10
    for solve in SOLVERS:
        result = analyze(problem, solve(problem), improve=True)
        verificar_factibilidad(problem, result.solution)
        assert result.solution.total_cost == 20
        assert result.status == "unique"


@pytest.mark.parametrize("invalid", [None, "texto", -1, float("nan"), float("inf")])
def test_rechaza_costos_invalidos(invalid: object) -> None:
    with pytest.raises(ValueError, match="costo"):
        Problem(((invalid, 0), (0, 0)), (1, 1), (1, 1))


def casos_aleatorios() -> list[Problem]:
    rng = random.Random(7349)
    problems = []
    for index in range(200):
        max_size = 6 if index % 2 == 0 else 5
        m, n = rng.randint(2, max_size), rng.randint(2, max_size)
        costs = tuple(tuple(rng.randint(0, 12) for _ in range(n)) for _ in range(m))
        if index % 2 == 0:
            # Las sumas de la misma matriz garantizan el balance.
            flows = tuple(tuple(rng.randint(0, 5) for _ in range(n)) for _ in range(m))
            supply = tuple(map(sum, flows))
            demand = tuple(map(sum, zip(*flows)))
        else:
            supply = tuple(rng.randint(0, 18) for _ in range(m))
            demand = tuple(rng.randint(0, 18) for _ in range(n))
        problems.append(Problem(costs, supply, demand))
    return problems


@pytest.mark.parametrize("original", casos_aleatorios(), ids=[f"caso-{i + 1}" for i in range(200)])
def test_modi_coincide_con_linprog(original: Problem) -> None:
    problem = balance(original)
    m, n = len(problem.supply), len(problem.demand)
    positions = [(i, j) for i in range(m) for j in range(n)]
    row_constraints = [[int(i == origin) for i, _ in positions] for origin in range(m)]
    column_constraints = [[int(j == destination) for _, j in positions] for destination in range(n)]
    oracle = linprog(
        [float(problem.costs[i][j]) for i, j in positions],
        A_eq=row_constraints + column_constraints,
        b_eq=list(map(float, (*problem.supply, *problem.demand))),
        method="highs",
    )
    assert oracle.success, oracle.message

    for solve in SOLVERS:
        initial = solve(problem)
        verificar_factibilidad(problem, initial)
        result = analyze(problem, initial, improve=True)
        verificar_factibilidad(problem, result.solution)
        assert result.status in ("unique", "alternate"), (solve.__module__, result.status)
        assert result.solution.total_cost == pytest.approx(oracle.fun, abs=1e-7), solve.__module__
