import os
from glob import glob
from os.path import join


def get_files():
    dir_path = os.path.dirname(os.path.realpath(__file__))
    files = glob(join(dir_path, "*.vcf"))
