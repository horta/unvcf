import argparse
import re
import sys
from os.path import abspath, basename, join

from dask.dataframe import read_csv
from tqdm import tqdm

NEWLINE = '\n'
SEP = '\t'
UNIQ_SEP = '\uDCDC'


def default_field_value(number):
    if number.isdigit():
        number = int(number)
        if number == 0:
            return ['0']
        return ['.']
    return ['.']


def parse_dict_update(v, number):
    if number.isdigit():
        number = int(number)
        v = v.split(',')
        return v + [''] * (number - len(v))
    if v == '.':
        return ['.']
    return [v]


def parse_dict(keys, fields, sep, assoc):
    if keys is None:
        if fields == '.':
            fields = []
        else:
            fields = fields.split(sep)
        dic = dict()
        for f in fields:
            kv = f.split('=')
            if len(kv) == 2:
                dic[kv[0]] = kv[1]
            else:
                dic[kv[0]] = '1'
    else:
        if fields == '.':
            fields = ['.'] * len(keys)
        else:
            fields = fields.split(sep)
        dic = {k: fields[i] for (i, k) in enumerate(keys)}

    return {
        k: parse_dict_update(v, assoc[k]['Number'])
        for k, v in dic.items()
    }


def add_missing_fields(fields, spec):
    miss = set(spec.keys()) - set(fields.keys())
    for k in miss:
        fields[k] = default_field_value(spec[k]['Number'])


def replace_open_mark(s, sep, mark):
    inside = False
    escaping = False
    s = list(s)
    for i in range(len(s)):
        if s[i] == "\\":
            escaping ^= escaping
        elif s[i] == "\"":
            if not escaping:
                inside ^= True
        elif s[i] == sep:
            if not inside:
                s[i] = mark
    return "".join(s)


def parse_dict_singular_fields(fields, sep):
    fields = fields.split(sep)
    r = dict()
    for f in fields:
        f = f.split('=')
        r[f[0]] = f[1]
    return r


def parse_metainfo_fields(line):
    left = line.find("<") + 1
    right = len(line) - line[::-1].find(">") - 1
    line = replace_open_mark(line[left:right], ',', UNIQ_SEP)
    return parse_dict_singular_fields(line, UNIQ_SEP)


def process_metainfo_line(line):

    m = re.compile(r"##([a-zA-Z]+)=.*").search(line)
    if m is None:
        raise RuntimeError("Could not parse {}.".format(line))

    key = m.groups()[0]

    return (key, parse_metainfo_fields(line))


class Metadata(object):
    def __init__(self, fp, verbosity):
        self._data = dict()
        self._line = dict(default=[])
        self._version = None
        self._verbosity = verbosity
        self._header_idx = 0

        with open(fp, 'r') as f:

            line = f.readline().strip()
            self._parse_file_header(line)
            self._line['default'].append(line)

            while line is not None:
                line = f.readline().strip()
                self._header_idx += 1

                if len(line) < 2 or line[:2] != '##':
                    break

                if self._know_field(line):
                    self._append(line)
                else:
                    if verbosity > 1:
                        print("Unknown meta-information line: {}".format(line))
                    self._line['default'].append(line)

    def _parse_file_header(self, line):
        m = re.compile(r'^##fileformat=(.*)$').search(line)
        if m is None:
            raise RuntimeError("Could not parse file header: {}".format(line))
        self._version = m.groups()[0]

        if self._verbosity > 1:
            print("File format: {}".format(self._version))

    def _know_field(self, line):
        return (line.startswith("##FORMAT") or line.startswith("##INFO")
                or line.startswith("##FILTER"))

    @property
    def header_idx(self):
        return self._header_idx

    def _append(self, line):
        key, field = process_metainfo_line(line)

        self._line[(key, field['ID'])] = line.strip()

        if key not in self._data:
            self._data[key] = []

        self._data[key].append(field)

    @property
    def format(self):
        return {d['ID']: d for d in self._data['FORMAT']}

    @property
    def info(self):
        return {d['ID']: d for d in self._data['INFO']}

    def line(self, field):
        self._line[field]


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


