from formatting import compact_number, format_display_date, format_number


def test_presentation_formatting_handles_dates_and_numbers() -> None:
    assert format_display_date("2022-01-01 00:00:00") == "01-Jan-22"
    assert format_display_date("2022-01-01 13:30:00") == "01-Jan-22 13:30:00"
    assert format_number(7_015_094_821.178518) == "7,015,094,821.18"
    assert format_number(-12.5) == "-12.5"
    assert format_number(0) == "0"
    assert compact_number(7_015_094_821.178518) == "7.0B"
