"""Fuzz targets, and the properties they check.

A package rather than loose scripts so that ``tests/test_fuzzing.py`` can import
:mod:`fuzz.properties` and run the same claims on every platform -- Atheris has
wheels for one. Run a target with ``python -m fuzz.fuzz_hostile``.
"""