class Files(object):
    def __init__(self, dst):
        self._dst = dst
        self._data = dict()

    def append(self, key, filename):
        f = open(join(self._dst, filename), 'w')
        self._data[key] = dict(filename=filename, stream=f)

    def stream(self, key):
        return self._data[key]['stream']

    def close(self):
        for k in self._data:
            self._data[k]['stream'].close()

    def print_files(self):
        for k in sorted(self._data.keys(), key=lambda v: str(v)):
            print("- " + self._data[k]['filename'])


def fetch_dask_dataframe(filepath, header_idx, verbosity):
    if verbosity > 0:
        sys.stdout.write("Warming up the engine... ")
        sys.stdout.flush()
    df = read_csv(filepath, header=header_idx, sep='\t', dtype=str)
    if verbosity > 0:
        sys.stdout.write('done.\n')
    return df


class DataFrameProcessor(object):
    def __init__(self, df, metadata, files):
        self._df = df
        self._metadata = metadata
        self._files = files
        self._default = None
        self._samples = None

    def parse_header(self):
        self._default = self._df.columns[:7]
        self._samples = self._df.columns[9:]
        self._files.stream('default').write(SEP.join(self._default))

        info_ids = sorted(self._metadata.info.keys())
        self._files.stream('info').write(SEP.join(info_ids))

        for k in self._metadata.format:
            self._files.stream(('format', k)).write(SEP.join(self._samples))

    def parse_body(self):
        rows = self._df.iterrows()
        for row in tqdm(rows, unit=' genotypes'):
            self._parse_row(row[1])

    def _parse_row(self, row):
        self._files.stream('default').write(NEWLINE)
        self._files.stream('default').write(SEP.join(row.iloc[:7].values))

        info = parse_dict(None, row.iloc[7], ';', self._metadata.info)

        add_missing_fields(info, self._metadata.info)

        v = SEP.join([','.join(info[k]) for k in sorted(info.keys())])
        self._files.stream('info').write(NEWLINE + v)

        keys = row.iloc[8].split(':')
        line = {k: [] for k in self._metadata.format.keys()}

        for fields in row.iloc[9:]:
            data = parse_dict(keys, fields, ':', self._metadata.format)
            add_missing_fields(data, self._metadata.format)

            for k in data:
                line[k].append(data[k])

        for k in line:
            v = NEWLINE + SEP.join([','.join(v) for v in line[k]])
            self._files.stream(('format', k)).write(v)


def unvcf(fp, dst, verbosity):

    if verbosity > 0:
        print("Destination folder: {}".format(abspath(dst)))

    metadata = Metadata(fp, verbosity)
    files = Files(dst)

    files.append('default', '{}.default.csv'.format(basename(fp)))

    for k, v in metadata.format.items():
        files.append(('format', k), '{}.sample.{}.csv'.format(basename(fp), k))

    files.append('info', '{}.genotype.csv'.format(basename(fp)))

    if verbosity > 0:
        print("Files that are being generated:")
        files.print_files()

    df = fetch_dask_dataframe(fp, metadata.header_idx, verbosity)

    dfp = DataFrameProcessor(df, metadata, files)
    dfp.parse_header()
    dfp.parse_body()

    files.close()
    if verbosity > 0:
        print("Finished successfully!")


def entry_point():
    from unvcf import __version__

    desc = 'Split VCF file into intelligible tab-delimited files.'
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument('vcf_file', type=str, help='file path to a VCF file')
    parser.add_argument('dst_dir', type=str, help='directory destination')
    parser.add_argument(
        '--verbose', help="increase output verbosity", action="store_true")
    parser.add_argument(
        '--quiet', help="decrease output verbosity", action="store_true")
    parser.add_argument(
        '--version',
        action='version',
        version='%(prog)s {}'.format(__version__))
    args = parser.parse_args()

    verbosity = 1
    if args.verbose:
        verbosity += 1
    if args.quiet:
        verbosity -= 1

    unvcf(args.vcf_file, args.dst_dir, verbosity)
