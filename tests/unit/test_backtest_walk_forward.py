from __future__ import annotations

import pandas as pd

from backtest.backtest import walk_forward_split


def test_walk_forward_split_returns_copies_and_isolation() -> None:
    df = pd.DataFrame({"x": list(range(10))})
    train, validation = walk_forward_split(df, train_pct=0.7)

    assert len(train) == 7
    assert len(validation) == 3

    train.loc[train.index[0], "x"] = 999
    assert df.loc[df.index[0], "x"] == 0

    validation.loc[validation.index[0], "x"] = 777
    assert df.loc[df.index[7], "x"] == 7
