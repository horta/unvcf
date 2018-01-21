import argparse
import sys
import re
from os.path import join, abspath
from os.path import basename
import dask
import dask.dataframe as dd
from tqdm import tqdm

NEWLINE = '\n'
SEP = '\t'


def get_header_index(fp):
    idx = 0
    with open(fp, 'r') as f:
        line = f.readline()
        while line is not None:
            if len(line) < 2 or line[:2] != '##':
                break
            idx += 1
            line = f.readline()
    return idx


def process_metainfo_info(line):
    m = re.compile(r"<ID=([^,]+),").search(line)
    if m is None:
        raise RuntimeError("Could not parse INFO: {}".format(line))
    return m.groups()[0]


def process_metainfo_format(line):
    m = re.compile(r"<ID=([^,]+),").search(line)
    if m is None:
        raise RuntimeError("Could not parse FORMAT: {}".format(line))
    return m.groups()[0]


def process_metainfo_line(line):
    if len(line) > 5 and line[2:6] == 'INFO':
        return ('info', process_metainfo_info(line))
    if len(line) > 7 and line[2:8] == 'FORMAT':
        return ('format', process_metainfo_format(line))
    return None


def parse_metainfo(f):
    idx = 0
    data = {'info': [], 'format': []}
    line = f.readline()
    while line is not None:
        if len(line) < 2 or line[:2] != '##':
            break
        dat = process_metainfo_line(line)
        if dat is not None:
            data[dat[0]].append({'id': dat[1], 'line': line})
        idx += 1
        line = f.readline()
    return (idx, data)


def define_format_filenames(fp, dst, data):
    name = basename(fp)
    assoc = dict()
    dst = abspath(dst)
    print("Sample-based files:")
    for d in data:
        f = join(dst, "{}.{}.csv".format(name, d['id']))
        assoc[d['id']] = f
        print("- {}={}".format(d['id'], basename(f)))
    return assoc


def process_format(df, format_files):

    rows = df.iterrows()
    row = next(rows)
    series = row[1][9:]
    nsamples = len(series)

    written = dict()
    for k in format_files:
        fp = format_files[k]
        f = open(fp, 'w')
        format_files[k] = (fp, f)
        f.write(SEP.join(series.index.values))
        written[k] = False

    for i, row in tqdm(rows, desc='Genotype'):
        formats = row[8].split(':')
        series = row[9:]

        for _, f in format_files.values():
            f.write(NEWLINE)

        for j, c in enumerate(series):
            for l, v in enumerate(c.split(':')):
                f = format_files[formats[l]][1]
                f.write(v)
                written[formats[l]] = True
                if j < nsamples - 1:
                    f.write(SEP)

        for f in written:
            if written[f]:
                written[f] = False
            else:
                format_files[f][1].write(NEWLINE)

    for f in format_files.values():
        f[1].close()


def unvcf(fp, dst):

    with open(fp, 'r') as f:
        (hidx, metadata) = parse_metainfo(f)

    sys.stdout.write("Warming up the engine... ")
    sys.stdout.flush()
    df = dd.read_csv(fp, header=hidx, sep='\t', dtype=str)
    sys.stdout.write('done.\n')

    print("Destination folder: {}".format(abspath(dst)))

    format_files = define_format_filenames(fp, dst, metadata['format'])
    process_format(df, format_files)

    print("Finished successfully!")


def entry_point():
    desc = 'Split VCF file into intelligible tab-delimited files.'
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument('vcf_file', type=str, help='file path to a VCF file')
    parser.add_argument('dst_dir', type=str, help='directory destination')
    args = parser.parse_args()

    unvcf(args.vcf_file, args.dst_dir)
