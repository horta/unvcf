import argparse
import re
import sys
from os.path import abspath, basename, join

from dask.dataframe import read_csv
from tqdm import tqdm

NEWLINE = '\n'
SEP = '\t'
UNIQ_SEP = '\uDCDC'


def field_header(field):
    try:
        number = int(field['Number'])
        number = max(1, number)
        return SEP.join([str(i) for i in range(number)])
    except ValueError:
        return SEP.join([field['Number']])


def default_field_value(number):
    try:
        number = int(number)
        if number == 0:
            return []
        raise RuntimeError
    except ValueError:
        import pdb
        pdb.set_trace()
        pass


def update_fields(fields, spec):
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


def parse_dict(keys, fields, sep):
    fields = fields.split(sep)
    return {k: fields[i] for (i, k) in enumerate(keys)}


def parse_dict_plural_fields(fields, sep):
    fields = fields.split(sep)
    r = dict()
    for f in fields:
        f = f.split('=')
        r[f[0]] = f[1:]
    return r


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


def save_info_head(source_fp, files, metadata):
    lines = dict()
    field_len = dict()
    for m in metadata:
        lines[m['fields']['ID'][0]] = m['line']
        field_len[m['fields']['ID'][0]] = int(m['fields']['Number'][0])

    for k in files:
        fp = files[k]['filepath']
        f = open(fp, 'w')
        files[k]['stream'] = f
        f.write("##SOURCE={}{}".format(source_fp, NEWLINE))
        f.write(lines[k])
        f.write(NEWLINE)
        n = max(field_len[k], 1)
        f.write(SEP.join([str(i) for i in range(n)]))
    return files


def save_format_head(source_fp, sample_ids, files, metadata):
    lines = dict()
    for m in metadata:
        lines[m['fields']['ID'][0]] = m['line']
    for k in files:
        fp = files[k]['filepath']
        f = open(fp, 'w')
        files[k]['stream'] = f
        f.write("##SOURCE={}{}".format(source_fp, NEWLINE))
        f.write(lines[k])
        f.write(NEWLINE)
        f.write(SEP.join(sample_ids))
    return files


def parse_genotype_info(geno_info):
    r = dict()
    for v in geno_info.split(';'):
        vk = v.split('=')
        if len(vk) == 1:
            r[vk[0]] = []
        elif len(vk) == 2:
            r[vk[0]] = [vk[1]]
    return r


def write_genotype_files(metadata, info, files):
    ids = [m['fields']['ID'][0] for m in metadata]
    written = {id_: False for id_ in ids}
    for k in info:
        if len(info[k]) > 0:
            files[k]['stream'].write(NEWLINE + ';'.join(info[k]))
        else:
            files[k]['stream'].write(NEWLINE + '1')
        written[k] = True
    for k in written:
        if not written[k]:
            files[k]['stream'].write(NEWLINE + '0')


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
        self._default = self._df.columns[:9]
        self._samples = self._df.columns[9:]
        self._files.stream('default').write(SEP.join(self._default))

        for k in self._metadata.info:
            v = field_header(self._metadata.info[k])
            self._files.stream(('info', k)).write(v)

        for k in self._metadata.format:
            self._files.stream(('format', k)).write(SEP.join(self._samples))

    def parse_body(self):
        rows = self._df.iterrows()
        while True:
            try:
                self._parse_row(next(rows)[1])
            except StopIteration:
                break

    def _parse_row(self, row):
        self._files.stream('default').write(NEWLINE)
        self._files.stream('default').write(SEP.join(row.iloc[:7].values))

        info = parse_dict_plural_fields(row.iloc[7], ';')
        update_fields(info, self._metadata.info)
        for k in info:
            v = NEWLINE + SEP.join(info[k])
            self._files.stream(('info', k)).write(v)

        keys = row.iloc[8].split(':')
        line = {k: [] for k in self._metadata.format.keys()}

        for fields in row.iloc[9:]:
            data = parse_dict(keys, fields, ':')
            update_fields(data, self._metadata.format)

            for k in data:
                line[k].append(data[k])

        for k in line:
            v = NEWLINE + SEP.join(line[k])
            self._files.stream(('format', k)).write(v)


def unvcf(fp, dst, verbosity):

    if verbosity > 0:
        print("Destination folder: {}".format(abspath(dst)))

    metadata = Metadata(fp, verbosity)
    files = Files(dst)

    files.append('default', '{}.default.csv'.format(basename(fp)))

    for k, v in metadata.format.items():
        files.append(('format', k), '{}.sample.{}.csv'.format(basename(fp), k))

    for k, v in metadata.info.items():
        files.append(('info', k), '{}.genotype.{}.csv'.format(basename(fp), k))

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
