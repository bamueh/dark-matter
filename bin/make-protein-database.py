#!/usr/bin/env python

from __future__ import print_function, division

import sys
import warnings
from time import time
from itertools import chain
import argparse

from dark.civ.proteins import SqliteIndexWriter
from dark.taxonomy import AccessionLineageFetcher


parser = argparse.ArgumentParser(
    formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    description=('Create a genome/protein sqlite3 database from GenBank '
                 'and JSON files. The protein sequences for the database are '
                 'printed to standard output for indexing by other tools.'))

parser.add_argument(
    '--databaseFile', required=True,
    help=('The output file. This file must not exist (use --force to '
          'overwrite).'))

parser.add_argument(
    '--databaseName',
    help=('The database that the records in the (--gb) GenBank files came '
          'from (e.g., "refseq" or "RVDB").'))

parser.add_argument(
    '--duplicationPolicy', choices=('error', 'ignore'), default='ignore',
    help=('What to do if a to-be-inserted accession number is already '
          'present in the database. "error" results in a ValueError being '
          'raised, "ignore" will ignore the duplicate. It should also be '
          'possible to update (i.e., replace) but that is not supported yet.'))

parser.add_argument(
    '--progress', default=False, action='store_true',
    help='Print indexing progress.')

parser.add_argument(
    '--logFile', type=argparse.FileType('w'),
    help='Write indexing details to a log file.')

parser.add_argument(
    '--noWarnings', default=False, action='store_true',
    help='Do not print warnings about unparseable GenBank or JSON records.')

parser.add_argument(
    '--rnaOnly', default=False, action='store_true',
    help='If given, only include RNA viruses.')

parser.add_argument(
    '--gb', metavar='GenBank-file', nargs='+', action='append',
    help=('The GenBank file(s) to make the database from. These may be '
          'uncompressed, or compressed with bgzip (from samtools), with '
          'a .gz suffix.'))

parser.add_argument(
    '--json', metavar='JSON-file', nargs='+', action='append',
    help=('The JSON file(s) to make the database from. These contain '
          'genome and protein information for cases where sequences that '
          'are not in GenBank should be added.'))

parser.add_argument(
    '--taxonomyDatabase',
    help=('The file holding the sqlite3 taxonomy database. See '
          'https://github.com/acorg/ncbi-taxonomy-database for how to '
          'build one.'))

parser.add_argument(
    '--proteinSource', default='GENBANK',
    help=('The source of the accession numbers for the proteins found in the '
          'input files. This becomes part of the sequence id printed in the '
          'protein FASTA output.'))

parser.add_argument(
    '--genomeSource', default='GENBANK',
    help=('The source of the accession numbers for the genomes in the input '
          'files. This becomes part of the sequence id printed in the '
          'protein FASTA output.'))


def filenamesAndAdders(args, db):
    """
    Get the filenames and database adding functions.

    @param args: A C{Namespace} instance as returned by argparse.
    @param db: An C{SqliteIndexWriter} instance.
    @return: A generator yielding 2-tuples containing a filename and a
        database adder function that can read the file and incorporate it.
    """
    # Use chain to flatten the lists of lists that we get from using both
    # nargs='+' and action='append'. We use both because it allows people
    # to use (e.g.) --gb on the command line either via "--gb file1 --gb
    # file2" or "--gb file1 file2", or a combination of these. That way
    # it's not necessary to remember which way you're supposed to use it
    # and you also can't be hit by the subtle problem encountered in
    # https://github.com/acorg/dark-matter/issues/453

    if not (args.gb or args.json):
        print('At least one of --gb or --json must be used to indicate input '
              'files to process.', file=sys.stderr)
        sys.exit(1)

    if args.gb:
        for filename in chain.from_iterable(args.gb):
            yield filename, db.addGenBankFile

    if args.json:
        for filename in chain.from_iterable(args.json):
            yield filename, db.addJSONFile


def main(args):
    """
    Build the protein database.

    @param args: The namespace of command-line arguments returned by
        argparse.parse_args()
    """
    if args.rnaOnly:
        if args.taxonomyDatabase:
            lineageFetcher = AccessionLineageFetcher(
                args.taxonomyDatabase).lineage
        else:
            print('If you specify --rnaOnly, you must also give a taxonomy '
                  'database file with --taxonomyDatabase', file=sys.stderr)
            sys.exit(1)
    else:
        lineageFetcher = None

    progress = args.progress

    if progress:
        overallStart = time()
        totalGenomeCount = totalProteinCount = 0

    with SqliteIndexWriter(args.databaseFile) as db:
        for fileCount, (filename, addFunc) in enumerate(
                filenamesAndAdders(args, db), start=1):
            if progress:
                print("Indexing '%s' ... " % filename, end='', file=sys.stderr)
                start = time()

            genomeCount, proteinCount = addFunc(
                filename, rnaOnly=args.rnaOnly, databaseName=args.databaseName,
                lineageFetcher=lineageFetcher,
                proteinSource=args.proteinSource,
                genomeSource=args.genomeSource,
                duplicationPolicy=args.duplicationPolicy, logfp=args.logFile)

            if not genomeCount:
                if addFunc is db.addGenBankFile:
                    print('WARNING: no genomes added from %r. Did the GenBank '
                          'download fail on that file?' % filename,
                          file=sys.stderr)
                else:
                    print('WARNING: no genomes added from JSON file %r.' %
                          filename, file=sys.stderr)

            if progress:
                totalGenomeCount += genomeCount
                totalProteinCount += proteinCount
                elapsed = time() - start
                print('indexed %3d genome%s (%5d protein%s) in %.2f seconds.' %
                      (genomeCount, '' if genomeCount == 1 else 's',
                       proteinCount, '' if proteinCount == 1 else 's',
                       elapsed), file=sys.stderr)

    if progress:
        elapsed = time() - overallStart
        print('%d files (containing %d genomes and %d proteins) '
              'processed in %.2f seconds (%.2f mins).' %
              (fileCount, totalGenomeCount, totalProteinCount, elapsed,
               elapsed / 60), file=sys.stderr)


args = parser.parse_args()

if args.noWarnings:
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        main(args)
else:
    main(args)