-- A schema spelled in mixed case, for `python -m tools.fuzz`.
--
--   * every name is mixed case, which SQL folds and the reserved names have
--     to match in every spelling;
--   * `Accounts.Parent_Id` points back at `Accounts`;
--   * `Amount` is a NUMERIC with a precision, `Opened` a DATE and `Enabled`
--     a BOOL, the aliases the type classes have to know;
--   * `Settings` has no foreign key at all, so the join graph never reaches
--     it.
--
-- Valid in both SQLite and PostgreSQL, so `tools/postgres.py` can run what
-- the walks write over it.

CREATE TABLE Accounts (
    Id BIGINT PRIMARY KEY,
    Name TEXT NOT NULL,
    Parent_Id BIGINT REFERENCES Accounts(Id),
    Opened DATE
);

CREATE TABLE Ledger (
    Id BIGINT PRIMARY KEY,
    Account_Id BIGINT NOT NULL REFERENCES Accounts(Id),
    Amount NUMERIC(12, 2) NOT NULL,
    Note VARCHAR(80),
    Booked TIMESTAMP
);

CREATE TABLE Settings (
    Key_Name TEXT PRIMARY KEY,
    Enabled BOOL NOT NULL
);
