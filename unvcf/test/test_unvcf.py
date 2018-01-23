import shutil
import tempfile


def test_unvcf_convert():
    from .data import get_files
    from unvcf import unvcf

    dirpath = tempfile.mkdtemp()

    try:
        for f in get_files():
            unvcf(f, dirpath, 0)
    finally:
        shutil.rmtree(dirpath)
