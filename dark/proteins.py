from __future__ import division, print_function

import os
import re
from os.path import dirname, join
from operator import itemgetter
from six.moves.urllib.parse import quote
import numpy as np
from textwrap import fill
from collections import Counter

import matplotlib
matplotlib.use('PDF')
import matplotlib.pyplot as plt

from dark.dimension import dimensionalIterator
from dark.fasta import FastaReads
from dark.fastq import FastqReads
from dark.html import NCBISequenceLinkURL
from dark.reads import Reads

# The following regex is deliberately greedy (using .*) to consume the
# whole protein name before backtracking to find the last [pathogen name]
# section. That way, it will match just the last [pathogen name] in a
# protein. This avoids situations in which two [...] delimited substrings
# are present in a protein name (in which case we just want the last).
# E.g., the following is a complete protein name:
#
#   gi|19919894|ref|NP_612577.1| Enzymatic polyprotein [Contains: Aspartic
#   protease; Endonuclease; Reverse transcriptase] [Carnation etched ring
#   virus]
#
# Unfortunately the regex doesn't find the pathogen name when the protein
# name has nested [...] sections, as in this example:
#
#   gi|224808893|ref|YP_002643049.1| replication-associated protein [Tomato
#   leaf curl Nigeria virus-[Nigeria:2006]]
#
# I decided not to worry about nested [...] sections (there are only 2
# instances that I know of).
_PATHOGEN_RE = re.compile('^(.*)\[([^\]]+)\]$')

# The pathogen name assigned to proteins whose id strings cannot be parsed
# for a pathogen name (see previous comment).  Do not use '<', '>' or any
# other HTML special chars in the following.
_NO_PATHOGEN_NAME = '[no pathogen name found in sequence id]'


def splitNames(names):
    """
    Split a sequence id string like "Protein name [pathogen name]" into two
    pieces using the final square brackets to delimit the pathogen name.

    @param names: A C{str} "protein name [pathogen name]" string.
    @return: A 2-C{tuple} giving the C{str} protein name and C{str} pathogen
        name. If C{names} cannot be split on square brackets, it is
        returned as the first tuple element, followed by _NO_PATHOGEN_NAME.
    """
    match = _PATHOGEN_RE.match(names)
    if match:
        proteinName = match.group(1).strip()
        pathogenName = match.group(2).strip()
    else:
        proteinName = names
        pathogenName = _NO_PATHOGEN_NAME

    return proteinName, pathogenName


def getPathogenProteinCounts(filenames):
    """
    Get the number of proteins for each pathogen in C{filenames}.

    @param filenames: Either C{None} or a C{list} of C{str} FASTA file names.
        If C{None} an empty C{Counter} is returned. If FASTA file names are
        given, their sequence ids should have the format used in the NCBI
        bacterial and viral protein reference sequence files, in which the
        protein name is followed by the pathogen name in square brackets.
    @return: A C{Counter} keyed by C{str} pathogen name, whose values are
        C{int}s with the count of the number of proteins for the pathogen.
    """
    result = Counter()
    if filenames:
        for filename in filenames:
            for protein in FastaReads(filename):
                _, pathogenName = splitNames(protein.id)
                if pathogenName != _NO_PATHOGEN_NAME:
                    result[pathogenName] += 1

    return result


