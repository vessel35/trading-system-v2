"""Hold strategy Adaptees that are deployed by placing a file here.

Nothing in this package is listed anywhere else. ``trading_plugins.discovery``
imports every module beside this one and keeps the classes that inherit
``StrategyBase`` and declare a ``STRATEGY_ID``, so adding a strategy is adding a
file rather than editing a list.
"""
