# unvcf

[![Travis](https://img.shields.io/travis/horta/unvcf.svg?style=flat-square&label=linux%20%2F%20macos%20build)](https://travis-ci.org/horta/unvcf) [![AppVeyor](https://img.shields.io/appveyor/ci/Horta/unvcf.svg?style=flat-square&label=windows%20build)](https://ci.appveyor.com/project/Horta/unvcf)

Split VCF file into intelligible tab-delimited files.

VCF stands for variants call format and is widelly used in bioinformatics for saving XX information for being flexible enough to store a wide range of data. Although it has been inspired by CSV files to (I suppose) make VCF easy to read by humans and easy to parse by machines, it is nowadays hardly doing well in both instances. It is a file format whose full specification cannot be given before-hand as each VCF files is free to specify the format of its own fields. As a result, the first step to process data contained in a VCF file is often extracting a subset of it and converting the extract data into a more amenable file format.

This command-line Python package aims to tackle the above problems. It will split a VCF format into standard CSV files, each of which containing a different field of the original VCF file. Therefore facilitating making it both easier to read by humans and machines again.

## Install

Assuming you have a up-to-date Python installation, you will almost certainly have all the necessary requirements to install unvcf. From terminal, enter:
```bash
pip install unvcf
```

## Usage

After the installation, you will have acccess to `unvcf` from terminal.
In which case you can start using it as follows:

```bash
unvcf path_to_file.vcf destination_folder/
```

This will produce CSV files that represent the original fields of `path_to_file.vcf`.
For more information, you can enter

```bash
unvcf --help
```

If by any change you face a problem or have a question, please, create a [new issue](https://github.com/horta/unvcf/issues/new) and we will try to sort it out as soon as possible.

## Authors

* [Danilo Horta](https://github.com/horta)

## License

This project is licensed under the [MIT License](https://raw.githubusercontent.com/horta/unvcf/master/LICENSE.md).
