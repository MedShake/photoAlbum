from photoalbum.album import (
    PageSide,
    PaginationResult,
    PlannedPage,
    PrintConstraints,
    PrintDiagnostics,
)


def pagination_with_pages(
    count: int,
) -> PaginationResult:
    return PaginationResult(
        pages=[
            PlannedPage(
                number=number,
                side=(
                    PageSide.RIGHT
                    if number % 2 == 1
                    else PageSide.LEFT
                ),
                kind=None,
                template_id=None,
            )
            for number in range(1, count + 1)
        ]
    )


def test_multiple_of_four_is_compatible():
    pagination = pagination_with_pages(40)

    diagnostic = PrintDiagnostics().analyze(
        pagination,
        PrintConstraints(page_multiple=4),
    )

    assert diagnostic.page_count == 40
    assert diagnostic.compatible
    assert diagnostic.pages_to_add == 0


def test_42_pages_suggests_two_additional_pages():
    pagination = pagination_with_pages(42)

    diagnostic = PrintDiagnostics().analyze(
        pagination,
        PrintConstraints(page_multiple=4),
    )

    assert diagnostic.page_count == 42
    assert not diagnostic.compatible
    assert diagnostic.pages_to_add == 2


def test_43_pages_suggests_one_additional_page():
    diagnostic = PrintDiagnostics().analyze(
        pagination_with_pages(43),
        PrintConstraints(page_multiple=4),
    )

    assert diagnostic.pages_to_add == 1


def test_41_pages_suggests_three_additional_pages():
    diagnostic = PrintDiagnostics().analyze(
        pagination_with_pages(41),
        PrintConstraints(page_multiple=4),
    )

    assert diagnostic.pages_to_add == 3


def test_no_constraints_always_accepts_pagination():
    pagination = pagination_with_pages(42)

    diagnostic = PrintDiagnostics().analyze(
        pagination,
        None,
    )

    assert diagnostic.compatible
    assert diagnostic.pages_to_add == 0


def test_constraints_can_have_no_page_multiple():
    diagnostic = PrintDiagnostics().analyze(
        pagination_with_pages(42),
        PrintConstraints(),
    )

    assert diagnostic.compatible
    assert diagnostic.pages_to_add == 0


def test_diagnostic_does_not_modify_pagination():
    pagination = pagination_with_pages(42)

    before = list(pagination.pages)

    PrintDiagnostics().analyze(
        pagination,
        PrintConstraints(page_multiple=4),
    )

    assert pagination.pages == before
    assert len(pagination.pages) == 42


def test_arbitrary_page_multiple_is_supported():
    diagnostic = PrintDiagnostics().analyze(
        pagination_with_pages(50),
        PrintConstraints(page_multiple=8),
    )

    assert not diagnostic.compatible
    assert diagnostic.pages_to_add == 6


def test_invalid_page_multiple_is_rejected():
    try:
        PrintConstraints(page_multiple=0)
    except ValueError:
        pass
    else:
        raise AssertionError(
            "Expected ValueError for page_multiple=0"
        )



def test_diagnostic_preserves_page_multiple_when_compatible():
    pagination = PaginationResult(
        pages=[
            PlannedPage(
                number=index + 1,
                side=(
                    PageSide.RIGHT
                    if index % 2 == 0
                    else PageSide.LEFT
                ),
                kind=None,
                template_id=None,
            )
            for index in range(4)
        ]
    )

    diagnostic = PrintDiagnostics().analyze(
        pagination,
        PrintConstraints(
            page_multiple=4,
        ),
    )

    assert diagnostic.compatible
    assert diagnostic.page_multiple == 4


def test_diagnostic_preserves_page_multiple_when_incompatible():
    pagination = PaginationResult(
        pages=[
            PlannedPage(
                number=index + 1,
                side=(
                    PageSide.RIGHT
                    if index % 2 == 0
                    else PageSide.LEFT
                ),
                kind=None,
                template_id=None,
            )
            for index in range(6)
        ]
    )

    diagnostic = PrintDiagnostics().analyze(
        pagination,
        PrintConstraints(
            page_multiple=4,
        ),
    )

    assert not diagnostic.compatible
    assert diagnostic.pages_to_add == 2
    assert diagnostic.page_multiple == 4
