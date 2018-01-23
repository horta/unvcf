import shutil
import tempfile


def test_unvcf_convert():
    from .data import get_files
    from unvcf import unvcf

    dirpath = tempfile.mkdtemp()

    try:
        for f in get_files():
            try:
                unvcf(f, dirpath, 0)
            except Exception:
                print(f)
                import pdb
                pdb.set_trace()
    finally:
        shutil.rmtree(dirpath)