class PathogenSampleFiles(object):
    """
    Maintain a cache of pathogen/sample FASTA/FASTQ file names, creating
    de-duplicated (by read id) FASTA/FASTQ files (from reads for all proteins
    of a pathogen that a sample has), on demand.

    @param proteinGrouper: An instance of C{ProteinGrouper}.
    @param format_: A C{str}, either 'fasta' or 'fastq' indicating the format
        of the files containing the reads matching proteins.
    @raise ValueError: If C{format_} is unknown.
    """
    def __init__(self, proteinGrouper, format_='fasta'):
        self._proteinGrouper = proteinGrouper
        if format_ in ('fasta', 'fastq'):
            self._format = format_
            self._readsClass = FastaReads if format_ == 'fasta' else FastqReads
        else:
            raise ValueError("format_ must be either 'fasta' or 'fastq'.")
        self._pathogens = {}
        self._samples = {}
        self._readsFilenames = {}

    def add(self, pathogenName, sampleName):
        """
        Add a (pathogen name, sample name) combination and get its FASTA/FASTQ
        file name and unique read count. Write the FASTA/FASTQ file if it does
        not already exist. Save the unique read count into
        C{self._proteinGrouper}.

        @param pathogenName: A C{str} pathogen name.
        @param sampleName: A C{str} sample name.
        @return: A C{str} giving the FASTA/FASTQ file name holding all the
            reads (without duplicates, by id) from the sample that matched the
            proteins in the given pathogen.
        """
        pathogenIndex = self._pathogens.setdefault(pathogenName,
                                                   len(self._pathogens))
        sampleIndex = self._samples.setdefault(sampleName, len(self._samples))

        try:
            return self._readsFilenames[(pathogenIndex, sampleIndex)]
        except KeyError:
            reads = Reads()
            for proteinMatch in self._proteinGrouper.pathogenNames[
                    pathogenName][sampleName]['proteins'].values():
                for read in self._readsClass(proteinMatch['readsFilename']):
                    reads.add(read)
            saveFilename = join(
                proteinMatch['outDir'],
                'pathogen-%d-sample-%d.%s' % (pathogenIndex, sampleIndex,
                                              self._format))
            reads.filter(removeDuplicatesById=True)
            nReads = reads.save(saveFilename, format_=self._format)
            # Save the unique read count into self._proteinGrouper
            self._proteinGrouper.pathogenNames[
                pathogenName][sampleName]['uniqueReadCount'] = nReads
            self._readsFilenames[(pathogenIndex, sampleIndex)] = saveFilename
            return saveFilename

    def lookup(self, pathogenName, sampleName):
        """
        Look up a pathogen name, sample name combination and get its
        FASTA/FASTQ file name and unique read count.

        This method should be used instead of C{add} in situations where
        you want an exception to be raised if a pathogen/sample combination has
        not already been passed to C{add}.

        @param pathogenName: A C{str} pathogen name.
        @param sampleName: A C{str} sample name.
        @raise KeyError: If the pathogen name or sample name have not been
            seen, either individually or in combination.
        @return: A (C{str}, C{int}) tuple retrieved from self._readsFilenames
        """
        pathogenIndex = self._pathogens[pathogenName]
        sampleIndex = self._samples[sampleName]
        return self._readsFilenames[(pathogenIndex, sampleIndex)]

    def writeSampleIndex(self, fp):
        """
        Write a file of sample indices and names, sorted by index.

        @param fp: A file-like object, opened for writing.
        """
        print('\n'.join(
            '%d %s' % (index, name) for (index, name) in
            sorted((index, name) for (name, index) in self._samples.items())
        ), file=fp)

    def writePathogenIndex(self, fp):
        """
        Write a file of pathogen indices and names, sorted by index.

        @param fp: A file-like object, opened for writing.
        """
        print('\n'.join(
            '%d %s' % (index, name) for (index, name) in
            sorted((index, name) for (name, index) in self._pathogens.items())
        ), file=fp)


