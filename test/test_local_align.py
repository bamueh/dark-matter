import six
from unittest import TestCase
from dark.local_align import LocalAlignment
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord


class TestLocalAlign(TestCase):
    """
    Test the LocalAlignment class.
    With match +1, mismatch -1, gap open -1, gap extend -1 and
        gap extend decay 0.0.
    """

    def testNonDNAString(self):
        """
        If the sequences do not consist of nucleotides, an exception
        must be raised.
        """
        seq1 = SeqRecord(Seq('xxx'), id='seq1')
        seq2 = SeqRecord(Seq('yyy'), id='seq2')
        six.assertRaisesRegex(self, ValueError, 'Invalid DNA nucleotide: "X"',
                              LocalAlignment, seq1, seq2)

    def testPositiveMismatch(self):
        """
        If the mismatch value passed is positive, an exception
        must be raised.
        """
        seq1 = SeqRecord(Seq(''), id='seq1')
        seq2 = SeqRecord(Seq(''), id='seq2')
        six.assertRaisesRegex(self, ValueError, 'Mismatch must be negative',
                              LocalAlignment, seq1, seq2, mismatch=3)

    def testZeroMismatch(self):
        """
        If the mismatch value passed is zero, an exception
        must be raised.
        """
        seq1 = SeqRecord(Seq(''), id='seq1')
        seq2 = SeqRecord(Seq(''), id='seq2')
        six.assertRaisesRegex(self, ValueError, 'Mismatch must be negative',
                              LocalAlignment, seq1, seq2, mismatch=0)

    def testPositiveGap(self):
        """
        If the gap value passed is positive, an exception
        must be raised.
        """
        seq1 = SeqRecord(Seq(''), id='seq1')
        seq2 = SeqRecord(Seq(''), id='seq2')
        six.assertRaisesRegex(self, ValueError, 'Gap must be negative',
                              LocalAlignment, seq1, seq2, gap=3)

    def testZeroGap(self):
        """
        If the gap value passed is zero, an exception
        must be raised.
        """
        seq1 = SeqRecord(Seq(''), id='seq1')
        seq2 = SeqRecord(Seq(''), id='seq2')
        six.assertRaisesRegex(self, ValueError, 'Gap must be negative',
                              LocalAlignment, seq1, seq2, gap=0)

    def testPositiveGapExtend(self):
        """
        If the gap extend value passed is positive, an exception
        must be raised.
        """
        seq1 = SeqRecord(Seq(''), id='seq1')
        seq2 = SeqRecord(Seq(''), id='seq2')
        six.assertRaisesRegex(self, ValueError,
                              'Gap extension penalty cannot be positive',
                              LocalAlignment, seq1, seq2, gapExtend=3)

    def testFirstSequenceEmpty(self):
        """
        If the first sequence passed is empty, an exception must be raised.
        """
        seq1 = SeqRecord(Seq(''), id='seq1')
        seq2 = SeqRecord(Seq('agtcagtcagtc'), id='seq2')
        six.assertRaisesRegex(self, ValueError, 'Empty sequence: seq1',
                              LocalAlignment, seq1, seq2)

    def testSecondSequenceEmpty(self):
        """
        If the second sequence passed is empty, an exception must be raised.
        """
        seq1 = SeqRecord(Seq('agtcagtcagtc'), id='seq1')
        seq2 = SeqRecord(Seq(''), id='seq2')
        six.assertRaisesRegex(self, ValueError, 'Empty sequence: seq2',
                              LocalAlignment, seq1, seq2)

    def testBothSequencesEmpty(self):
        """
        If two empty sequences are passed, an exception must be raised.
        """
        seq1 = SeqRecord(Seq(''), id='seq1')
        seq2 = SeqRecord(Seq(''), id='seq2')
        six.assertRaisesRegex(self, ValueError, 'Empty sequence: seq1',
                              LocalAlignment, seq1, seq2)

    def testGapAtStartOfSeq1(self):
        seq1 = SeqRecord(Seq('gaatcg'), id='seq1')
        seq2 = SeqRecord(Seq('cgaatcg'), id='seq2')
        align = LocalAlignment(seq1, seq2)
        result = align.createAlignment()
        alignment = ("\nCigar string of aligned region: 6=\n"
                     "seq1 Match start: 1 Match end: 6\n"
                     "seq2 Match start: 2 Match end: 7\n"
                     "seq1 1 GAATCG 6\n"
                     "       ||||||\n"
                     "seq2 2 GAATCG 7")
        self.assertEqual(result, alignment)

    def testGapAtStartOfSeq2(self):
        seq1 = SeqRecord(Seq('cgaatcg'), id='seq1')
        seq2 = SeqRecord(Seq('gaatcg'), id='seq2')
        align = LocalAlignment(seq1, seq2)
        result = align.createAlignment()
        alignment = ("\nCigar string of aligned region: 6=\n"
                     "seq1 Match start: 2 Match end: 7\n"
                     "seq2 Match start: 1 Match end: 6\n"
                     "seq1 2 GAATCG 7\n"
                     "       ||||||\n"
                     "seq2 1 GAATCG 6")
        self.assertEqual(result, alignment)

    def testGapAtEndOfSeq1(self):
        seq1 = SeqRecord(Seq('cgaatc'), id='seq1')
        seq2 = SeqRecord(Seq('cgaatcg'), id='seq2')
        align = LocalAlignment(seq1, seq2)
        result = align.createAlignment()
        alignment = ("\nCigar string of aligned region: 6=\n"
                     "seq1 Match start: 1 Match end: 6\n"
                     "seq2 Match start: 1 Match end: 6\n"
                     "seq1 1 CGAATC 6\n"
                     "       ||||||\n"
                     "seq2 1 CGAATC 6")
        self.assertEqual(result, alignment)

    def testGapAtEndOfSeq2(self):
        seq1 = SeqRecord(Seq('cgaatcg'), id='seq1')
        seq2 = SeqRecord(Seq('cgaatc'), id='seq2')
        align = LocalAlignment(seq1, seq2)
        result = align.createAlignment()
        alignment = ("\nCigar string of aligned region: 6=\n"
                     "seq1 Match start: 1 Match end: 6\n"
                     "seq2 Match start: 1 Match end: 6\n"
                     "seq1 1 CGAATC 6\n"
                     "       ||||||\n"
                     "seq2 1 CGAATC 6")
        self.assertEqual(result, alignment)

    def testGapAtBothEndsOfSeq1(self):
        seq1 = SeqRecord(Seq('gaatc'), id='seq1')
        seq2 = SeqRecord(Seq('cgaatcg'), id='seq2')
        align = LocalAlignment(seq1, seq2)
        result = align.createAlignment()
        alignment = ("\nCigar string of aligned region: 5=\n"
                     "seq1 Match start: 1 Match end: 5\n"
                     "seq2 Match start: 2 Match end: 6\n"
                     "seq1 1 GAATC 5\n"
                     "       |||||\n"
                     "seq2 2 GAATC 6")
        self.assertEqual(result, alignment)

    def testGapAtBothEndsOfSeq2(self):
        seq1 = SeqRecord(Seq('cgaatcg'), id='seq1')
        seq2 = SeqRecord(Seq('gaatc'), id='seq2')
        align = LocalAlignment(seq1, seq2)
        result = align.createAlignment()
        align = LocalAlignment(seq1, seq2)
        result = align.createAlignment()
        alignment = ("\nCigar string of aligned region: 5=\n"
                     "seq1 Match start: 2 Match end: 6\n"
                     "seq2 Match start: 1 Match end: 5\n"
                     "seq1 2 GAATC 6\n"
                     "       |||||\n"
                     "seq2 1 GAATC 5")
        self.assertEqual(result, alignment)

    def testAlignmentWithGapInMiddle(self):
        seq1 = SeqRecord(Seq('agtcagtcagtc'), id='seq1')
        seq2 = SeqRecord(Seq('cgaatcg'), id='seq2')
        align = LocalAlignment(seq1, seq2)
        result = align.createAlignment()
        alignment = ("\nCigar string of aligned region: 2=1D1=\n"
                     "seq1 Match start: 7 Match end: 10\n"
                     "seq2 Match start: 5 Match end: 7\n"
                     "seq1 7 TCAG 10\n"
                     "       || |\n"
                     "seq2 5 TC-G 7")
        self.assertEqual(result, alignment)

    def testTwoEqualSequences(self):
        """
        When two identical sequences are given, the result should
        show that the sequences completely match.
        """
        seq1 = SeqRecord(Seq('cgaatcg'), id='seq1')
        seq2 = SeqRecord(Seq('cgaatcg'), id='seq2')
        align = LocalAlignment(seq1, seq2)
        result = align.createAlignment()
        alignment = ("\nCigar string of aligned region: 7=\n"
                     "seq1 Match start: 1 Match end: 7\n"
                     "seq2 Match start: 1 Match end: 7\n"
                     "seq1 1 CGAATCG 7\n"
                     "       |||||||\n"
                     "seq2 1 CGAATCG 7")
        self.assertEqual(result, alignment)

    def testTwoCompletelyDifferentSequences(self):
        """
        When two completely different sequences are given, the result
        should be the two sequences with an empty alignment.
        """
        seq1 = SeqRecord(Seq('aaaaaa'), id='seq1')
        seq2 = SeqRecord(Seq('gggggg'), id='seq2')
        align = LocalAlignment(seq1, seq2)
        result = align.createAlignment()
        alignment = ("\nNo alignment between seq1 and seq2 \n")
        self.assertEqual(result, alignment)

    def testWikiAnswer(self):
        """
        Test the example given in Wikipedia:
        http://en.wikipedia.org/wiki/Smith%E2%80%93Waterman_algorithm
        """
        seq1 = SeqRecord(Seq('ACACACTA'), id='seq1')
        seq2 = SeqRecord(Seq('AGCACACA'), id='seq2')
        align = LocalAlignment(seq1, seq2, match=2)
        result = align.createAlignment()
        alignment = ("\nCigar string of aligned region: 1=1I5=1D1=\n"
                     "seq1 Match start: 1 Match end: 8\n"
                     "seq2 Match start: 1 Match end: 8\n"
                     "seq1 1 A-CACACTA 8\n"
                     "       | ||||| |\n"
                     "seq2 1 AGCACAC-A 8")
        self.assertEqual(result, alignment)

    def testWikiAnswerWithMatchOne(self):
        """
        Test the example given in Wikipedia
        http://en.wikipedia.org/wiki/Smith%E2%80%93Waterman_algorithm
        Wikipedia uses a match score of two, here we use a score of one.
        """
        seq1 = SeqRecord(Seq('ACACACTA'), id='seq1')
        seq2 = SeqRecord(Seq('AGCACACA'), id='seq2')
        align = LocalAlignment(seq1, seq2, match=1)
        result = align.createAlignment()
        alignment = ("\nCigar string of aligned region: 5=1D1=\n"
                     "seq1 Match start: 2 Match end: 8\n"
                     "seq2 Match start: 3 Match end: 8\n"
                     "seq1 2 CACACTA 8\n"
                     "       ||||| |\n"
                     "seq2 3 CACAC-A 8")
        self.assertEqual(result, alignment)
