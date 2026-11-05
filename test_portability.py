import sqlite3
from contextlib import closing
import tempfile
import unittest
from pathlib import Path
from prepare_laptop import relocate_mlflow


class PortabilityTest(unittest.TestCase):
    def test_relocation_preserves_results_and_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with closing(sqlite3.connect(root/'mlflow.db')) as c, c:
                c.executescript('CREATE TABLE experiments (experiment_id INTEGER, artifact_location TEXT);'
                                'CREATE TABLE runs (run_uuid TEXT, experiment_id INTEGER, artifact_uri TEXT);'
                                'CREATE TABLE metrics (value REAL);')
                c.execute('INSERT INTO experiments VALUES (?,?)',(1,'file:D:/old/mlruns/1'))
                c.execute('INSERT INTO runs VALUES (?,?,?)',('abc',1,'file:D:/old/mlruns/1/abc/artifacts'))
                c.execute('INSERT INTO metrics VALUES (?)',(12.61,))
            relocate_mlflow(root)
            relocate_mlflow(root)
            with closing(sqlite3.connect(root/'mlflow.db')) as c:
                self.assertEqual(c.execute('SELECT artifact_uri FROM runs').fetchone()[0],
                                 (root/'mlruns/1/abc/artifacts').as_uri())
                self.assertEqual(c.execute('SELECT value FROM metrics').fetchone()[0],12.61)
            with closing(sqlite3.connect(root/'mlflow.db.before_move')) as c:
                self.assertEqual(c.execute('SELECT artifact_uri FROM runs').fetchone()[0],
                                 'file:D:/old/mlruns/1/abc/artifacts')


if __name__=='__main__':
    unittest.main()