class ProteinGrouper(object):
    """
    Group matched proteins by the pathogen they come from.

    @param assetDir: The C{str} directory name where
        C{noninteractive-alignment-panel.py} put its HTML, blue plot and
        alignment panel images, and FASTA or FASTQ files. This must be relative
        to the filenames that will later be passed to C{addFile}.
    @param sampleNameRegex: A C{str} regular expression that can be used to
        extract a short sample name from full file names subsequently passed
        to C{self.addFile}. The regular expression must have a matching group
        (delimited by parentheses) to capture the part of the file name that
        should be used as the sample name.
    @param format_: A C{str}, either 'fasta' or 'fastq' indicating the format
        of the files containing the reads matching proteins.
    @param proteinFastaFilenames: If not C{None}, a C{list} of C{str} filenames
        giving the name of the FASTA file with the protein AA sequences with
        their associated pathogens in square brackets. This is the format used
        by NCBI for the bacterial and viral reference sequence protein files.
        If given, the contents of this file will be used to determine how many
        proteins each matched pathogen has.
    @param saveReadLengths: If C{True}, save the lengths of all reads matching
        proteins.
    @raise ValueError: If C{format_} is unknown.
    """

    VIRALZONE = 'http://viralzone.expasy.org/cgi-bin/viralzone/search?query='

    def __init__(self, assetDir='out', sampleNameRegex=None, format_='fasta',
                 proteinFastaFilenames=None, saveReadLengths=False):
        self._assetDir = assetDir
        self._sampleNameRegex = (re.compile(sampleNameRegex) if sampleNameRegex
                                 else None)
        if format_ in ('fasta', 'fastq'):
            self._format = format_
        else:
            raise ValueError("format_ must be either 'fasta' or 'fastq'.")
        self._saveReadLengths = saveReadLengths

        self._pathogenProteinCount = getPathogenProteinCounts(
            proteinFastaFilenames)

        # pathogenNames will be a dict of dicts of dicts. The first two keys
        # will be a pathogen name and a sample name. The final dict will
        # contain 'proteins' (a list of dicts) and 'uniqueReadCount' (an int).
        self.pathogenNames = {}
        # sampleNames is keyed by sample name and will have values that hold
        # the sample's alignment panel index.html file.
        self.sampleNames = {}
        self.pathogenSampleFiles = PathogenSampleFiles(self, format_=format_)

    def _title(self):
        """
        Create a title summarizing the pathogens and samples.

        @return: A C{str} title.
        """
        return (
            'Overall, proteins from %d pathogen%s were found in %d sample%s.' %
            (len(self.pathogenNames),
             '' if len(self.pathogenNames) == 1 else 's',
             len(self.sampleNames),
             '' if len(self.sampleNames) == 1 else 's'))

    def maxProteinFraction(self, pathogenName):
        """
        Get the fraction of a pathogen's proteins matched by any sample that
        matches the pathogen.

        @param pathogenName: A C{str} pathogen name.
        @return: The C{float} maximum fraction of a pathogen's proteins that is
            matched by any sample. If the number of proteins for the pathogen
            is unknown, return 1.0 (i.e., assume all proteins are matched).
        """

        proteinCount = self._pathogenProteinCount[pathogenName]
        if proteinCount:
            maxMatches = max(
                len(sample['proteins'])
                for sample in self.pathogenNames[pathogenName].values())
            return maxMatches / proteinCount
        else:
            return 1.0

    def addFile(self, filename, fp):
        """
        Read and record protein information for a sample.

        @param filename: A C{str} file name.
        @param fp: An open file pointer to read the file's data from.
        @raise ValueError: If information for a pathogen/protein/sample
            combination is given more than once.
        """
        if self._sampleNameRegex:
            match = self._sampleNameRegex.search(filename)
            if match:
                sampleName = match.group(1)
            else:
                sampleName = filename
        else:
            sampleName = filename

        outDir = join(dirname(filename), self._assetDir)

        self.sampleNames[sampleName] = join(outDir, 'index.html')

        for index, proteinLine in enumerate(fp):
            proteinLine = proteinLine[:-1]
            (coverage, medianScore, bestScore, readCount, hspCount,
             proteinLength, names) = proteinLine.split(None, 6)

            proteinName, pathogenName = splitNames(names)

            if pathogenName not in self.pathogenNames:
                self.pathogenNames[pathogenName] = {}

            if sampleName not in self.pathogenNames[pathogenName]:
                self.pathogenNames[pathogenName][sampleName] = {
                    'proteins': {},
                    'uniqueReadCount': None,
                }

            proteins = self.pathogenNames[pathogenName][sampleName]['proteins']

            # We should only receive one line of information for a given
            # pathogen/sample/protein combination.
            if proteinName in proteins:
                raise ValueError(
                    'Protein %r already seen for pathogen %r sample %r.' %
                    (proteinName, pathogenName, sampleName))

            readsFilename = join(outDir, '%d.%s' % (index, self._format))

            proteins[proteinName] = {
                'bestScore': float(bestScore),
                'bluePlotFilename': join(outDir, '%d.png' % index),
                'coverage': float(coverage),
                'readsFilename': readsFilename,
                'hspCount': int(hspCount),
                'index': index,
                'medianScore': float(medianScore),
                'outDir': outDir,
                'proteinLength': int(proteinLength),
                'proteinName': proteinName,
                'proteinURL': NCBISequenceLinkURL(proteinName),
                'readCount': int(readCount),
            }

            if self._saveReadLengths:
                readsClass = (FastaReads if self._format == 'fasta'
                              else FastqReads)
                proteins[proteinName]['readLengths'] = tuple(
                    len(read) for read in readsClass(readsFilename))

    def _computeUniqueReadCounts(self):
        """
        Add all pathogen / sample combinations to self.pathogenSampleFiles.

        This will make all de-duplicated (by id) FASTA/FASTQ files and store
        the number of de-duplicated reads into C{self.pathogenNames}.
        """
        for pathogenName, samples in self.pathogenNames.items():
            for sampleName in samples:
                self.pathogenSampleFiles.add(pathogenName, sampleName)

    def toStr(self):
        """
        Produce a string representation of the pathogen summary.

        @return: A C{str} suitable for printing.
        """
        # Note that the string representation contains much less
        # information than the HTML summary. E.g., it does not contain the
        # unique (de-duplicated, by id) read count, since that is only computed
        # when we are making combined FASTA files of reads matching a
        # pathogen.
        readCountGetter = itemgetter('readCount')
        result = []
        append = result.append

        append(self._title())
        append('')

        for pathogenName in sorted(self.pathogenNames):
            samples = self.pathogenNames[pathogenName]
            sampleCount = len(samples)
            append('%s (in %d sample%s)' %
                   (pathogenName,
                    sampleCount, '' if sampleCount == 1 else 's'))
            for sampleName in sorted(samples):
                proteins = samples[sampleName]['proteins']
                proteinCount = len(proteins)
                totalReads = sum(readCountGetter(p) for p in proteins.values())
                append('  %s (%d protein%s, %d read%s)' %
                       (sampleName,
                        proteinCount, '' if proteinCount == 1 else 's',
                        totalReads, '' if totalReads == 1 else 's'))
                for proteinName in sorted(proteins):
                    append(
                        '    %(coverage).2f\t%(medianScore).2f\t'
                        '%(bestScore).2f\t%(readCount)4d\t%(hspCount)4d\t'
                        '%(index)3d\t%(proteinName)s'
                        % proteins[proteinName])
            append('')

        return '\n'.join(result)

    def toHTML(self, pathogenPanelFilename=None, minProteinFraction=0.0,
               pathogenType='viral', sampleIndexFilename=None,
               pathogenIndexFilename=None):
        """
        Produce an HTML string representation of the pathogen summary.

        @param pathogenPanelFilename: If not C{None}, a C{str} filename to
            write a pathogen panel PNG image to.
        @param minProteinFraction: The C{float} minimum fraction of proteins
            in a pathogen that must be matched by at least one sample in order
            for that pathogen to be displayed.
        @param pathogenType: A C{str} giving the type of the pathogen involved,
            either 'bacterial' or 'viral'.
        @param sampleIndexFilename: A C{str} filename to write a sample index
            file to. Lines in the file will have an integer index, a space, and
            then the sample name.
        @param pathogenIndexFilename: A C{str} filename to write a pathogen
            index file to. Lines in the file will have an integer index, a
            space, and then the pathogen name.
        @return: An HTML C{str} suitable for printing.
        """
        if pathogenType not in ('bacterial', 'viral'):
            raise ValueError(
                "Unrecognized pathogenType argument: %r. Value must be either "
                "'bacterial' or 'viral'." % pathogenType)

        highlightSymbol = '&starf;'
        self._computeUniqueReadCounts()

        if pathogenPanelFilename:
            self.pathogenPanel(pathogenPanelFilename)

        if sampleIndexFilename:
            with open(sampleIndexFilename, 'w') as fp:
                self.pathogenSampleFiles.writeSampleIndex(fp)

        if pathogenIndexFilename:
            with open(pathogenIndexFilename, 'w') as fp:
                self.pathogenSampleFiles.writePathogenIndex(fp)

        pathogenNames = sorted(
            pathogenName for pathogenName in self.pathogenNames
            if self.maxProteinFraction(pathogenName) >= minProteinFraction)
        nPathogenNames = len(pathogenNames)
        sampleNames = sorted(self.sampleNames)

        result = [
            '<html>',
            '<head>',
            '<title>',
            'Summary of pathogens',
            '</title>',
            '<meta charset="UTF-8">',
            '</head>',
            '<body>',
            '<style>',
            '''\
            body {
                margin-left: 2%;
                margin-right: 2%;
            }
            hr {
                display: block;
                margin-top: 0.5em;
                margin-bottom: 0.5em;
                margin-left: auto;
                margin-right: auto;
                border-style: inset;
                border-width: 1px;
            }
            p.pathogen {
                margin-top: 10px;
                margin-bottom: 3px;
            }
            p.sample {
                margin-top: 10px;
                margin-bottom: 3px;
            }
            .significant {
                color: red;
                margin-right: 2px;
            }
            .sample {
                margin-top: 5px;
                margin-bottom: 2px;
            }
            ul {
                margin-bottom: 2px;
            }
            .indented {
                margin-left: 2em;
            }
            .sample-name {
                font-size: 125%;
                font-weight: bold;
            }
            .pathogen-name {
                font-size: 125%;
                font-weight: bold;
            }
            .index-name {
                font-weight: bold;
            }
            .index {
                font-size: small;
            }
            .protein-name {
                font-family: "Courier New", Courier, monospace;
            }
            .stats {
                font-family: "Courier New", Courier, monospace;
                white-space: pre;
            }
            .protein-list {
                margin-top: 2px;
            }''',
            '</style>',
            '</head>',
            '<body>',
        ]

        proteinFieldsDescription = [
            '<p>',
            'In all bullet point protein lists below, there are the following '
            'fields:',
            '<ol>',
            '<li>Coverage fraction.</li>',
            '<li>Median bit score.</li>',
            '<li>Best bit score.</li>',
            '<li>Read count.</li>',
            '<li>HSP count (a read can match a protein more than once).</li>',
            '<li>Protein length (in AAs).</li>',
            '<li>Index (just ignore this).</li>',
        ]

        if self._saveReadLengths:
            proteinFieldsDescription.append(
                '<li>All read lengths (in parentheses).</li>')

        proteinFieldsDescription.extend([
            '<li>Protein name.</li>',
            '</ol>',
            '</p>',
        ])

        append = result.append

        append('<h1>Summary of pathogens</h1>')
        append('<p>')
        append(self._title())

        if self._pathogenProteinCount:
            percent = minProteinFraction * 100.0
            if nPathogenNames < len(self.pathogenNames):
                if nPathogenNames == 1:
                    append('Pathogen protein fraction filtering has been '
                           'applied, so information on only 1 pathogen is '
                           'displayed. This is the only pathogen for which at '
                           'least one sample matches at least %.2f%% of the '
                           'pathogen proteins.' % percent)
                else:
                    append('Pathogen protein fraction filtering has been '
                           'applied, so information on only %d pathogens is '
                           'displayed. These are the only pathogens for which '
                           'at least one sample matches at least %.2f%% of '
                           'the pathogen proteins.' % (nPathogenNames,
                                                       percent))
            else:
                append('Pathogen protein fraction filtering has been applied, '
                       'but all pathogens have at least %.2f%% of their '
                       'proteins matched by at least one sample.' % percent)

            append('Samples that match a pathogen (and pathogens with a '
                   'matching sample) with at least this protein fraction are '
                   'highlighted using <span class="significant">%s</span>.' %
                   highlightSymbol)

        append('</p>')

        if pathogenPanelFilename:
            append('<p>')
            append('<a href="%s">Panel showing read count per pathogen, per '
                   'sample.</a>' % pathogenPanelFilename)
            append('Red vertical bars indicate samples with an unusually high '
                   'read count.')
            append('</p>')

        result.extend(proteinFieldsDescription)

        # Write a linked table of contents by pathogen.
        append('<p><span class="index-name">Pathogen index:</span>')
        append('<span class="index">')
        for pathogenName in pathogenNames:
            append('<a href="#pathogen-%s">%s</a>' % (pathogenName,
                                                      pathogenName))
            append('&middot;')
        # Get rid of final middle dot and add a period.
        result.pop()
        result[-1] += '.'
        append('</span></p>')

        # Write a linked table of contents by sample.
        append('<p><span class="index-name">Sample index:</span>')
        append('<span class="index">')
        for sampleName in sampleNames:
            append('<a href="#sample-%s">%s</a>' % (sampleName, sampleName))
            append('&middot;')
        # Get rid of final middle dot and add a period.
        result.pop()
        result[-1] += '.'
        append('</span></p>')

        # Write all pathogens (with samples (with proteins)).
        append('<hr>')
        append('<h1>Pathogens by sample</h1>')

        for pathogenName in pathogenNames:
            samples = self.pathogenNames[pathogenName]
            sampleCount = len(samples)
            pathogenProteinCount = self._pathogenProteinCount[pathogenName]
            if pathogenType == 'viral':
                pathogenNameHTML = '<a href="%s%s">%s</a>' % (
                    self.VIRALZONE, quote(pathogenName), pathogenName)
            else:
                pathogenNameHTML = pathogenName
            append(
                '<a id="pathogen-%s"></a>'
                '<p class="pathogen"><span class="pathogen-name">%s</span>'
                '%s, was matched by %d sample%s:</p>' %
                (pathogenName, pathogenNameHTML,
                 ((' (with %d protein%s)' %
                   (pathogenProteinCount,
                    '' if pathogenProteinCount == 1 else 's'))
                  if pathogenProteinCount else ''),
                 sampleCount,
                 '' if sampleCount == 1 else 's'))
            for sampleName in sorted(samples):
                readsFileName = self.pathogenSampleFiles.lookup(
                    pathogenName, sampleName)
                proteins = samples[sampleName]['proteins']
                proteinCount = len(proteins)
                uniqueReadCount = samples[sampleName]['uniqueReadCount']
                if pathogenProteinCount and (
                        proteinCount / pathogenProteinCount >=
                        minProteinFraction):
                    highlight = ('<span class="significant">%s</span>' %
                                 highlightSymbol)
                else:
                    highlight = ''

                append(
                    '<p class="sample indented">'
                    '%sSample <a href="#sample-%s">%s</a> '
                    '(%d protein%s, <a href="%s">%d de-duplicated (by id) '
                    'read%s</a>, <a href="%s">panel</a>):</p>' %
                    (highlight, sampleName, sampleName,
                     proteinCount, '' if proteinCount == 1 else 's',
                     readsFileName,
                     uniqueReadCount, '' if uniqueReadCount == 1 else 's',
                     self.sampleNames[sampleName]))
                append('<ul class="protein-list indented">')
                for proteinName in sorted(proteins):
                    proteinMatch = proteins[proteinName]
                    append(
                        '<li>'
                        '<span class="stats">'
                        '%(coverage).2f %(medianScore).2f %(bestScore).2f '
                        '%(readCount)4d %(hspCount)4d %(proteinLength)4d '
                        '%(index)3d '
                        % proteinMatch
                    )

                    if self._saveReadLengths:
                        append('(%s) ' % ', '.join(
                            map(str, sorted(proteinMatch['readLengths']))))

                    append(
                        '</span> '
                        '<span class="protein-name">'
                        '%(proteinName)s'
                        '</span> '
                        '(<a href="%(bluePlotFilename)s">blue plot</a>, '
                        '<a href="%(readsFilename)s">reads</a>'
                        % proteinMatch)

                    if proteinMatch['proteinURL']:
                        # Append this directly to the last string in result, to
                        # avoid introducing whitespace when we join result
                        # using '\n'.
                        result[-1] += (', <a href="%s">NCBI</a>' %
                                       proteinMatch['proteinURL'])
                    result[-1] += ')'

                    append('</li>')

                append('</ul>')

        # Write all samples (with pathogens (with proteins)).
        append('<hr>')
        append('<h1>Samples by pathogen</h1>')

        for sampleName in sampleNames:
            samplePathogenNames = set()
            for pathogenName in pathogenNames:
                if (sampleName in self.pathogenNames[pathogenName] and
                        self.maxProteinFraction(pathogenName) >=
                        minProteinFraction):
                    samplePathogenNames.add(pathogenName)

            append(
                '<a id="sample-%s"></a>'
                '<p class="sample">Sample <span class="sample-name">%s</span> '
                'matched proteins from %d pathogen%s, '
                '<a href="%s">panel</a>:</p>' %
                (sampleName, sampleName, len(samplePathogenNames),
                 '' if len(samplePathogenNames) == 1 else 's',
                 self.sampleNames[sampleName]))

            for pathogenName in sorted(samplePathogenNames):
                readsFileName = self.pathogenSampleFiles.lookup(pathogenName,
                                                                sampleName)
                proteins = self.pathogenNames[pathogenName][sampleName][
                    'proteins']
                uniqueReadCount = self.pathogenNames[
                    pathogenName][sampleName]['uniqueReadCount']
                proteinCount = len(proteins)
                pathogenProteinCount = self._pathogenProteinCount[pathogenName]

                highlight = ''
                if pathogenProteinCount:
                    proteinCountStr = '%d/%d protein%s' % (
                        proteinCount, pathogenProteinCount,
                        '' if pathogenProteinCount == 1 else 's')
                    if (proteinCount / pathogenProteinCount >=
                            minProteinFraction):
                        highlight = ('<span class="significant">%s</span>' %
                                     highlightSymbol)
                else:
                    proteinCountStr = '%d protein%s' % (
                        proteinCount, '' if proteinCount == 1 else 's')

                append(
                    '<p class="sample indented">'
                    '%s<a href="#pathogen-%s">%s</a> %s, '
                    '<a href="%s">%d de-duplicated (by id) read%s</a>:</p>' %
                    (highlight, pathogenName, pathogenName,
                     proteinCountStr, readsFileName,
                     uniqueReadCount, '' if uniqueReadCount == 1 else 's'))
                append('<ul class="protein-list indented">')
                for proteinName in sorted(proteins):
                    proteinMatch = proteins[proteinName]
                    append(
                        '<li>'
                        '<span class="stats">'
                        '%(coverage).2f %(medianScore).2f %(bestScore).2f '
                        '%(readCount)4d %(hspCount)4d %(proteinLength)4d '
                        '%(index)3d '
                        '</span> '
                        '<span class="protein-name">'
                        '%(proteinName)s'
                        '</span> '
                        '(<a href="%(bluePlotFilename)s">blue plot</a>, '
                        '<a href="%(readsFilename)s">reads</a>'
                        % proteinMatch)

                    if proteinMatch['proteinURL']:
                        # Append this directly to the last string in result, to
                        # avoid introducing whitespace when we join result
                        # using '\n'.
                        result[-1] += (', <a href="%s">NCBI</a>' %
                                       proteinMatch['proteinURL'])
                    result[-1] += ')'

                    append('</li>')

                append('</ul>')

        append('</body>')
        append('</html>')

        return '\n'.join(result)

    def _pathogenSamplePlot(self, pathogenName, sampleNames, ax):
        """
        Make an image of a graph giving pathogen read count (Y axis) versus
        sample id (X axis).

        @param pathogenName: A C{str} pathogen name.
        @param sampleNames: A sorted C{list} of sample names.
        @param ax: A matplotlib C{axes} instance.
        """
        readCounts = []
        for i, sampleName in enumerate(sampleNames):
            try:
                readCount = self.pathogenNames[pathogenName][sampleName][
                    'uniqueReadCount']
            except KeyError:
                readCount = 0
            readCounts.append(readCount)

        highlight = 'r'
        normal = 'gray'
        sdMultiple = 2.5
        minReadsForHighlighting = 10
        highlighted = []

        if len(readCounts) == 1:
            if readCounts[0] > minReadsForHighlighting:
                color = [highlight]
                highlighted.append(sampleNames[0])
            else:
                color = [normal]
        else:
            mean = np.mean(readCounts)
            sd = np.std(readCounts)
            color = []
            for readCount, sampleName in zip(readCounts, sampleNames):
                if (readCount > (sdMultiple * sd) + mean and
                        readCount >= minReadsForHighlighting):
                    color.append(highlight)
                    highlighted.append(sampleName)
                else:
                    color.append(normal)

        nSamples = len(sampleNames)
        x = np.arange(nSamples)
        yMin = np.zeros(nSamples)
        ax.set_xticks([])
        ax.set_xlim((-0.5, nSamples - 0.5))
        ax.vlines(x, yMin, readCounts, color=color)
        if highlighted:
            title = '%s\nIn red: %s' % (
                pathogenName, fill(', '.join(highlighted), 50))
        else:
            # Add a newline to keep the first line of each title at the
            # same place as those titles that have an "In red:" second
            # line.
            title = pathogenName + '\n'

        ax.set_title(title, fontsize=10)
        ax.tick_params(axis='both', which='major', labelsize=8)
        ax.tick_params(axis='both', which='minor', labelsize=6)

    def pathogenPanel(self, filename):
        """
        Make a panel of images, with each image being a graph giving pathogen
        de-duplicated (by id) read count (Y axis) versus sample id (X axis).

        @param filename: A C{str} file name to write the image to.
        """
        self._computeUniqueReadCounts()
        pathogenNames = sorted(self.pathogenNames)
        sampleNames = sorted(self.sampleNames)

        cols = 5
        rows = int(len(pathogenNames) / cols) + (
            0 if len(pathogenNames) % cols == 0 else 1)
        figure, ax = plt.subplots(rows, cols, squeeze=False)

        coords = dimensionalIterator((rows, cols))

        for i, pathogenName in enumerate(pathogenNames):
            row, col = next(coords)
            self._pathogenSamplePlot(pathogenName, sampleNames, ax[row][col])

        # Hide the final panel graphs (if any) that have no content. We do
        # this because the panel is a rectangular grid and some of the
        # plots at the end of the last row may be unused.
        for row, col in coords:
            ax[row][col].axis('off')

        figure.suptitle(
            ('Per-sample read count for %d pathogen%s and %d sample%s.\n\n'
             'Sample name%s: %s') % (
                 len(pathogenNames),
                 '' if len(pathogenNames) == 1 else 's',
                 len(sampleNames),
                 '' if len(sampleNames) == 1 else 's',
                 '' if len(sampleNames) == 1 else 's',
                 fill(', '.join(sampleNames), 50)),
            fontsize=20)
        figure.set_size_inches(5.0 * cols, 2.0 * rows, forward=True)
        plt.subplots_adjust(hspace=0.4)

        figure.savefig(filename)
