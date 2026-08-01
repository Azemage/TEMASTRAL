import os
import tempfile

# Base de données isolée pour les tests, définie avant tout import de `app`.
_tmp_dir = tempfile.mkdtemp()
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmp_dir}/test.db")
